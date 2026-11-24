"""First-run setup: platform catalogue, connection storage and runtime hand-off.

The wizard writes one `CloudConnection` row per platform and puts every secret in the
configured secret provider, so the database only ever holds references. The collectors
still read their settings from configuration, so `hydrate_runtime_config()` is the
single seam that turns stored connections into the values they expect.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.config import get_settings
from unimonitor.core.logging import get_logger
from unimonitor.db.models.cloud_connection import CloudConnection
from unimonitor.db.models.tenant import Tenant
from unimonitor.db.models.user import AppUser
from unimonitor.grc.providers import PROVIDERS
from unimonitor.onboarding import certificates, clouds, m365
from unimonitor.onboarding.google_auth import GCP_SCOPES, WORKSPACE_SCOPES, mint_access_token
from unimonitor.onboarding.permissions import MANUAL_FOLLOW_UP
from unimonitor.secrets.resolver import get_secret_resolver

logger = get_logger(__name__)

# What each platform asks for, in the order the wizard shows it. Secrets are listed
# under `secret_fields` so the UI can mask them and the service knows to vault them.
# `auth_methods` drives the mode selector: Entra defaults to a certificate, AWS can use
# a role instead of long-lived keys, and the two Google platforms can share one key.
PLATFORM_FIELDS: dict[str, dict[str, Any]] = {
    "microsoft": {
        "config": [
            {
                "name": "tenant",
                "label": "Directory (tenant) ID",
                "placeholder": "filled in automatically by the wizard",
                "required": "",
            },
            {
                "name": "client_id",
                "label": "Application (client) ID",
                "placeholder": "00000000-0000-0000-0000-000000000000",
                "required": "",
            },
        ],
        "secrets": [
            {
                "name": "client_secret",
                "label": "Client secret",
                "placeholder": "only for client-secret authentication",
                "required": "",
            },
            {
                "name": "certificate_pem",
                "label": "Certificate",
                "placeholder": "-----BEGIN CERTIFICATE-----",
                "required": "",
                "multiline": "1",
            },
            {
                "name": "private_key_pem",
                "label": "Private key",
                "placeholder": "-----BEGIN PRIVATE KEY-----",
                "required": "",
                "multiline": "1",
            },
        ],
        "auth_methods": [
            {
                "id": "certificate",
                "label": "Certificate (recommended)",
                "description": "UniMonitor generates a certificate, uploads it to the app registration and keeps the private key in the vault.",
            },
            {
                "id": "client_secret",
                "label": "Client secret",
                "description": "Entra mints a secret string instead; rotate it in the portal when it expires.",
            },
        ],
        "automated": [
            {
                "id": "device_code",
                "label": "Sign in as a Global Administrator",
                "hint": "UniMonitor creates the app registration and grants consent for you.",
            }
        ],
    },
    "aws": {
        "config": [
            {"name": "region", "label": "AWS region", "placeholder": "us-east-1", "required": "1"},
            {
                "name": "role_arn",
                "label": "IAM role ARN",
                "placeholder": "arn:aws:iam::123456789012:role/UniMonitorReadOnly",
                "required": "",
            },
        ],
        "secrets": [
            {"name": "access_key_id", "label": "Access key ID", "placeholder": "AKIA...", "required": ""},
            {"name": "secret_access_key", "label": "Secret access key", "placeholder": "", "required": ""},
            {"name": "session_token", "label": "Session token", "placeholder": "optional", "required": ""},
            {"name": "external_id", "label": "External ID", "placeholder": "only if the role trust policy requires one", "required": ""},
        ],
        "auth_methods": [
            {"id": "access_keys", "label": "Access keys", "description": "An IAM user's key pair with the read-only policy attached."},
            {
                "id": "iam_role",
                "label": "IAM role / SSO (assume role)",
                "description": (
                    "One role trust-policy for UniMonitor; it assumes the role with the identity it already "
                    "runs as — no long-lived access keys to hand out."
                ),
            },
        ],
    },
    "gcp": {
        "config": [{"name": "project_id", "label": "Project ID", "placeholder": "my-project", "required": "1"}],
        "secrets": [
            {
                "name": "credentials_json",
                "label": "Service-account JSON key",
                "placeholder": "paste the key file contents",
                "required": "",
                "multiline": "1",
            },
            {"name": "access_token", "label": "— or an access token", "placeholder": "ya29...", "required": ""},
        ],
        "auth_methods": [
            {"id": "service_account_key", "label": "Service-account key", "description": "Paste a key that can read this project."},
            {
                "id": "shared_service_account",
                "label": "One service account for both Google platforms",
                "description": "Reuse a single service account for Google Cloud and Workspace so the administrator maintains one identity.",
            },
        ],
    },
    "google_workspace": {
        "config": [
            {"name": "admin_email", "label": "Administrator email", "placeholder": "admin@example.com", "required": "1"},
            {"name": "customer_id", "label": "Customer ID", "placeholder": "my_customer", "required": ""},
        ],
        "secrets": [
            {
                "name": "credentials_json",
                "label": "Service-account JSON key (domain-wide delegation)",
                "placeholder": "paste the key file contents",
                "required": "",
                "multiline": "1",
            },
            {"name": "access_token", "label": "— or an access token", "placeholder": "ya29...", "required": ""},
        ],
        "auth_methods": [
            {"id": "service_account_key", "label": "Service-account key", "description": "A key with domain-wide delegation for the admin scopes."},
            {
                "id": "shared_service_account",
                "label": "One service account for both Google platforms",
                "description": "Reuse the Google Cloud service account, adding domain-wide delegation, so there is only one key to rotate.",
            },
        ],
    },
}


def _loads(raw: str | None) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def platform_catalogue() -> list[dict[str, Any]]:
    """Everything the wizard needs to render the platform picker."""
    catalogue = []
    # Only platforms with a collector appear: a picker entry that can never produce
    # evidence would look connected and silently report nothing.
    platforms = [
        {
            "id": provider.id,
            "name": provider.name,
            "short_name": provider.short_name,
            "description": provider.description,
            "colour": provider.colour,
        }
        for provider in PROVIDERS.values()
    ]
    for platform in platforms:
        fields = PLATFORM_FIELDS[platform["id"]]
        catalogue.append(
            {
                **platform,
                "automated": bool(fields.get("automated")),
                "config_fields": fields["config"],
                "secret_fields": fields["secrets"],
                "auth_methods": fields.get("auth_methods", []),
            }
        )
    return catalogue


async def first_tenant(session: AsyncSession) -> Tenant | None:
    return (await session.execute(select(Tenant).limit(1))).scalar_one_or_none()


async def connected_providers(session: AsyncSession, tenant_id: str | None = None) -> set[str]:
    """Providers with a completed connection — the only ones that can have data."""
    stmt = select(CloudConnection.provider).where(CloudConnection.status == "connected")
    if tenant_id is not None:
        stmt = stmt.where(CloudConnection.tenant_id == tenant_id)
    return set((await session.execute(stmt)).scalars().all())


async def has_admin(session: AsyncSession) -> bool:
    count = await session.scalar(select(func.count()).select_from(AppUser).where(AppUser.role == "admin"))
    return bool(count)


async def get_status(session: AsyncSession) -> dict[str, Any]:
    """Drive the first-run redirect and the setup checklist."""
    admin_exists = await has_admin(session)
    rows = list((await session.execute(select(CloudConnection))).scalars())
    # A connection waiting for its certificate upload is listed but does not count as
    # configured: the wizard may not finish until connectivity is proven.
    connected = {row.provider: connection_dict(row) for row in rows if row.status == "connected"}
    return {
        "needs_admin": not admin_exists,
        "configured": admin_exists and bool(connected),
        "connections": [connection_dict(row) for row in rows],
        "connected_providers": sorted(connected),
        "platforms": platform_catalogue(),
        "manual_follow_up": MANUAL_FOLLOW_UP,
    }


def connection_dict(row: CloudConnection) -> dict[str, Any]:
    return {
        "id": row.id,
        "provider": row.provider,
        "account": row.account,
        "display_name": row.display_name,
        "status": row.status,
        "config": _loads(row.config),
        "last_error": row.last_error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def create_first_admin(session: AsyncSession, email: str, password: str, organisation: str = "") -> AppUser:
    """Create the local admin and its tenant. Refuses once an admin exists."""
    if await has_admin(session):
        raise PermissionError("An administrator already exists; sign in to add platforms.")
    if not email or "@" not in email:
        raise ValueError("A valid email address is required.")
    if len(password) < 12:
        raise ValueError("Use a password of at least 12 characters.")

    tenant = await first_tenant(session)
    if tenant is None:
        tenant = Tenant(tenant_id="local", name=organisation or "Default Organization", display_name=organisation or None)
        session.add(tenant)
        await session.flush()

    user = AppUser(
        tenant_id=tenant.id,
        email=email.strip().lower(),
        full_name="Administrator",
        role="admin",
        is_active=True,
        is_verified=True,
        hashed_password=bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8"),
    )
    session.add(user)
    await session.flush()
    logger.info("first admin created", email=user.email)
    return user


async def upsert_connection(
    session: AsyncSession,
    *,
    tenant_id: str,
    provider: str,
    account: str,
    display_name: str,
    config: dict[str, Any],
    secrets: dict[str, str],
    status: str = "connected",
) -> CloudConnection:
    """Store a connection; secrets go to the vault, only their names to the database."""
    resolver = await get_secret_resolver()
    secret_refs: dict[str, str] = {}
    for field, value in secrets.items():
        if not value:
            continue
        ref = f"unimonitor/connections/{provider}/{field}"
        await resolver.set(ref, value)
        secret_refs[field] = ref

    existing = (
        (await session.execute(select(CloudConnection).where(CloudConnection.provider == provider, CloudConnection.tenant_id == tenant_id)))
        .scalars()
        .first()
    )

    row = existing or CloudConnection(tenant_id=tenant_id, provider=provider)
    row.account = account
    row.display_name = display_name or (PROVIDERS[provider].name if provider in PROVIDERS else provider.title())
    row.status = status
    row.config = json.dumps(config)
    row.secret_refs = json.dumps(secret_refs)
    row.last_error = None
    row.last_checked_at = datetime.now(UTC)
    if existing is None:
        session.add(row)
    await session.flush()
    logger.info("cloud connection stored", provider=provider, account=account)
    return row


def _require_tenant(tenant: Tenant | None) -> str:
    if tenant is None:
        raise ValueError("Run the setup wizard first: no tenant exists yet.")
    return tenant.id


async def connect_microsoft(
    session: AsyncSession,
    *,
    tenant_id: str,
    client_id: str,
    client_secret: str = "",
    tenant: str = "",
    display_name: str = "",
    granted: list[str] | None = None,
    auth_method: str = "certificate",
    certificate_pem: str = "",
    private_key_pem: str = "",
) -> CloudConnection:
    """Validate and save Microsoft 365 credentials (automated or manual)."""
    if auth_method not in m365.AUTH_METHODS:
        raise ValueError(f"Unknown authentication method '{auth_method}'.")
    if not client_id:
        raise ValueError("An application (client) ID is required.")
    if auth_method == "certificate" and not (certificate_pem and private_key_pem):
        raise ValueError("Certificate authentication needs both the certificate and its private key.")
    if auth_method == "client_secret" and not client_secret:
        raise ValueError("Client-secret authentication needs a client secret.")

    directory = tenant or tenant_id
    name = await m365.verify_client_credentials(
        directory,
        client_id,
        client_secret,
        certificate_pem=certificate_pem,
        private_key_pem=private_key_pem,
    )
    config: dict[str, Any] = {"client_id": client_id, "auth_method": auth_method, "granted_permissions": granted or []}
    if certificate_pem:
        config["certificate_thumbprint"] = certificates.thumbprint(certificate_pem)
        config["certificate_expires_at"] = certificates.expiry(certificate_pem).replace(microsecond=0).isoformat()
    row = await upsert_connection(
        session,
        tenant_id=tenant_id,
        provider="microsoft",
        account=directory,
        display_name=display_name or name,
        config=config,
        secrets={
            "client_secret": client_secret,
            "certificate_pem": certificate_pem,
            "private_key_pem": private_key_pem,
        },
    )
    # Sign-in and the pages that call Graph straight after setup must see this app
    # without waiting for the next process restart.
    await _hydrate_microsoft(session, get_settings(), row, config)
    return row


async def verify_microsoft_connection(session: AsyncSession) -> CloudConnection:
    """Re-check a stored Microsoft connection and mark it connected.

    This is what the certificate-upload fallback calls after the administrator has
    added the certificate in the Entra portal.
    """
    row = (await session.execute(select(CloudConnection).where(CloudConnection.provider == "microsoft"))).scalars().first()
    if row is None:
        raise ValueError("No Microsoft 365 connection has been started yet.")
    config = _loads(row.config)
    auth_method = config.get("auth_method", "client_secret")
    await m365.verify_client_credentials(
        row.account,
        config.get("client_id", ""),
        await _stored_secret(session, "microsoft", "client_secret"),
        certificate_pem=await _stored_secret(session, "microsoft", "certificate_pem") if auth_method == "certificate" else "",
        private_key_pem=await _stored_secret(session, "microsoft", "private_key_pem") if auth_method == "certificate" else "",
    )
    row.status = "connected"
    row.last_error = None
    row.last_checked_at = datetime.now(UTC)
    await session.flush()
    await _hydrate_microsoft(session, get_settings(), row, config)
    logger.info("microsoft connection verified", provider="microsoft", auth=auth_method)
    return row


async def rotate_microsoft_certificate(session: AsyncSession, *, validity_days: int | None = None) -> CloudConnection:
    """Add a fresh certificate to the app registration and drop the old one.

    The runtime app already holds Application.ReadWrite.All, so rotation needs no new
    sign-in: mint an app-only token with the stored certificate, add the new key, prove
    it works, then retire the old key so a leaked copy stops being useful.
    """
    row = (await session.execute(select(CloudConnection).where(CloudConnection.provider == "microsoft"))).scalars().first()
    if row is None:
        raise ValueError("No Microsoft 365 connection to rotate.")
    config = _loads(row.config)
    client_id = config.get("client_id", "")
    old_certificate = await _stored_secret(session, "microsoft", "certificate_pem")
    old_key = await _stored_secret(session, "microsoft", "private_key_pem")
    if config.get("auth_method") != "certificate" or not (client_id and old_certificate and old_key):
        raise ValueError("This connection does not use a certificate; rotate the client secret in the Entra portal.")

    token = await m365.client_credentials_token(
        row.account,
        client_id,
        certificate_pem=old_certificate,
        private_key_pem=old_key,
    )
    object_id = config.get("app_object_id") or await m365.find_app_object_id(token, client_id)
    new_certificate = certificates.generate_client_certificate(row.display_name or "UniMonitor", validity_days)
    try:
        await m365.add_certificate(token, object_id, new_certificate)
    except m365.M365Error as exc:
        if " 403 " not in str(exc):
            raise
        # A registration made by hand has neither the permission nor the ownership.
        raise ValueError(
            "Entra refused the new certificate: this app registration may not manage itself. "
            "Grant the UniMonitor app the application permission Application.ReadWrite.OwnedBy and "
            "add it as an owner of its own registration (Entra → App registrations → UniMonitor → "
            "Owners → Add), or upload a new certificate in the portal and reconnect Microsoft 365."
        ) from exc
    await m365.verify_client_credentials(
        row.account,
        client_id,
        certificate_pem=new_certificate.certificate_pem,
        private_key_pem=new_certificate.private_key_pem,
    )

    updated = {
        **config,
        "app_object_id": object_id,
        "certificate_thumbprint": new_certificate.thumbprint,
        "certificate_expires_at": new_certificate.not_after_iso,
    }
    row = await upsert_connection(
        session,
        tenant_id=row.tenant_id,
        provider="microsoft",
        account=row.account,
        display_name=row.display_name,
        config=updated,
        secrets={"certificate_pem": new_certificate.certificate_pem, "private_key_pem": new_certificate.private_key_pem},
    )

    # Collectors read the settings singleton, so the new key must land there now.
    settings = get_settings()
    settings.ENTRA_CLIENT_CERTIFICATE = new_certificate.certificate_pem
    settings.ENTRA_CLIENT_PRIVATE_KEY = new_certificate.private_key_pem
    settings.ENTRA_CLIENT_SECRET = ""

    try:
        removed = await m365.remove_certificate(token, object_id, old_certificate)
        if not removed:
            logger.warning("previous certificate not found in Entra", provider="microsoft")
    except m365.M365Error as exc:
        # The new certificate works; a stale one is worth a warning, not a failed rotation.
        logger.warning("could not remove the previous certificate", error=str(exc))

    logger.info("microsoft certificate rotated", thumbprint=new_certificate.thumbprint, expires=new_certificate.not_after_iso)
    return row


async def connect_platform(session: AsyncSession, provider: str, payload: dict[str, Any], tenant_id: str | None = None) -> CloudConnection:
    """Validate a platform's credentials, then persist the connection.

    ``tenant_id`` lets the Managed tenants page onboard a client with its own
    platform credentials; omitting it keeps the first-run wizard's behaviour.
    """
    if tenant_id:
        if await session.get(Tenant, tenant_id) is None:
            raise ValueError(f"Tenant '{tenant_id}' not found")
        local_tenant = tenant_id
    else:
        local_tenant = _require_tenant(await first_tenant(session))
    provider = provider.strip().lower()

    if provider == "microsoft":
        return await connect_microsoft(
            session,
            tenant_id=local_tenant,
            client_id=str(payload.get("client_id", "")).strip(),
            client_secret=str(payload.get("client_secret", "")).strip(),
            tenant=str(payload.get("tenant", "")).strip(),
            granted=payload.get("granted_permissions") or [],
            auth_method=str(payload.get("auth_method") or "certificate"),
            certificate_pem=str(payload.get("certificate_pem", "")).strip(),
            private_key_pem=str(payload.get("private_key_pem", "")).strip(),
        )

    if provider == "aws":
        region = str(payload.get("region") or get_settings().AWS_REGION or "us-east-1")
        role_arn = str(payload.get("role_arn", "")).strip()
        auth_method = str(payload.get("auth_method") or ("iam_role" if role_arn else "access_keys"))
        if auth_method == "iam_role":
            account = await clouds.validate_aws_role(role_arn, region, str(payload.get("external_id", "")).strip())
            return await upsert_connection(
                session,
                tenant_id=local_tenant,
                provider="aws",
                account=account,
                display_name=f"AWS {account}",
                config={"region": region, "role_arn": role_arn, "auth_mode": "iam_role"},
                secrets={"external_id": str(payload.get("external_id", "")).strip()},
            )

        account = await clouds.validate_aws(
            region,
            str(payload.get("access_key_id", "")).strip(),
            str(payload.get("secret_access_key", "")).strip(),
            str(payload.get("session_token", "")).strip() or None,
        )
        return await upsert_connection(
            session,
            tenant_id=local_tenant,
            provider="aws",
            account=account,
            display_name=f"AWS {account}",
            config={"region": region, "auth_mode": "access_keys"},
            secrets={
                "access_key_id": str(payload.get("access_key_id", "")).strip(),
                "secret_access_key": str(payload.get("secret_access_key", "")).strip(),
                "session_token": str(payload.get("session_token", "")).strip(),
            },
        )

    if provider == "gcp":
        project = str(payload.get("project_id", "")).strip()
        name = await clouds.validate_gcp(
            project,
            str(payload.get("credentials_json", "")),
            str(payload.get("access_token", "")),
        )
        return await upsert_connection(
            session,
            tenant_id=local_tenant,
            provider="gcp",
            account=project,
            display_name=name,
            config={"project_id": project},
            secrets={
                "credentials_json": str(payload.get("credentials_json", "")),
                "access_token": str(payload.get("access_token", "")),
            },
        )

    if provider == "google_workspace":
        admin_email = str(payload.get("admin_email", "")).strip()
        customer = str(payload.get("customer_id", "")).strip() or "my_customer"
        await clouds.validate_workspace(
            admin_email,
            customer,
            str(payload.get("credentials_json", "")),
            str(payload.get("access_token", "")),
        )
        return await upsert_connection(
            session,
            tenant_id=local_tenant,
            provider="google_workspace",
            account=customer,
            display_name=f"Google Workspace ({admin_email})",
            config={"admin_email": admin_email, "customer_id": customer},
            secrets={
                "credentials_json": str(payload.get("credentials_json", "")),
                "access_token": str(payload.get("access_token", "")),
            },
        )

    raise ValueError(f"Unknown platform '{provider}'.")


async def connect_google_service_account(
    session: AsyncSession,
    *,
    project_id: str = "",
    admin_email: str = "",
    customer_id: str = "",
    credentials_json: str = "",
    access_token: str = "",
    providers: list[str] | None = None,
) -> list[CloudConnection]:
    """Connect Google Cloud and Workspace with a single service account.

    The administrator creates one service account, grants it project read access and
    domain-wide delegation, then pastes one key here. Both connections share it, so
    there is one key to rotate instead of one per platform.
    """
    local_tenant = _require_tenant(await first_tenant(session))
    wanted = [p for p in (providers or ["gcp", "google_workspace"]) if p in ("gcp", "google_workspace")]
    if not wanted:
        raise ValueError("Choose Google Cloud, Google Workspace or both.")

    rows: list[CloudConnection] = []
    if "gcp" in wanted:
        name = await clouds.validate_gcp(project_id, credentials_json, access_token)
        rows.append(
            await upsert_connection(
                session,
                tenant_id=local_tenant,
                provider="gcp",
                account=project_id,
                display_name=name,
                config={"project_id": project_id, "shared_service_account": True},
                secrets={"credentials_json": credentials_json},
            )
        )
    if "google_workspace" in wanted:
        customer = customer_id.strip() or "my_customer"
        await clouds.validate_workspace(admin_email, customer, credentials_json, access_token)
        rows.append(
            await upsert_connection(
                session,
                tenant_id=local_tenant,
                provider="google_workspace",
                account=customer,
                display_name=f"Google Workspace ({admin_email})",
                config={"admin_email": admin_email, "customer_id": customer, "shared_service_account": True},
                secrets={"credentials_json": credentials_json},
            )
        )
    return rows


async def delete_tenant_connection(session: AsyncSession, tenant_id: str, provider: str) -> bool:
    """Remove one tenant's connection and its stored secrets."""
    row = (
        (await session.execute(select(CloudConnection).where(CloudConnection.tenant_id == tenant_id, CloudConnection.provider == provider)))
        .scalars()
        .first()
    )
    if row is None:
        return False
    resolver = await get_secret_resolver()
    for ref in _loads(row.secret_refs).values():
        try:
            await resolver.delete(ref)
        except Exception as exc:  # noqa: BLE001 - removal must not fail on a missing secret
            logger.warning("could not delete connection secret", ref=ref, error=str(exc))
    await session.delete(row)
    await session.flush()
    return True


