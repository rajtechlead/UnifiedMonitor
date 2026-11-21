"""Notification settings and delivery management API."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.auth.dependencies import get_current_user, require_role
from unimonitor.core.logging import get_logger
from unimonitor.db.base import get_session
from unimonitor.db.models.tenant import Tenant
from unimonitor.db.models.user import User

logger = get_logger(__name__)
router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────


class SmtpSettings(BaseModel):
    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""  # write-only; returned as masked
    from_address: str = ""
    use_tls: bool = True
    enabled: bool = False


class TeamsSettings(BaseModel):
    webhook_url: str = ""
    enabled: bool = False
    send_on_critical: bool = True
    send_on_high: bool = True
    send_on_medium: bool = False
    digest_mode: bool = False


class SlackSettings(BaseModel):
    webhook_url: str = ""
    channel: str = "#security-alerts"
    enabled: bool = False
    send_on_critical: bool = True
    send_on_high: bool = True
    send_on_medium: bool = False
    digest_mode: bool = False


class WebhookSettings(BaseModel):
    url: str = ""
    secret: str = ""
    enabled: bool = False
    headers: dict[str, str] = {}


class AlertThresholds(BaseModel):
    new_critical_finding: bool = True
    new_high_finding: bool = True
    new_medium_finding: bool = False
    score_drop_threshold: float = 10.0  # alert if score drops by this much
    collection_failure: bool = True
    assessment_complete: bool = False


class NotificationSettings(BaseModel):
    tenant_id: str
    smtp: SmtpSettings = SmtpSettings()
    teams: TeamsSettings = TeamsSettings()
    slack: SlackSettings = SlackSettings()
    generic_webhook: WebhookSettings = WebhookSettings()
    thresholds: AlertThresholds = AlertThresholds()
    # Scheduled digest
    daily_digest_enabled: bool = False
    daily_digest_time: str = "08:00"  # HH:MM UTC
    weekly_digest_enabled: bool = False
    weekly_digest_day: str = "Monday"


class NotificationSettingsUpdate(BaseModel):
    smtp: SmtpSettings | None = None
    teams: TeamsSettings | None = None
    slack: SlackSettings | None = None
    generic_webhook: WebhookSettings | None = None
    thresholds: AlertThresholds | None = None
    daily_digest_enabled: bool | None = None
    daily_digest_time: str | None = None
    weekly_digest_enabled: bool | None = None
    weekly_digest_day: str | None = None


class TestNotificationRequest(BaseModel):
    channel: str  # "email" | "teams" | "slack" | "webhook"
    recipient: str | None = None  # email address for SMTP test


class TestNotificationResponse(BaseModel):
    channel: str
    success: bool
    message: str


# ── Helper: load/persist settings via tenant JSON column ──────────────────


async def _get_tenant(tenant_id: str, db: AsyncSession) -> Tenant:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def _mask(value: str) -> str:
    if not value:
        return ""
    return value[:4] + "***" if len(value) > 4 else "***"


_CHANNEL_SECRET_FIELDS = {
    "smtp": "password",
    "teams": "webhook_url",
    "slack": "webhook_url",
    "generic_webhook": "secret",
}


def _merge_channel(raw: dict[str, Any], channel_name: str, update_model: BaseModel) -> None:
    """Merge one channel's update, keeping the stored secret when it comes back masked."""
    merged = update_model.model_dump()
    secret_field = _CHANNEL_SECRET_FIELDS[channel_name]
    if str(merged.get(secret_field, "")).endswith("***"):
        merged[secret_field] = (raw.get(channel_name) or {}).get(secret_field, "")
    raw[channel_name] = merged


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.get(
    "/settings",
    summary="Get notification settings for a tenant",
    responses={404: {"description": "Tenant not found"}},
)
async def get_notification_settings(
    tenant_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> NotificationSettings:
    """Return notification settings for a tenant (secrets masked)."""
    tenant = await _get_tenant(tenant_id, db)

    raw: dict[str, Any] = {}
    if hasattr(tenant, "notification_settings") and tenant.notification_settings:
        try:
            raw = json.loads(tenant.notification_settings)
        except (json.JSONDecodeError, TypeError):
            raw = {}

    settings = NotificationSettings(tenant_id=tenant_id)

    # Apply stored values
    if "smtp" in raw:
        s = raw["smtp"]
        settings.smtp = SmtpSettings(
            host=s.get("host", ""),
            port=s.get("port", 587),
            username=s.get("username", ""),
            password=_mask(s.get("password", "")),
            from_address=s.get("from_address", ""),
            use_tls=s.get("use_tls", True),
            enabled=s.get("enabled", False),
        )
    if "teams" in raw:
        t = raw["teams"]
        settings.teams = TeamsSettings(
            webhook_url=_mask(t.get("webhook_url", "")),
            enabled=t.get("enabled", False),
            send_on_critical=t.get("send_on_critical", True),
            send_on_high=t.get("send_on_high", True),
            send_on_medium=t.get("send_on_medium", False),
            digest_mode=t.get("digest_mode", False),
        )
    if "slack" in raw:
        s = raw["slack"]
        settings.slack = SlackSettings(
            webhook_url=_mask(s.get("webhook_url", "")),
            channel=s.get("channel", "#security-alerts"),
            enabled=s.get("enabled", False),
            send_on_critical=s.get("send_on_critical", True),
            send_on_high=s.get("send_on_high", True),
            send_on_medium=s.get("send_on_medium", False),
            digest_mode=s.get("digest_mode", False),
        )
    if "thresholds" in raw:
        settings.thresholds = AlertThresholds(**raw["thresholds"])
    if "daily_digest_enabled" in raw:
        settings.daily_digest_enabled = raw["daily_digest_enabled"]
    if "daily_digest_time" in raw:
        settings.daily_digest_time = raw["daily_digest_time"]
    if "weekly_digest_enabled" in raw:
        settings.weekly_digest_enabled = raw["weekly_digest_enabled"]
    if "weekly_digest_day" in raw:
        settings.weekly_digest_day = raw["weekly_digest_day"]

    return settings


@router.put(
    "/settings",
    summary="Update notification settings for a tenant",
    responses={404: {"description": "Tenant not found"}},
)
async def update_notification_settings(
    tenant_id: str,
    update: NotificationSettingsUpdate,
    current_user: Annotated[User, Depends(require_role("analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> NotificationSettings:
    """Persist notification settings for a tenant."""
    tenant = await _get_tenant(tenant_id, db)

    # Load existing
    try:
        raw: dict[str, Any] = json.loads(tenant.notification_settings or "{}")
    except (json.JSONDecodeError, TypeError):
        raw = {}

    # Merge updates. A masked secret ("******") echoed back keeps its stored value.
    for channel_name, update_model in (
        ("smtp", update.smtp),
        ("teams", update.teams),
        ("slack", update.slack),
        ("generic_webhook", update.generic_webhook),
    ):
        if update_model is not None:
            _merge_channel(raw, channel_name, update_model)

    if update.thresholds is not None:
        raw["thresholds"] = update.thresholds.model_dump()
    for field_name in ("daily_digest_enabled", "daily_digest_time", "weekly_digest_enabled", "weekly_digest_day"):
        value = getattr(update, field_name)
        if value is not None:
            raw[field_name] = value

    if not hasattr(tenant, "notification_settings"):
        # Store as metadata on tenant record if column exists
        pass
    else:
        tenant.notification_settings = json.dumps(raw)
        await db.commit()

    logger.info("Notification settings updated", tenant_id=tenant_id, user_id=str(current_user.id))

    # Return the sanitised view
    return await get_notification_settings(tenant_id=tenant_id, current_user=current_user, db=db)


async def _teams_test(raw: dict[str, Any], tenant: Tenant, current_user: User) -> TestNotificationResponse:
    webhook_url = raw.get("teams", {}).get("webhook_url", "")
    if not webhook_url:
        return TestNotificationResponse(channel="teams", success=False, message="Teams webhook URL not configured")
    import httpx

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            webhook_url,
            json={
                "@type": "MessageCard",
                "@context": "https://schema.org/extensions",
                "summary": "UniMonitor Test Notification",
                "themeColor": "0078D4",
                "title": "UniMonitor — Test Notification",
                "text": f"Test notification from UniMonitor for tenant **{tenant.name}**. Sent by {current_user.email}.",
            },
        )
    if resp.is_success:
        return TestNotificationResponse(channel="teams", success=True, message="Teams notification sent successfully")
    return TestNotificationResponse(channel="teams", success=False, message=f"Teams returned HTTP {resp.status_code}")


async def _slack_test(raw: dict[str, Any], tenant: Tenant, current_user: User) -> TestNotificationResponse:
    webhook_url = raw.get("slack", {}).get("webhook_url", "")
    if not webhook_url:
        return TestNotificationResponse(channel="slack", success=False, message="Slack webhook URL not configured")
    import httpx

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            webhook_url,
            json={
                "text": f":white_check_mark: UniMonitor test notification for tenant *{tenant.name}*. Sent by {current_user.email}.",
            },
        )
    if resp.is_success:
        return TestNotificationResponse(channel="slack", success=True, message="Slack notification sent successfully")
    return TestNotificationResponse(channel="slack", success=False, message=f"Slack returned HTTP {resp.status_code}")


def _email_test(
    raw: dict[str, Any],
    tenant: Tenant,
    current_user: User,
    request: TestNotificationRequest,
) -> TestNotificationResponse:
    smtp_cfg = raw.get("smtp", {})
    if not smtp_cfg.get("enabled") or not smtp_cfg.get("host"):
        return TestNotificationResponse(channel="email", success=False, message="SMTP not configured or disabled")
    recipient = request.recipient or current_user.email
    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText(f"Test notification from UniMonitor.\n\nTenant: {tenant.name}\nSent by: {current_user.email}")
    msg["Subject"] = "UniMonitor — Test Notification"
    msg["From"] = smtp_cfg.get("from_address", smtp_cfg.get("username", ""))
    msg["To"] = recipient
    with smtplib.SMTP(smtp_cfg["host"], smtp_cfg.get("port", 587)) as s:
        if smtp_cfg.get("use_tls", True):
            s.starttls()
        if smtp_cfg.get("username") and smtp_cfg.get("password"):
            s.login(smtp_cfg["username"], smtp_cfg["password"])
        s.send_message(msg)
    return TestNotificationResponse(channel="email", success=True, message=f"Email sent to {recipient}")


async def _webhook_test(
    raw: dict[str, Any],
    current_user: User,
    test_payload: dict[str, Any],
) -> TestNotificationResponse:
    wh_cfg = raw.get("generic_webhook", {})
    if not wh_cfg.get("enabled") or not wh_cfg.get("url"):
        return TestNotificationResponse(channel="webhook", success=False, message="Webhook not configured or disabled")
    import hashlib
    import hmac

    import httpx

    headers = {**wh_cfg.get("headers", {}), "Content-Type": "application/json"}
    if wh_cfg.get("secret"):
        body = json.dumps(test_payload).encode()
        sig = hmac.new(wh_cfg["secret"].encode(), body, hashlib.sha256).hexdigest()
        headers["X-UniMonitor-Signature"] = f"sha256={sig}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(wh_cfg["url"], json=test_payload, headers=headers)
    if resp.is_success:
        return TestNotificationResponse(channel="webhook", success=True, message="Webhook delivered successfully")
    return TestNotificationResponse(channel="webhook", success=False, message=f"Webhook returned HTTP {resp.status_code}")


@router.post(
    "/test",
    summary="Send a test notification",
    responses={
        400: {"description": "Unknown channel"},
        404: {"description": "Tenant not found"},
    },
)
async def test_notification(
    tenant_id: str,
    request: TestNotificationRequest,
    current_user: Annotated[User, Depends(require_role("analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> TestNotificationResponse:
    """Send a test notification via the specified channel."""
    tenant = await _get_tenant(tenant_id, db)

    try:
        raw: dict[str, Any] = json.loads(tenant.notification_settings or "{}")
    except (json.JSONDecodeError, TypeError):
        raw = {}

    channel = request.channel
    if channel not in ("email", "teams", "slack", "webhook"):
        raise HTTPException(status_code=400, detail=f"Unknown channel: {channel}")

    test_payload = {
        "type": "test",
        "message": "This is a test notification from UniMonitor.",
        "tenant": tenant.name,
        "sent_by": current_user.email,
    }

    try:
        if channel == "teams":
            return await _teams_test(raw, tenant, current_user)
        if channel == "slack":
            return await _slack_test(raw, tenant, current_user)
        if channel == "email":
            return _email_test(raw, tenant, current_user, request)
        return await _webhook_test(raw, current_user, test_payload)
    except Exception as exc:
        logger.error("Test notification failed", channel=channel, error=str(exc))
        return TestNotificationResponse(channel=channel, success=False, message=f"Error: {str(exc)[:200]}")
