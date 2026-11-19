"""The in-process fallback that makes collection work without a Celery worker."""

from __future__ import annotations

import asyncio

import pytest

from unimonitor.worker.inline import dispatch


class _NoBroker:
    """Stands in for a task whose broker refuses the connection."""

    name = "unimonitor.worker.tasks.assessment.run_assessment_task"

    def delay(self, **_kwargs):
        raise ConnectionError("redis://localhost:6379/1 unreachable")


@pytest.mark.asyncio
async def test_dispatch_runs_in_process_when_the_broker_is_down():
    seen: list[str] = []

    async def job(run_id: str) -> dict:
        seen.append(run_id)
        return {"run_id": run_id}

    task_id = dispatch(_NoBroker(), job, run_id="run-1")
    await asyncio.sleep(0.6)  # the inline job waits for the caller to commit

    assert task_id == "inline:run-1"
    assert seen == ["run-1"]


@pytest.mark.asyncio
async def test_dispatch_keeps_celery_when_it_accepts_the_task():
    class _Broker:
        name = "task"

        def delay(self, **_kwargs):
            class _Result:
                id = "celery-1"

            return _Result()

    async def job(**_kwargs):
        raise AssertionError("the in-process job must not start")

    assert dispatch(_Broker(), job, run_id="run-2") == "celery-1"
