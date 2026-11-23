"""Zero Trust assessment worker task.

A full assessment (Microsoft's own module can take hours) must not block the API, so
this task owns the run. On an install without a Celery broker ``worker.inline.dispatch``
runs the same coroutine as a background asyncio task.
"""

from __future__ import annotations

import asyncio

from celery.utils.log import get_task_logger

from unimonitor.worker.celery_app import celery_app
from unimonitor.zerotrust.runner import run_assessment_now

logger = get_task_logger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    name="unimonitor.worker.tasks.zerotrust.run_zt_assessment_task",
    queue="assessment",
)
def run_zt_assessment_task(
    self,
    tenant_id: str,
    platform: str,
    user_id: str | None = None,
    engine: str = "python",
) -> dict:
    """Run one platform's Zero Trust assessment and write its report."""
    logger.info("Zero Trust assessment started", extra={"tenant_id": tenant_id, "platform": platform})
    return _run_async(run_assessment_now(tenant_id=tenant_id, platform=platform, user_id=user_id, engine=engine))


__all__ = ["run_zt_assessment_task"]
