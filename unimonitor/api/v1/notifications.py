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
from unimonitor.notifications.preferences import NotificationPreferences
from unimonitor.notifications.preferences import load as load_preferences
from unimonitor.notifications.preferences import save as save_preferences

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


def _nested(prefs, tenant_id: str) -> NotificationSettings:
    """Present the one stored document in the nested shape this API exposes."""
    return NotificationSettings(
        tenant_id=tenant_id,
        smtp=SmtpSettings(
            host=prefs.smtp_host,
            port=prefs.smtp_port,
            username=prefs.smtp_username,
            password=prefs.smtp_password,
            from_address=prefs.smtp_from_address or prefs.smtp_username,
            use_tls=prefs.smtp_use_tls,
            enabled=prefs.smtp_enabled,
        ),
        teams=TeamsSettings(webhook_url=prefs.teams_webhook_url, enabled=bool(prefs.teams_webhook_url)),
        slack=SlackSettings(webhook_url=prefs.slack_webhook_url, enabled=bool(prefs.slack_webhook_url)),
        generic_webhook=WebhookSettings(
            url=prefs.generic_webhook_url,
            secret=prefs.generic_webhook_secret,
            enabled=bool(prefs.generic_webhook_url),
        ),
        thresholds=AlertThresholds(**prefs.alert_thresholds) if prefs.alert_thresholds else AlertThresholds(),
        daily_digest_enabled=prefs.daily_digest,
        weekly_digest_enabled=prefs.weekly_digest,
    )


def _apply(prefs, update: NotificationSettingsUpdate):
    """Fold a nested update into the flat document, leaving untouched fields alone."""
    if update.smtp is not None:
        prefs.smtp_enabled = update.smtp.enabled
        prefs.smtp_host = update.smtp.host
        prefs.smtp_port = update.smtp.port
        prefs.smtp_username = update.smtp.username
        prefs.smtp_password = update.smtp.password
        prefs.smtp_from_address = update.smtp.from_address
        prefs.smtp_use_tls = update.smtp.use_tls
    if update.teams is not None:
        prefs.teams_webhook_url = update.teams.webhook_url
    if update.slack is not None:
        prefs.slack_webhook_url = update.slack.webhook_url
    if update.generic_webhook is not None:
        prefs.generic_webhook_url = update.generic_webhook.url
        prefs.generic_webhook_secret = update.generic_webhook.secret
    if update.thresholds is not None:
        prefs.alert_thresholds = update.thresholds.model_dump()
    if update.daily_digest_enabled is not None:
        prefs.daily_digest = update.daily_digest_enabled
    if update.weekly_digest_enabled is not None:
        prefs.weekly_digest = update.weekly_digest_enabled
    return prefs


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
    """Notification settings for a tenant, with every credential masked."""
    from unimonitor.auth.tenant_scope import resolve_tenant

    tenant = await _get_tenant(await resolve_tenant(db, current_user, tenant_id), db)
    return _nested(await load_preferences(tenant), tenant.id)


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
    """Persist notification settings in the shared document and secret provider."""
    from unimonitor.auth.tenant_scope import resolve_tenant

    tenant = await _get_tenant(await resolve_tenant(db, current_user, tenant_id), db)
    prefs = _apply(await load_preferences(tenant), update)
    saved = await save_preferences(tenant, prefs)
    await db.flush()
    logger.info("Notification settings updated", tenant_id=tenant.id, user_id=str(current_user.id))
    return _nested(saved, tenant.id)


async def _teams_test(prefs: NotificationPreferences, tenant: Tenant, current_user: User) -> TestNotificationResponse:
    webhook_url = prefs.teams_webhook_url
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


async def _slack_test(prefs: NotificationPreferences, tenant: Tenant, current_user: User) -> TestNotificationResponse:
    webhook_url = prefs.slack_webhook_url
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
    prefs: NotificationPreferences,
    tenant: Tenant,
    current_user: User,
    request: TestNotificationRequest,
) -> TestNotificationResponse:
    if not prefs.smtp_enabled or not prefs.smtp_host:
        return TestNotificationResponse(channel="email", success=False, message="SMTP not configured or disabled")
    recipient = request.recipient or current_user.email
    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText(f"Test notification from UniMonitor.\n\nTenant: {tenant.name}\nSent by: {current_user.email}")
    msg["Subject"] = "UniMonitor — Test Notification"
    msg["From"] = prefs.smtp_from_address or prefs.smtp_username
    msg["To"] = recipient
    with smtplib.SMTP(prefs.smtp_host, prefs.smtp_port) as s:
        if prefs.smtp_use_tls:
            s.starttls()
        if prefs.smtp_username and prefs.smtp_password:
            s.login(prefs.smtp_username, prefs.smtp_password)
        s.send_message(msg)
    return TestNotificationResponse(channel="email", success=True, message=f"Email sent to {recipient}")


async def _webhook_test(
    prefs: NotificationPreferences,
    test_payload: dict[str, Any],
) -> TestNotificationResponse:
    if not prefs.generic_webhook_url:
        return TestNotificationResponse(channel="webhook", success=False, message="Webhook not configured or disabled")
    import hashlib
    import hmac

    import httpx

    headers = {"Content-Type": "application/json"}
    if prefs.generic_webhook_secret:
        body = json.dumps(test_payload).encode()
        sig = hmac.new(prefs.generic_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        headers["X-UniMonitor-Signature"] = f"sha256={sig}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(prefs.generic_webhook_url, json=test_payload, headers=headers)
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
    from unimonitor.auth.tenant_scope import resolve_tenant

    tenant = await _get_tenant(await resolve_tenant(db, current_user, tenant_id), db)
    # Delivery needs the real credentials, not the masked view the GET returns.
    prefs = await load_preferences(tenant, reveal=True)

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
            return await _teams_test(prefs, tenant, current_user)
        if channel == "slack":
            return await _slack_test(prefs, tenant, current_user)
        if channel == "email":
            return _email_test(prefs, tenant, current_user, request)
        return await _webhook_test(prefs, test_payload)
    except Exception as exc:
        logger.error("Test notification failed", channel=channel, error=str(exc))
        return TestNotificationResponse(channel=channel, success=False, message=f"Error: {str(exc)[:200]}")
