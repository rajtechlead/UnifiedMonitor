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


async def _run_later(job: Callable[..., Coroutine[Any, Any, Any]], kwargs: dict[str, Any]) -> None:
    # The caller has flushed its run row but not committed it yet; give the request time
    # to commit before the job opens its own session and looks the row up.
    await asyncio.sleep(0.5)
    await job(**kwargs)


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
