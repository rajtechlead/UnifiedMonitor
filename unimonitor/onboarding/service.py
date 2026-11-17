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
from unimonitor.onboarding import clouds, m365
from unimonitor.onboarding.google_auth import GCP_SCOPES, WORKSPACE_SCOPES, mint_access_token
from unimonitor.onboarding.permissions import MANUAL_FOLLOW_UP
from unimonitor.secrets.resolver import get_secret_resolver

logger = get_logger(__name__)

# What each platform asks for, in the order the wizard shows it. Secrets are listed
# under `secret_fields` so the UI can mask them and the service knows to vault them.
PLATFORM_FIELDS: dict[str, dict[str, list[dict[str, str]]]] = {
    "microsoft": {
        "config": [],
        "secrets": [],
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
        ],
        "secrets": [
            {"name": "access_key_id", "label": "Access key ID", "placeholder": "AKIA...", "required": "1"},
            {"name": "secret_access_key", "label": "Secret access key", "placeholder": "", "required": "1"},
            {"name": "session_token", "label": "Session token", "placeholder": "optional", "required": ""},
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
            },
            {"name": "access_token", "label": "— or an access token", "placeholder": "ya29...", "required": ""},
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
            },
            {"name": "access_token", "label": "— or an access token", "placeholder": "ya29...", "required": ""},
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
    for provider in PROVIDERS.values():
        fields = PLATFORM_FIELDS[provider.id]
        catalogue.append(
            {
                "id": provider.id,
                "name": provider.name,
                "short_name": provider.short_name,
                "description": provider.description,
                "colour": provider.colour,
                "automated": bool(fields.get("automated")),
                "config_fields": fields["config"],
                "secret_fields": fields["secrets"],
            }
        )
    return catalogue


async def first_tenant(session: AsyncSession) -> Tenant | None:
    return (await session.execute(select(Tenant).limit(1))).scalar_one_or_none()


async def has_admin(session: AsyncSession) -> bool:
    count = await session.scalar(select(func.count()).select_from(AppUser).where(AppUser.role == "admin"))
    return bool(count)


async def get_status(session: AsyncSession) -> dict[str, Any]:
    """Drive the first-run redirect and the setup checklist."""
    admin_exists = await has_admin(session)
    rows = list((await session.execute(select(CloudConnection))).scalars())
    connected = {row.provider: connection_dict(row) for row in rows}
    return {
        "needs_admin": not admin_exists,
        "configured": admin_exists and bool(connected),
        "connections": list(connected.values()),
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
    row.display_name = display_name or PROVIDERS[provider].name
    row.status = "connected"
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
    client_secret: str,
    tenant: str = "",
    display_name: str = "",
    granted: list[str] | None = None,
) -> CloudConnection:
    """Validate and save Microsoft 365 client credentials (automated or manual)."""
    name = await m365.verify_client_credentials(tenant or tenant_id, client_id, client_secret)
    return await upsert_connection(
        session,
        tenant_id=tenant_id,
        provider="microsoft",
        account=tenant or tenant_id,
        display_name=display_name or name,
        config={"client_id": client_id, "granted_permissions": granted or []},
        secrets={"client_secret": client_secret},
    )


async def connect_platform(session: AsyncSession, provider: str, payload: dict[str, Any]) -> CloudConnection:
    """Validate a platform's credentials, then persist the connection."""
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
        )

    if provider == "aws":
        region = str(payload.get("region") or get_settings().AWS_REGION or "us-east-1")
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
            config={"region": region},
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


async def _stored_secret(session: AsyncSession, provider: str, field: str) -> str:
    row = (await session.execute(select(CloudConnection).where(CloudConnection.provider == provider))).scalars().first()
    if row is None:
        return ""
    ref = _loads(row.secret_refs).get(field)
    if not ref:
        return ""
    try:
        return await (await get_secret_resolver()).get(ref)
    except KeyError:
        return ""


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
    rows = list((await session.execute(select(CloudConnection))).scalars())
    for row in rows:
        config = _loads(row.config)
        if row.provider == "microsoft":
            settings.ENTRA_TENANT_ID = row.account or settings.ENTRA_TENANT_ID
            settings.ENTRA_CLIENT_ID = config.get("client_id") or settings.ENTRA_CLIENT_ID
            secret = await _stored_secret(session, "microsoft", "client_secret")
            if secret:
                settings.ENTRA_CLIENT_SECRET = secret
        elif row.provider == "gcp":
            settings.GCP_PROJECT_ID = config.get("project_id", settings.GCP_PROJECT_ID)
        elif row.provider == "google_workspace":
            settings.GOOGLE_WORKSPACE_CUSTOMER_ID = config.get("customer_id", settings.GOOGLE_WORKSPACE_CUSTOMER_ID)
    logger.info("runtime configuration hydrated", connections=len(rows))
