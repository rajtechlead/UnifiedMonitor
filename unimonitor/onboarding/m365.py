"""Microsoft 365 onboarding: device-code sign-in plus automatic app registration.

The old flow told the administrator to click through Entra, paste three GUIDs and a
secret into a text file. This module does the same work through Graph: an admin signs
in with a device code, the app registration is created with every role UniMonitor
needs, admin consent is granted, and a credential is returned — a certificate by
default, a client secret on request.

Two Graph permissions drive the automation: `Application.ReadWrite.All` (create the
app and its credential) and `AppRoleAssignment.ReadWrite.All` (grant consent). Both
come from the delegated sign-in, so no credential has to exist beforehand.

Certificate upload can be refused (tenant policy, or a consent that only covers app
creation). That is not fatal: the certificate is handed back to the administrator to
upload in the portal, and `verify_client_credentials()` proves it works before setup
is allowed to finish.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx

from unimonitor.core.logging import get_logger
from unimonitor.onboarding import certificates
from unimonitor.onboarding.permissions import GRAPH_APP_ID, OPTIONAL, REQUIRED

logger = get_logger(__name__)

LOGIN_BASE = certificates.LOGIN_BASE
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Azure CLI's first-party client: a public client that supports the device-code flow
# and already holds delegated Application.ReadWrite.All, which is what lets the wizard
# register an app before UniMonitor has any credentials of its own.
PUBLIC_CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
SCOPES = (
    "https://graph.microsoft.com/Application.ReadWrite.All "
    "https://graph.microsoft.com/AppRoleAssignment.ReadWrite.All "
    "https://graph.microsoft.com/Directory.Read.All "
    "offline_access openid profile"
)

GRAPH_SCOPE = "https://graph.microsoft.com/.default"
ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"

AUTH_METHODS = ("certificate", "client_secret")

MANUAL_CERTIFICATE_STEPS = (
    "Save the certificate files to this computer — the .cer file is what Entra accepts.",
    "Open Entra admin centre → Identity → Applications → App registrations → UniMonitor → "
    "Certificates & secrets → Certificates → Upload certificate.",
    "Choose the downloaded .cer file, then Add.",
    "Come back here and press “Check certificate connectivity” to finish.",
)


class M365Error(RuntimeError):
    """A step of the M365 onboarding failed; the message is shown to the administrator."""


@dataclass
class DeviceCode:
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int
    message: str


@dataclass
class ProvisionResult:
    tenant_id: str
    tenant_name: str
    client_id: str
    auth_method: str = "certificate"
    client_secret: str = ""
    certificate: certificates.ClientCertificate | None = None
    certificate_uploaded: bool = False
    certificate_error: str = ""
    app_object_id: str = ""
    manual_steps: list[str] = field(default_factory=list)
    granted: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _client(client: httpx.AsyncClient | None) -> tuple[httpx.AsyncClient, bool]:
    if client is not None:
        return client, False
    return httpx.AsyncClient(timeout=60), True


async def _graph(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    token: str,
    *,
    payload: dict | None = None,
    retries: int = 1,
) -> dict[str, Any]:
    """Call Graph, retrying while a freshly created object replicates.

    Consent against a service principal Entra has not finished replicating fails with
    400/404 for a few seconds; retrying is what makes one-click consent reliable.
    """
    url = path if path.startswith("http") else f"{GRAPH_BASE}{path}"
    last = ""
    for attempt in range(retries):
        resp = await client.request(
            method,
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
        )
        if resp.status_code < 400:
            return resp.json() if resp.content else {}
        last = f"{resp.status_code} {resp.text[:300]}"
        if resp.status_code not in (400, 404, 409) or attempt == retries - 1:
            break
        await asyncio.sleep(3)
    raise M365Error(f"Graph {method} {path} failed: {last}")


async def start_device_flow(client: httpx.AsyncClient | None = None) -> DeviceCode:
    """Ask Entra for a device code the administrator enters at microsoft.com/devicelogin."""
    http, owned = _client(client)
    try:
        resp = await http.post(
            f"{LOGIN_BASE}/organizations/oauth2/v2.0/devicecode",
            data={"client_id": PUBLIC_CLIENT_ID, "scope": SCOPES},
        )
        if resp.status_code >= 400:
            raise M365Error(f"Could not start Microsoft sign-in: {resp.text[:300]}")
        data = resp.json()
        return DeviceCode(
            device_code=data["device_code"],
            user_code=data["user_code"],
            verification_uri=data.get("verification_uri", "https://microsoft.com/devicelogin"),
            expires_in=int(data.get("expires_in", 900)),
            interval=int(data.get("interval", 5)),
            message=data.get("message", ""),
        )
    finally:
        if owned:
            await http.aclose()


async def poll_device_flow(device_code: str, client: httpx.AsyncClient | None = None) -> dict[str, str]:
    """Poll the token endpoint once.

    Returns `{"status": "pending"}` until the administrator finishes signing in, then
    `{"status": "ok", "access_token": ...}`.
    """
    http, owned = _client(client)
    try:
        resp = await http.post(
            f"{LOGIN_BASE}/organizations/oauth2/v2.0/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": PUBLIC_CLIENT_ID,
                "device_code": device_code,
            },
        )
        data = resp.json()
        if resp.status_code < 400 and data.get("access_token"):
            return {"status": "ok", "access_token": data["access_token"]}
        error = data.get("error", "")
        if error == "authorization_pending":
            return {"status": "pending"}
        if error == "slow_down":
            return {"status": "pending", "slow_down": "1"}
        if error in ("authorization_declined", "expired_token"):
            return {"status": "expired" if error == "expired_token" else "declined"}
        raise M365Error(data.get("error_description", error or "Device sign-in failed"))
    finally:
        if owned:
            await http.aclose()


async def _resolve_role_ids(client: httpx.AsyncClient, token: str) -> tuple[str, dict[str, str]]:
    """Return the Microsoft Graph service principal id and app-role name → id map."""
    body = await _graph(
        client,
        "GET",
        f"/servicePrincipals?$filter=appId eq '{GRAPH_APP_ID}'&$select=id,appRoles",
        token,
    )
    items = body.get("value", [])
    if not items:
        raise M365Error("Microsoft Graph service principal not found in this tenant.")
    sp = items[0]
    return sp["id"], {r["value"]: r["id"] for r in sp.get("appRoles", []) if r.get("value")}


async def _tenant_info(client: httpx.AsyncClient, token: str) -> tuple[str, str]:
    body = await _graph(client, "GET", "/organization?$select=id,displayName", token)
    org = (body.get("value") or [{}])[0]
    return org.get("id", ""), org.get("displayName", "")


async def add_certificate(
    access_token: str,
    app_object_id: str,
    certificate: certificates.ClientCertificate,
    *,
    client: httpx.AsyncClient | None = None,
) -> None:
    """Upload the public certificate to an existing app registration."""
    http, owned = _client(client)
    try:
        await _graph(
            http,
            "POST",
            f"/applications/{app_object_id}/addKey",
            access_token,
            payload={"keyCredential": certificates.graph_key_credential(certificate)},
        )
    finally:
        if owned:
            await http.aclose()


async def provision_app(
    access_token: str,
    *,
    display_name: str = "UniMonitor",
    auth_method: str = "certificate",
    certificate_validity_days: int | None = None,
    client: httpx.AsyncClient | None = None,
) -> ProvisionResult:
    """Create the app registration, grant admin consent and add one credential.

    `auth_method="certificate"` (the default) generates a certificate and uploads it.
    If Graph refuses the upload the result carries the certificate and the portal
    steps instead of raising: the app and its consent are already in place, so all
    that is left is a file upload the administrator can do.
    """
    if auth_method not in AUTH_METHODS:
        raise M365Error(f"Unknown authentication method '{auth_method}'.")

    http, owned = _client(client)
    try:
        tenant_id, tenant_name = await _tenant_info(http, access_token)
        graph_sp_id, role_ids = await _resolve_role_ids(http, access_token)

        warnings: list[str] = []
        required_roles = []
        for perm in REQUIRED:
            if perm.name in role_ids:
                required_roles.append({"id": role_ids[perm.name], "type": "Role"})
            else:
                warnings.append(f"Graph has no app role '{perm.name}'; skipped.")
        optional_roles = [{"id": role_ids[p.name], "type": "Role"} for p in OPTIONAL if p.name in role_ids]

        app = await _graph(
            http,
            "POST",
            "/applications",
            access_token,
            payload={
                "displayName": display_name,
                "signInAudience": "AzureADMyOrg",
                "requiredResourceAccess": [
                    {
                        "resourceAppId": GRAPH_APP_ID,
                        "resourceAccess": required_roles + optional_roles,
                    }
                ],
            },
        )
        app_id, app_object_id = app["appId"], app["id"]

        sp = await _graph(
            http,
            "POST",
            "/servicePrincipals",
            access_token,
            payload={"appId": app_id},
            retries=5,
        )
        sp_id = sp["id"]

        # Admin consent: assign each Graph app role to the new service principal.
        granted: list[str] = []
        for perm in REQUIRED + OPTIONAL:
            role_id = role_ids.get(perm.name)
            if not role_id:
                continue
            try:
                await _graph(
                    http,
                    "POST",
                    f"/servicePrincipals/{graph_sp_id}/appRoleAssignedTo",
                    access_token,
                    payload={"principalId": sp_id, "resourceId": graph_sp_id, "appRoleId": role_id},
                    retries=5,
                )
                granted.append(perm.name)
            except M365Error as exc:
                # An optional role a tenant refuses must not abort the whole setup.
                warnings.append(f"{perm.name} not granted: {exc}")

        result = ProvisionResult(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            client_id=app_id,
            auth_method=auth_method,
            app_object_id=app_object_id,
            granted=granted,
            warnings=warnings,
        )

        if auth_method == "client_secret":
            secret = await _graph(
                http,
                "POST",
                f"/applications/{app_object_id}/addPassword",
                access_token,
                payload={"passwordCredential": {"displayName": "unimonitor-setup"}},
            )
            result.client_secret = secret.get("secretText", "")
            if not result.client_secret:
                raise M365Error("Graph created the app but returned no client secret.")
            logger.info("M365 app registration provisioned", app_id=app_id, tenant_id=tenant_id, auth="client_secret")
            return result

        result.certificate = certificates.generate_client_certificate(display_name, certificate_validity_days)
        try:
            await add_certificate(access_token, app_object_id, result.certificate, client=http)
            result.certificate_uploaded = True
        except M365Error as exc:
            result.certificate_error = str(exc)
            result.manual_steps = list(MANUAL_CERTIFICATE_STEPS)
            warnings.append(f"Certificate upload failed: {exc}")

        logger.info(
            "M365 app registration provisioned",
            app_id=app_id,
            tenant_id=tenant_id,
            auth="certificate",
            uploaded=result.certificate_uploaded,
            granted=len(granted),
        )
        return result
    finally:
        if owned:
            await http.aclose()


async def verify_client_credentials(
    tenant_id: str,
    client_id: str,
    client_secret: str = "",
    *,
    certificate_pem: str = "",
    private_key_pem: str = "",
    client: httpx.AsyncClient | None = None,
) -> str:
    """Prove the saved credentials work; returns the tenant display name.

    Accepts a client secret or a certificate + private key, so both the automated and
    the manual path (and the manual-upload fallback) are checked the same way — a typo
    surfaces during setup instead of as an empty dashboard.
    """
    if not (certificate_pem and private_key_pem) and not client_secret:
        raise M365Error("Supply a client secret or a certificate with its private key.")

    http, owned = _client(client)
    try:
        data: dict[str, str] = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "scope": GRAPH_SCOPE,
        }
        if certificate_pem and private_key_pem:
            try:
                data["client_assertion_type"] = ASSERTION_TYPE
                data["client_assertion"] = certificates.client_assertion(client_id, tenant_id, private_key_pem, certificate_pem)
            except Exception as exc:  # noqa: BLE001 — a bad key file is a user-facing error
                raise M365Error(f"Could not read the certificate or private key: {exc}") from exc
        else:
            data["client_secret"] = client_secret

        resp = await http.post(f"{LOGIN_BASE}/{tenant_id}/oauth2/v2.0/token", data=data)
        body = resp.json() if resp.content else {}
        token = body.get("access_token")
        if not token:
            detail = body.get("error_description") or body.get("error") or f"HTTP {resp.status_code}"
            raise M365Error(f"Entra rejected the credentials: {detail}")
        name = ""
        try:
            _, name = await _tenant_info(http, token)
        except M365Error:
            # The token is valid; a missing Directory.Read.All only costs the display name.
            pass
        return name or tenant_id
    finally:
        if owned:
            await http.aclose()