async def delete_connection(session: AsyncSession, provider: str) -> bool:
    row = (await session.execute(select(CloudConnection).where(CloudConnection.provider == provider))).scalars().first()
    if row is None:
        return False
    resolver = await get_secret_resolver()
    for ref in _loads(row.secret_refs).values():
        try:
            await resolver.delete(ref)
        except Exception as exc:  # noqa: BLE001 — a missing secret must not block removal
            logger.warning("could not delete connection secret", ref=ref, error=str(exc))
    await session.delete(row)
    await session.flush()
    return True


async def _connection_secret(session: AsyncSession, row: CloudConnection, field: str) -> str:
    """Resolve one stored secret for a specific connection."""
    ref = _loads(row.secret_refs).get(field)
    if not ref:
        return ""
    try:
        return await (await get_secret_resolver()).get(ref)
    except KeyError:
        return ""


async def _stored_secret(session: AsyncSession, provider: str, field: str) -> str:
    row = (await session.execute(select(CloudConnection).where(CloudConnection.provider == provider))).scalars().first()
    if row is None:
        return ""
    return await _connection_secret(session, row, field)


async def microsoft_app(session: AsyncSession, tenant_id: str | None = None) -> dict[str, Any]:
    """The connected Entra app, with its credential resolved from the vault.

    One resolver serves sign-in and the Graph client so neither has to guess at the
    `Tenant` row (which stores a reference, not a credential) and a certificate-based
    connection works everywhere a client secret does.
    """
    settings = get_settings()
    stmt = select(CloudConnection).where(CloudConnection.provider == "microsoft", CloudConnection.status == "connected")
    if tenant_id:
        stmt = stmt.where(CloudConnection.tenant_id == tenant_id)
    row = (await session.execute(stmt.order_by(CloudConnection.created_at))).scalars().first()

    if row is None:
        return {
            "configured": bool(settings.ENTRA_CLIENT_ID and settings.ENTRA_TENANT_ID),
            "client_id": settings.ENTRA_CLIENT_ID,
            "directory": settings.ENTRA_TENANT_ID,
            "auth_method": "certificate" if settings.ENTRA_CLIENT_CERTIFICATE else "client_secret",
            "client_secret": settings.ENTRA_CLIENT_SECRET,
            "certificate_pem": settings.ENTRA_CLIENT_CERTIFICATE,
            "private_key_pem": settings.ENTRA_CLIENT_PRIVATE_KEY,
            "source": "settings",
        }

    config = _loads(row.config)
    auth_method = config.get("auth_method", "client_secret")
    certificate_pem = private_key_pem = ""
    client_secret = ""
    if auth_method == "certificate":
        certificate_pem = await _connection_secret(session, row, "certificate_pem")
        private_key_pem = await _connection_secret(session, row, "private_key_pem")
    else:
        client_secret = await _connection_secret(session, row, "client_secret")

    client_id = config.get("client_id", "")
    return {
        "configured": bool(client_id and row.account),
        "client_id": client_id,
        "directory": row.account,
        "auth_method": auth_method,
        "client_secret": client_secret,
        "certificate_pem": certificate_pem,
        "private_key_pem": private_key_pem,
        "source": "connection",
        "connection_id": row.id,
        "display_name": row.display_name,
    }


