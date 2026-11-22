"""Deployment settings that are safe to edit from the UI.

The posture snapshot is a JSON document merged into collected data for keys that
no Graph endpoint exposes. Its path is deployment configuration
(``UNIMONITOR_POSTURE_SNAPSHOT``); this endpoint lets an administrator maintain
the document without shell access, and refuses to create a path that was not
configured.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.auth.dependencies import get_current_user, require_role
from unimonitor.config import get_settings
from unimonitor.db.models.tenant import Tenant
from unimonitor.db.session import get_db
from unimonitor.graph.collectors.snapshot import load_snapshot

logger = structlog.get_logger(__name__)
router = APIRouter()

MAX_SNAPSHOT_BYTES = 256 * 1024


class PostureSnapshotResponse(BaseModel):
    configured: bool
    path: str
    snapshot: dict[str, Any]


BRANDING_KEY = "branding"


class Branding(BaseModel):
    """Per-tenant white-label settings, stored in ``Tenant.settings_json``."""

    portal_name: str = Field(default="UniMonitor", min_length=1, max_length=64)
    accent_colour: str = Field(default="#2563EB", pattern=r"^#[0-9A-Fa-f]{6}$")
    logo_url: str | None = Field(default=None, max_length=512)
    support_email: str | None = Field(default=None, max_length=254)

    @field_validator("logo_url")
    @classmethod
    def _safe_logo(cls, value: str | None) -> str | None:
        """Only https or site-relative URLs — never a javascript:/data: URL."""
        if value and not value.startswith(("https://", "/")):
            raise ValueError("logo_url must be an https:// URL or a site-relative path")
        return value

    @field_validator("support_email")
    @classmethod
    def _email_shape(cls, value: str | None) -> str | None:
        if value and ("@" not in value or any(char.isspace() for char in value)):
            raise ValueError("support_email must be an email address")
        return value


def _tenant_settings(tenant: Tenant) -> dict[str, Any]:
    try:
        data = json.loads(tenant.settings_json or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _branding_from(tenant: Tenant | None) -> Branding:
    if tenant is None:
        return Branding()
    raw = _tenant_settings(tenant).get(BRANDING_KEY)
    if not isinstance(raw, dict):
        return Branding()
    try:
        return Branding(**raw)
    except ValidationError:
        # A hand-edited settings blob must not break every page that renders the brand.
        logger.warning("branding_invalid", tenant_id=tenant.id)
        return Branding()


@router.get("/branding", responses={401: {"description": "Not authenticated"}})
async def get_branding(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Branding:
    """The caller's tenant branding (defaults when nothing is configured)."""
    tenant = await db.get(Tenant, current_user.tenant_id) if current_user.tenant_id else None
    return _branding_from(tenant)


