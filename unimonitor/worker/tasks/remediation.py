"""AI remediation tasks.

The finding's own row is the only thing read here; the engine anonymises it before
any provider sees it. Runs in-process when there is no broker (see
``unimonitor.worker.inline``).
"""

from __future__ import annotations

import asyncio
import json

from celery.utils.log import get_task_logger

from unimonitor.worker.celery_app import celery_app

logger = get_task_logger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def generate_ai_remediation_now(finding_id: str) -> dict:
    """Generate and store remediation guidance for one finding."""
    from sqlalchemy import select

    from unimonitor.db.base import async_session_factory
    from unimonitor.db.models.finding import Finding
    from unimonitor.db.models.tenant import Tenant
    from unimonitor.grc.ai_remediation import AIRemediationEngine

    async with async_session_factory() as db:
        finding = (await db.execute(select(Finding).where(Finding.id == finding_id))).scalar_one_or_none()
        if finding is None:
            raise ValueError(f"Finding {finding_id} not found")

        tenant = await db.get(Tenant, finding.tenant_id)
        result = await AIRemediationEngine().generate_remediation(finding, tenant=tenant)
        finding.ai_remediation = json.dumps(result)
        await db.commit()

    logger.info("ai_remediation_stored", finding_id=finding_id, source=result.get("source"))
    return {"finding_id": finding_id, "source": result.get("source")}


@celery_app.task(name="unimonitor.generate_ai_remediation")
def generate_ai_remediation_task(finding_id: str) -> dict:
    """Celery entry point."""
    return _run_async(generate_ai_remediation_now(finding_id))
