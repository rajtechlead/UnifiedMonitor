"""Microsoft 365 onboarding: device-code sign-in plus automatic app registration.

The old flow told the administrator to click through Entra, paste three GUIDs and a
secret into a text file. This module does the same work through Graph: an admin signs
in with a device code, the app registration is created with every role UniMonitor
needs, admin consent is granted, and a client secret is returned — then stored in the
secret vault by the caller.

Two Graph permissions drive the automation: `Application.ReadWrite.All` (create the
app and its secret) and `AppRoleAssignment.ReadWrite.All` (grant consent). Both come
from the delegated sign-in, so no credential has to exist beforehand.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx

from unimonitor.core.logging import get_logger
from unimonitor.onboarding.permissions import GRAPH_APP_ID, OPTIONAL, REQUIRED

logger = get_logger(__name__)

LOGIN_BASE = "https://login.microsoftonline.com"
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
    client_secret: str
    granted: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _client(client: httpx.AsyncClient | None) -> tuple[httpx.AsyncClient, bool]:
    if client is not None:
        return client, False
    return httpx.AsyncClient(timeout=30), True


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
    `{"status": "ok", "access_token": ..., "tenant_id": ...}`.
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


async def provision_app(
    access_token: str,
    *,
    display_name: str = "UniMonitor",
    client: httpx.AsyncClient | None = None,
) -> ProvisionResult:
    """Create the app registration, grant admin consent and mint a client secret."""
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

        secret = await _graph(
            http,
            "POST",
            f"/applications/{app_object_id}/addPassword",
            access_token,
            payload={"passwordCredential": {"displayName": "unimonitor-setup"}},
        )
        client_secret = secret.get("secretText", "")

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

        if not client_secret:
            raise M365Error("Graph created the app but returned no client secret.")

        logger.info("M365 app registration provisioned", app_id=app_id, tenant_id=tenant_id, granted=len(granted))
        return ProvisionResult(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            client_id=app_id,
            client_secret=client_secret,
            granted=granted,
            warnings=warnings,
        )
    finally:
        if owned:
            await http.aclose()


async def verify_client_credentials(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Prove the saved credentials work; returns the tenant display name.

    Used for both the automated and the manual path, so a typo surfaces during setup
    instead of as an empty dashboard.
    """
    http, owned = _client(client)
    try:
        resp = await http.post(
            f"{LOGIN_BASE}/{tenant_id}/oauth2/v2.0/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://graph.microsoft.com/.default",
            },
        )
        data = resp.json() if resp.content else {}
        token = data.get("access_token")
        if not token:
            raise M365Error(data.get("error_description", "Client credentials were rejected."))
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
