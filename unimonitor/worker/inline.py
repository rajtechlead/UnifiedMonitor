"""Run collection in the API process when no Celery worker is reachable.

The Windows installer starts a single process — no Redis broker, no worker and no beat
— so every ``.delay()`` raised and "Collect now" answered 503. Here the API runs the
same task body as a background asyncio task, and schedules automatic collection itself.
When a broker does answer, Celery keeps the work, so nothing runs twice.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from unimonitor.core.logging import get_logger
from unimonitor.worker.celery_app import celery_app

logger = get_logger(__name__)

# Hold a reference so the garbage collector cannot cancel a running collection.
_running: set[asyncio.Task[Any]] = set()


def broker_available() -> bool:
    """True when a Celery broker accepts a connection right now."""
    try:
        with celery_app.connection_for_write() as connection:
            connection.ensure_connection(max_retries=0)
        return True
    except Exception:  # noqa: BLE001 - any failure means "no worker here"
        return False


async def _fail_run(run_id: str, exc: Exception) -> None:
    """Record an in-process failure, so a run never stays "pending" forever."""
    from datetime import UTC, datetime

    from unimonitor.db.base import async_session_factory
    from unimonitor.db.models.assessment import AssessmentRun

    try:
        async with async_session_factory() as session:
            run = await session.get(AssessmentRun, run_id)
            if run is not None and run.status in ("pending", "running"):
                run.status = "failed"
                run.error_message = str(exc)[:2000]
                run.completed_at = datetime.now(UTC)
                await session.commit()
    except Exception as mark_exc:  # noqa: BLE001 - the original failure is what matters
        logger.error("Could not record failed in-process run", run_id=run_id, error=str(mark_exc)[:300])


async def _run_later(job: Callable[..., Coroutine[Any, Any, Any]], kwargs: dict[str, Any]) -> None:
    # The caller commits its run row first; the short pause keeps a snapshot of it
    # visible before the job opens its own session and looks the row up.
    await asyncio.sleep(0.5)
    try:
        await job(**kwargs)
    except Exception as exc:  # noqa: BLE001 - a background task must not fail silently
        logger.error("In-process job failed", job=job.__name__, error=str(exc)[:500])
        run_id = kwargs.get("run_id")
        if run_id:
            await _fail_run(str(run_id), exc)


def dispatch(task: Any, job: Callable[..., Coroutine[Any, Any, Any]], /, **kwargs: Any) -> str:
    """Queue ``job`` on Celery, or start it in this process when no broker answers."""
    try:
        return str(task.delay(**kwargs).id)
    except Exception as exc:  # noqa: BLE001 - a broker-less install is supported
        logger.warning("No Celery worker; running in-process", task=task.name, error=str(exc)[:200])
    running = asyncio.create_task(_run_later(job, kwargs))
    _running.add(running)
    running.add_done_callback(_running.discard)
    return f"inline:{kwargs.get('run_id') or kwargs.get('collector_name') or 'job'}"


async def collect_periodically(
    interval_minutes: int,
    collect: Callable[[], Coroutine[Any, Any, Any]],
    *,
    initial_delay_seconds: int = 0,
) -> None:
    """Run ``collect`` every interval — the broker-less beat schedule.

    The first run waits ``initial_delay_seconds`` so a fresh start serves the setup and
    dashboard pages before a full tenant collection competes with them.
    """
    if initial_delay_seconds > 0:
        await asyncio.sleep(initial_delay_seconds)
    while True:
        try:
            await collect()
        except Exception as exc:  # noqa: BLE001 - one bad run must not stop the loop
            logger.error("In-process collection failed", error=str(exc)[:300])
        await asyncio.sleep(max(60, interval_minutes * 60))
