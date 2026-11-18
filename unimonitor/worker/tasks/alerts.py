"""Alert policy evaluation task — runs on the beat schedule."""

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
    name="unimonitor.worker.tasks.alerts.evaluate_alert_policies",
    queue="notifications",
)
def evaluate_alert_policies() -> dict:
    """Evaluate every tenant's alert policies and notify on new alerts."""
    from unimonitor.alerts.engine import evaluate_all_tenants

    result = _run_async(evaluate_all_tenants())
    logger.info("Alert policies evaluated", extra=result)
    return result
