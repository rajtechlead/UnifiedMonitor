"""Assessment-related Celery tasks."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

from celery import shared_task
from celery.utils.log import get_task_logger

from unimonitor.worker.celery_app import celery_app

logger = get_task_logger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    name="unimonitor.worker.tasks.assessment.run_assessment_task",
    max_retries=1,
    default_retry_delay=60,
    queue="assessments",
)
def run_assessment_task(
    self,
    run_id: str,
    tenant_id: str,
    assessment_id: str,
    frameworks: list[str],
    collectors: list[str] | None = None,
    triggered_by: str | None = None,
) -> dict:
    """Run a full assessment for a tenant."""
    logger.info(
        "Assessment task started",
        extra={"run_id": run_id, "tenant_id": tenant_id, "task_id": self.request.id},
    )

    async def _run():
        from unimonitor.db.base import async_session_factory
        from unimonitor.db.models.assessment import AssessmentRun
        from unimonitor.db.models.tenant import Tenant
        from unimonitor.grc.engine import AssessmentEngine
        from sqlalchemy import select

        async with async_session_factory() as db:
            # Load run and tenant
            result = await db.execute(select(AssessmentRun).where(AssessmentRun.id == run_id))
            run = result.scalar_one_or_none()
            if not run:
                raise ValueError(f"AssessmentRun {run_id} not found")

            result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")

            # Update task ID on run
            run.task_id = self.request.id
            await db.commit()

            engine = AssessmentEngine(
                db=db,
                tenant_id=tenant_id,
                entra_tenant_id=tenant.entra_tenant_id,
                client_id=tenant.client_id,
                client_secret=tenant.client_secret,
            )
            completed_run = await engine.run(
                run=run,
                frameworks=frameworks,
                collectors=collectors,
            )
            return {
                "run_id": completed_run.id,
                "status": completed_run.status,
                "security_score": completed_run.security_score,
                "compliance_score": completed_run.compliance_score,
                "total_findings": completed_run.critical_count + completed_run.high_count,
            }

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error("Assessment task failed", extra={"run_id": run_id, "error": str(exc)})
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"run_id": run_id, "status": "failed", "error": str(exc)[:500]}


@celery_app.task(
    name="unimonitor.worker.tasks.assessment.run_scheduled_assessments",
    queue="assessments",
)
def run_scheduled_assessments() -> dict:
    """Trigger assessment runs for all active tenants on schedule."""
    logger.info("Running scheduled assessments")

    async def _run():
        from unimonitor.db.base import async_session_factory
        from unimonitor.db.models.tenant import Tenant
        from unimonitor.db.models.assessment import Assessment, AssessmentRun, AssessmentStatus
        from sqlalchemy import select
        import uuid

        triggered = 0
        async with async_session_factory() as db:
            result = await db.execute(
                select(Assessment)
                .join(Tenant)
                .where(Tenant.is_active == True, Assessment.is_active == True)
            )
            assessments = result.scalars().all()

            for assessment in assessments:
                # Create a new run
                run = AssessmentRun(
                    id=str(uuid.uuid4()),
                    assessment_id=assessment.id,
                    trigger="scheduled",
                    status=AssessmentStatus.PENDING.value,
                )
                db.add(run)
                await db.flush()

                # Queue the task
                run_assessment_task.delay(
                    run_id=run.id,
                    tenant_id=assessment.tenant_id,
                    assessment_id=assessment.id,
                    frameworks=assessment.framework_list(),
                    collectors=assessment.collector_list() or None,
                )
                triggered += 1

            await db.commit()
        return {"triggered": triggered}

    result = _run_async(_run())
    logger.info("Scheduled assessments triggered", extra={"count": result.get("triggered", 0)})
    return result


@celery_app.task(
    name="unimonitor.worker.tasks.assessment.run_single_collector_task",
    queue="assessments",
)
def run_single_collector_task(
    tenant_id: str,
    collector_name: str,
    triggered_by: str | None = None,
) -> dict:
    """Run a single collector for a tenant."""
    logger.info("Single collector task", extra={"tenant_id": tenant_id, "collector": collector_name})

    async def _run():
        from unimonitor.db.base import async_session_factory
        from unimonitor.db.models.tenant import Tenant
        from unimonitor.graph.collector_registry import CollectorRegistry
        from sqlalchemy import select

        async with async_session_factory() as db:
            result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")

            registry = CollectorRegistry(
                tenant_id=tenant.entra_tenant_id,
                client_id=tenant.client_id,
                client_secret=tenant.client_secret,
            )
            data = await registry.collect_all([collector_name])
            return {"collector": collector_name, "keys_collected": len(data)}

    return _run_async(_run())


@celery_app.task(
    name="unimonitor.worker.tasks.assessment.cleanup_old_runs",
    queue="maintenance",
)
def cleanup_old_runs(retention_days: int = 90) -> dict:
    """Delete assessment runs older than retention_days."""
    logger.info("Cleaning up old assessment runs", extra={"retention_days": retention_days})

    async def _run():
        from unimonitor.db.base import async_session_factory
        from unimonitor.db.models.assessment import AssessmentRun
        from sqlalchemy import select, delete

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        async with async_session_factory() as db:
            stmt = delete(AssessmentRun).where(AssessmentRun.started_at < cutoff)
            result = await db.execute(stmt)
            await db.commit()
            return {"deleted_runs": result.rowcount}

    return _run_async(_run())
