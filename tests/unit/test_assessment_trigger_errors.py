"""A manual run that cannot start must report the real cause.

The trigger endpoint recorded ``status="failed"`` on the run and then answered
"queued successfully" with ``status="pending"``, so a run that never started looked
healthy. Worse, ``run_assessment_task`` was never exported from
``unimonitor.worker.tasks``, so the import in that handler raised on every call and
*every* manual run failed this way.

The endpoint commits before dispatching (the in-process job opens its own session),
which is not exercisable through the shared-transaction test client, so this drives
the handler with a mocked repository.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from unimonitor.api.v1.assessments import trigger_run

REPO = "unimonitor.db.repositories.assessment_repo.AssessmentRepository"


class _Assessment:
    tenant_id = "tenant-1"

    def framework_list(self):
        return ["mcsb"]

    def collector_list(self):
        return []


class _User:
    id = "user-1"


@pytest.mark.asyncio
async def test_a_failed_dispatch_reports_the_error_instead_of_success(monkeypatch):
    db = AsyncMock()
    update_run = AsyncMock()

    def _boom(*args, **kwargs):
        raise RuntimeError("no broker on this host")

    monkeypatch.setattr("unimonitor.worker.inline.dispatch", _boom)
    with (
        patch(f"{REPO}.get_by_id", AsyncMock(return_value=_Assessment())),
        patch(f"{REPO}.create_run", AsyncMock(return_value=SimpleNamespace(id="run-1"))),
        patch(f"{REPO}.update_run", update_run),
    ):
        result = await trigger_run("assessment-1", _User(), db)

    assert result.status == "failed"
    assert result.run_id == "run-1"
    assert "RuntimeError: no broker on this host" in result.message
    assert "queued successfully" not in result.message

    kwargs = update_run.await_args.kwargs
    assert kwargs["status"] == "failed"
    assert "RuntimeError: no broker on this host" in kwargs["error_message"]


@pytest.mark.asyncio
async def test_a_successful_dispatch_reports_pending(monkeypatch):
    db = AsyncMock()
    update_run = AsyncMock()
    monkeypatch.setattr("unimonitor.worker.inline.dispatch", lambda *a, **k: "task-123")
    with (
        patch(f"{REPO}.get_by_id", AsyncMock(return_value=_Assessment())),
        patch(f"{REPO}.create_run", AsyncMock(return_value=SimpleNamespace(id="run-2"))),
        patch(f"{REPO}.update_run", update_run),
    ):
        result = await trigger_run("assessment-1", _User(), db)

    assert result.status == "pending"
    assert result.task_id == "task-123"
    assert "queued successfully" in result.message


@pytest.mark.asyncio
async def test_the_worker_package_exports_the_task_the_handler_imports():
    """The missing re-export is what made every manual run fail."""
    from unimonitor.worker.tasks import run_assessment_task

    assert callable(run_assessment_task)
