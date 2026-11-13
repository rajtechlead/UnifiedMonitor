"""Notification Celery tasks — digests and finding alerts."""

from __future__ import annotations

import asyncio

from celery.utils.log import get_task_logger

from unimonitor.worker.celery_app import celery_app

logger = get_task_logger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="unimonitor.worker.tasks.notifications.send_daily_digests",
    queue="notifications",
)
def send_daily_digests() -> dict:
    """Send daily security digest to all tenants with notifications enabled."""
    logger.info("Sending daily digests")

    async def _run():
        from sqlalchemy import select

        from unimonitor.db.base import async_session_factory
        from unimonitor.db.models.notification_setting import NotificationSetting
        from unimonitor.db.models.tenant import Tenant
        from unimonitor.notifications.dispatcher import NotificationDispatcher

        sent = 0
        failed = 0
        async with async_session_factory() as db:
            result = await db.execute(select(NotificationSetting).join(Tenant).where(Tenant.is_active, NotificationSetting.daily_digest))
            settings_list = result.scalars().all()

            for settings in settings_list:
                try:
                    dispatcher = NotificationDispatcher(db=db, tenant_id=settings.tenant_id)
                    await dispatcher.send_daily_digest(settings=settings)
                    sent += 1
                except Exception as exc:
                    logger.error(
                        "Daily digest failed",
                        tenant_id=settings.tenant_id,
                        error=str(exc),
                    )
                    failed += 1

        return {"sent": sent, "failed": failed}

    return _run_async(_run())


@celery_app.task(
    name="unimonitor.worker.tasks.notifications.send_weekly_digests",
    queue="notifications",
)
def send_weekly_digests() -> dict:
    """Send weekly security digest."""
    logger.info("Sending weekly digests")

    async def _run():
        from sqlalchemy import select

        from unimonitor.db.base import async_session_factory
        from unimonitor.db.models.notification_setting import NotificationSetting
        from unimonitor.db.models.tenant import Tenant
        from unimonitor.notifications.dispatcher import NotificationDispatcher

        sent = 0
        failed = 0
        async with async_session_factory() as db:
            result = await db.execute(select(NotificationSetting).join(Tenant).where(Tenant.is_active, NotificationSetting.weekly_digest))
            settings_list = result.scalars().all()

            for settings in settings_list:
                try:
                    dispatcher = NotificationDispatcher(db=db, tenant_id=settings.tenant_id)
                    await dispatcher.send_weekly_digest(settings=settings)
                    sent += 1
                except Exception as exc:
                    logger.error(
                        "Weekly digest failed",
                        tenant_id=settings.tenant_id,
                        error=str(exc),
                    )
                    failed += 1

        return {"sent": sent, "failed": failed}

    return _run_async(_run())


@celery_app.task(
    name="unimonitor.worker.tasks.notifications.dispatch_finding_alert",
    queue="notifications",
)
def dispatch_finding_alert(
    finding_id: str,
    tenant_id: str,
    severity: str,
) -> dict:
    """Dispatch an immediate alert for a critical/high finding."""

    async def _run():
        from sqlalchemy import select

        from unimonitor.db.base import async_session_factory
        from unimonitor.db.models.finding import Finding
        from unimonitor.db.models.notification_setting import NotificationSetting
        from unimonitor.notifications.dispatcher import NotificationDispatcher

        async with async_session_factory() as db:
            result = await db.execute(select(Finding).where(Finding.id == finding_id))
            finding = result.scalar_one_or_none()
            if not finding:
                return {"status": "skipped", "reason": "finding not found"}

            result = await db.execute(select(NotificationSetting).where(NotificationSetting.tenant_id == tenant_id))
            settings = result.scalar_one_or_none()
            if not settings or not settings.immediate_alerts:
                return {"status": "skipped", "reason": "alerts disabled"}

            # Only alert if severity meets threshold
            threshold_map = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
            if threshold_map.get(severity, 0) < threshold_map.get(settings.alert_severity_threshold, 3):
                return {"status": "skipped", "reason": "below threshold"}

            dispatcher = NotificationDispatcher(db=db, tenant_id=tenant_id)
            await dispatcher.send_finding_alert(finding=finding, settings=settings)
            return {"status": "sent", "finding_id": finding_id}

    return _run_async(_run())