async def google_token_for(provider: str, session: AsyncSession | None = None) -> str:
    """Mint a Google access token from the stored connection, if there is one."""
    if session is None:
        from unimonitor.db.base import db_session_context

        async with db_session_context() as own_session:
            return await google_token_for(provider, own_session)

    row = (await session.execute(select(CloudConnection).where(CloudConnection.provider == provider))).scalars().first()
    if row is None:
        return ""
    config = _loads(row.config)
    credentials_json = await _stored_secret(session, provider, "credentials_json")
    if credentials_json:
        scopes = WORKSPACE_SCOPES if provider == "google_workspace" else GCP_SCOPES
        subject = config.get("admin_email") if provider == "google_workspace" else None
        try:
            return await mint_access_token(credentials_json, scopes, subject=subject)
        except Exception as exc:  # noqa: BLE001 — collection must not raise on a bad key
            logger.warning("google token mint failed", provider=provider, error=str(exc))
    return await _stored_secret(session, provider, "access_token")


async def aws_credentials_for(session: AsyncSession | None = None) -> dict[str, str] | None:
    """Stored AWS keys, for the collector when the environment has none."""
    if session is None:
        from unimonitor.db.base import db_session_context

        async with db_session_context() as own_session:
            return await aws_credentials_for(own_session)

    row = (await session.execute(select(CloudConnection).where(CloudConnection.provider == "aws"))).scalars().first()
    if row is None:
        return None
    config = _loads(row.config)
    if config.get("auth_mode") == "iam_role" and config.get("role_arn"):
        try:
            assumed = await clouds.assume_role_credentials(
                config["role_arn"],
                await _stored_secret(session, "aws", "external_id"),
                config.get("region", "us-east-1"),
            )
        except Exception as exc:  # noqa: BLE001 — collection must not raise on a bad role
            logger.warning("AWS role assumption failed", error=str(exc))
            return None
        assumed.pop("aws_account_id", None)
        return assumed
    return {
        "aws_access_key_id": await _stored_secret(session, "aws", "access_key_id"),
        "aws_secret_access_key": await _stored_secret(session, "aws", "secret_access_key"),
        "region_name": config.get("region", "us-east-1"),
    }


