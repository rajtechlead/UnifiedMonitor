"""Deployment settings that are safe to edit from the UI.

The posture snapshot is a JSON document merged into collected data for keys that
no Graph endpoint exposes. Its path is deployment configuration
(``UNIMONITOR_POSTURE_SNAPSHOT``); this endpoint lets an administrator maintain
the document without shell access, and refuses to create a path that was not
configured.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.auth.dependencies import get_current_user, require_role
from unimonitor.config import get_settings
from unimonitor.db.models.tenant import Tenant
from unimonitor.db.session import get_db
from unimonitor.graph.collectors.snapshot import load_snapshot
from unimonitor.notifications.preferences import NotificationPreferences
from unimonitor.notifications.preferences import load as load_notification_preferences
from unimonitor.notifications.preferences import save as save_notification_preferences

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
        from unimonitor.settings_validation import validate_logo_url

        return validate_logo_url(value)

    @field_validator("support_email")
    @classmethod
    def _email_shape(cls, value: str | None) -> str | None:
        from unimonitor.settings_validation import validate_support_email

        return validate_support_email(value)


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


async def _caller_tenant(current_user: Any, db: AsyncSession) -> Tenant | None:
    return await db.get(Tenant, current_user.tenant_id) if current_user.tenant_id else None


@router.get("/notifications", responses={401: {"description": "Not authenticated"}})
async def get_notification_preferences(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationPreferences:
    """Notification channels for the caller's tenant (credentials masked)."""
    return await load_notification_preferences(await _caller_tenant(current_user, db))


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
    tenant = await _caller_tenant(current_user, db)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Only the fields this request carries are replaced; a form that edits SMTP
    # must not clear the webhook credentials stored by the other API.
    current = await load_notification_preferences(tenant)
    for field in body.model_fields_set:
        setattr(current, field, getattr(body, field))
    updated = await save_notification_preferences(tenant, current)
    await db.flush()
    logger.info("notification_settings_updated", tenant_id=tenant.id, by=current_user.id)
    return updated


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


# ── Diagnostics bundle ───────────────────────────────────────

_REDACT_MARKERS = ("SECRET", "PASSWORD", "TOKEN", "API_KEY", "PRIVATE", "CREDENTIAL", "DATABASE_URL")


def _redact(value: Any) -> Any:
    """Hide anything that could be a credential without hiding its presence."""
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            sensitive = any(marker in str(key).upper() for marker in _REDACT_MARKERS)
            redacted[str(key)] = "<redacted>" if sensitive else _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


async def _diagnostics_manifest() -> dict[str, Any]:
    """Versions, counts and collector catalogue — no credentials, no finding text."""
    from sqlalchemy import func, select

    from unimonitor import __version__
    from unimonitor.db.base import async_session_factory
    from unimonitor.db.models.assessment import AssessmentRun
    from unimonitor.db.models.finding import Finding
    from unimonitor.db.models.tenant import Tenant
    from unimonitor.db.models.user import AppUser
    from unimonitor.graph.collector_registry import CollectorRegistry
    from unimonitor.grc.providers import PROVIDERS

    settings = get_settings()
    async with async_session_factory() as session:
        tenants = (await session.execute(select(func.count(Tenant.id)))).scalar_one()
        users = (await session.execute(select(func.count(AppUser.id)))).scalar_one()
        finding_counts = select(Finding.severity, Finding.state, func.count(Finding.id)).group_by(Finding.severity, Finding.state)
        findings = (await session.execute(finding_counts)).all()
        latest_run = (await session.execute(select(AssessmentRun).order_by(AssessmentRun.started_at.desc()).limit(1))).scalar_one_or_none()

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "application": {
            "name": "UniMonitor",
            "version": __version__,
            "environment": settings.UNIMONITOR_ENV,
            "python": __import__("sys").version.split()[0],
        },
        "inventory": {
            "tenants": tenants,
            "users": users,
            "findings": [{"severity": severity, "state": state, "count": count} for severity, state, count in findings],
            "latest_assessment": {
                "run_id": latest_run.id if latest_run else None,
                "status": latest_run.status if latest_run else None,
                "started_at": latest_run.started_at.isoformat() if latest_run and latest_run.started_at else None,
                "completed_at": latest_run.completed_at.isoformat() if latest_run and latest_run.completed_at else None,
                "error": (latest_run.error_message or "")[:500] if latest_run else None,
            },
        },
        "collectors": list(CollectorRegistry.ALL_COLLECTORS),
        "providers": [
            {
                "id": provider.id,
                "name": provider.name,
                "collectors": list(provider.collectors),
                "credential_settings": list(provider.credential_settings),
            }
            for provider in PROVIDERS.values()
        ],
        "configuration": _redact(settings.model_dump()),
        "posture": {
            "auto_inventory": bool(settings.POSTURE_AUTO_INVENTORY),
            "configured_snapshot": bool(settings.UNIMONITOR_POSTURE_SNAPSHOT),
        },
    }


@router.get(
    "/diagnostics",
    responses={401: {"description": "Not authenticated"}, 403: {"description": "Administrator role required"}},
)
async def diagnostics_bundle(
    current_user: Annotated[Any, Depends(require_role("admin"))],
) -> StreamingResponse:
    """Download a redacted support bundle: versions, counts, collectors and settings.

    Built in memory and never written to disk. Credential-shaped settings are
    replaced with ``<redacted>``; finding text and user details are not included.
    """
    manifest = await _diagnostics_manifest()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True, default=str))
        archive.writestr("README.txt", "UniMonitor diagnostics bundle\nAll values under configuration that look credential-shaped are redacted.\n")
    buffer.seek(0)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    logger.info("diagnostics_bundle_created", by=current_user.id)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="unimonitor-diagnostics-{stamp}.zip"'},
    )