@router.put(
    "/branding",
    responses={
        400: {"description": "The user has no tenant to brand"},
        401: {"description": "Not authenticated"},
        404: {"description": "Tenant not found"},
        422: {"description": "Invalid branding value"},
    },
)
async def put_branding(
    body: Branding,
    current_user: Annotated[Any, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Branding:
    """Update portal name, accent colour, logo and support address for the tenant."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="This account is not attached to a tenant")
    tenant = await db.get(Tenant, current_user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    settings = _tenant_settings(tenant)
    settings[BRANDING_KEY] = body.model_dump()
    tenant.settings_json = json.dumps(settings, sort_keys=True)
    await db.flush()
    logger.info("branding_updated", tenant_id=tenant.id, by=current_user.id)
    return body


NOTIFICATIONS_KEY = "notifications"
MASK = "******"
SMTP_VAULT_KEY_TEMPLATE = "unimonitor-tenant-{tenant_id}-smtp-credential"


class NotificationPreferences(BaseModel):
    """The flat notification shape the Settings page edits.

    Stored in ``Tenant.settings_json`` so no schema change is needed; the SMTP
    password is write-only from the client's point of view and is masked on read.
    """

    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_to_emails: list[str] = Field(default_factory=list)
    teams_webhook_url: str = ""
    slack_webhook_url: str = ""
    immediate_alerts: bool = True
    daily_digest: bool = False
    weekly_digest: bool = True
    alert_severity_threshold: str = "HIGH"


def _mask(secret: str) -> str:
    return MASK if secret else ""


def _smtp_secret_name(tenant_id: str) -> str:
    """Vault entry holding one tenant's SMTP password."""
    return SMTP_VAULT_KEY_TEMPLATE.format(tenant_id=tenant_id)


async def _read_smtp_password(tenant: Tenant | None) -> str:
    """The stored SMTP password from the secret provider; empty when unset."""
    if tenant is None:
        return ""
    from unimonitor.secrets import get_secret_resolver

    resolver = await get_secret_resolver()
    try:
        return await resolver.get(_smtp_secret_name(tenant.id))
    except KeyError:
        # One release wrote this password into the settings row; treat it as set
        # until the next save moves it into the provider.
        legacy = _tenant_settings(tenant).get(NOTIFICATIONS_KEY)
        if isinstance(legacy, dict) and legacy.get("smtp_password"):
            return str(legacy["smtp_password"])
        return ""


async def _store_smtp_password(tenant_id: str, value: str) -> None:
    """Write or clear the SMTP password in the secret provider."""
    from unimonitor.secrets import get_secret_resolver

    resolver = await get_secret_resolver()
    if value:
        await resolver.set(_smtp_secret_name(tenant_id), value, tags={"purpose": "smtp"})
        return
    try:
        await resolver.delete(_smtp_secret_name(tenant_id))
    except KeyError:
        pass


def _notification_preferences(tenant: Tenant | None, password: str) -> NotificationPreferences:
    if tenant is None:
        return NotificationPreferences()
    raw = _tenant_settings(tenant).get(NOTIFICATIONS_KEY)
    if not isinstance(raw, dict):
        raw = {}
    try:
        prefs = NotificationPreferences(**raw)
    except ValidationError:
        logger.warning("notification_settings_invalid", tenant_id=tenant.id)
        prefs = NotificationPreferences()
    prefs.smtp_password = _mask(password)
    return prefs


@router.get("/notifications", responses={401: {"description": "Not authenticated"}})
async def get_notification_preferences(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationPreferences:
    """Notification channels for the caller's tenant (secrets masked)."""
    tenant = await db.get(Tenant, current_user.tenant_id) if current_user.tenant_id else None
    return _notification_preferences(tenant, await _read_smtp_password(tenant))


@router.put(
    "/notifications",
    responses={
        400: {"description": "The user has no tenant to configure"},
        401: {"description": "Not authenticated"},
        404: {"description": "Tenant not found"},
        422: {"description": "Invalid notification value"},
    },
)
async def put_notification_preferences(
    body: NotificationPreferences,
    current_user: Annotated[Any, Depends(require_role("analyst"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationPreferences:
    """Persist SMTP, webhook and digest preferences for the tenant."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="This account is not attached to a tenant")
    tenant = await db.get(Tenant, current_user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    payload = body.model_dump()
    incoming = payload.pop("smtp_password")
    stored_password = await _read_smtp_password(tenant)
    # The client round-trips the mask; keep the secret it stands for. An empty
    # value clears the stored password, and the settings row never holds it.
    if incoming == MASK:
        password = stored_password
    else:
        password = incoming
    await _store_smtp_password(tenant.id, password)

    settings = _tenant_settings(tenant)
    settings[NOTIFICATIONS_KEY] = payload
    tenant.settings_json = json.dumps(settings, sort_keys=True)
    await db.flush()
    logger.info("notification_settings_updated", tenant_id=tenant.id, by=current_user.id)

    body.smtp_password = _mask(password)
    return body


def _snapshot_path() -> Path | None:
    configured = str(getattr(get_settings(), "UNIMONITOR_POSTURE_SNAPSHOT", "") or "")
    return Path(configured) if configured else None


@router.get("/posture-snapshot")
async def get_posture_snapshot(
    current_user: Annotated[Any, Depends(require_role("admin"))],
) -> PostureSnapshotResponse:
    """Read the configured posture snapshot (empty when the path is unset)."""
    path = _snapshot_path()
    return PostureSnapshotResponse(
        configured=path is not None,
        path=str(path) if path else "",
        snapshot=load_snapshot(path),
    )


@router.put(
    "/posture-snapshot",
    responses={409: {"description": "Conflict"}, 413: {"description": "Payload too large"}, 500: {"description": "Internal error"}},
)
async def put_posture_snapshot(
    body: dict[str, Any],
    current_user: Annotated[Any, Depends(require_role("admin"))],
) -> PostureSnapshotResponse:
    """Replace the posture snapshot document atomically."""
    path = _snapshot_path()
    if path is None:
        raise HTTPException(
            status_code=409,
            detail="UNIMONITOR_POSTURE_SNAPSHOT is not configured; set it to a writable path first.",
        )
    encoded = json.dumps(body, indent=2, sort_keys=True)
    if len(encoded.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        raise HTTPException(status_code=413, detail=f"Posture snapshot exceeds {MAX_SNAPSHOT_BYTES} bytes")

    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(encoded, encoding="utf-8")
        temporary.replace(path)
    except OSError as exc:
        logger.warning("posture_snapshot_write_failed", path=str(path), error=str(exc))
        raise HTTPException(status_code=500, detail="Could not write the posture snapshot") from exc

    logger.info("posture_snapshot_updated", path=str(path), by=current_user.id, keys=len(body))
    return PostureSnapshotResponse(configured=True, path=str(path), snapshot=load_snapshot(path))