async def hydrate_runtime_config(session: AsyncSession) -> None:
    """Apply stored connections to the settings singleton the collectors read.

    Microsoft credentials live on `Settings`, so this is where a connection made in the
    browser becomes the credential the Graph client uses after a restart.
    """
    settings = get_settings()
    rows = [row for row in (await session.execute(select(CloudConnection))).scalars() if row.status == "connected"]
    for row in rows:
        await _hydrate_connection(session, settings, row)
    logger.info("runtime configuration hydrated", connections=len(rows))


async def _hydrate_connection(session: AsyncSession, settings: Any, row: Any) -> None:
    """Copy one saved connection's identifiers and secrets onto the settings singleton."""
    config = _loads(row.config)
    if row.provider == "microsoft":
        await _hydrate_microsoft(session, settings, row, config)
    elif row.provider == "gcp":
        settings.GCP_PROJECT_ID = config.get("project_id", settings.GCP_PROJECT_ID)
    elif row.provider == "google_workspace":
        settings.GOOGLE_WORKSPACE_CUSTOMER_ID = config.get("customer_id", settings.GOOGLE_WORKSPACE_CUSTOMER_ID)


async def _hydrate_microsoft(session: AsyncSession, settings: Any, row: Any, config: dict[str, Any]) -> None:
    """Microsoft credentials live on `Settings`, including the certificate pair."""
    settings.ENTRA_TENANT_ID = row.account or settings.ENTRA_TENANT_ID
    settings.ENTRA_CLIENT_ID = config.get("client_id") or settings.ENTRA_CLIENT_ID
    if config.get("auth_method") == "certificate":
        certificate_pem = await _stored_secret(session, "microsoft", "certificate_pem")
        private_key = await _stored_secret(session, "microsoft", "private_key_pem")
        if certificate_pem and private_key:
            settings.ENTRA_CLIENT_CERTIFICATE = certificate_pem
            settings.ENTRA_CLIENT_PRIVATE_KEY = private_key
            settings.ENTRA_CLIENT_SECRET = ""
        return
    secret = await _stored_secret(session, "microsoft", "client_secret")
    if secret:
        settings.ENTRA_CLIENT_SECRET = secret
