"""Report generation API: run-based request contract and worker dispatch."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _make_run(db_session, tenant) -> str:
    from unimonitor.db.models.assessment import Assessment, AssessmentRun

    assessment = Assessment(tenant_id=tenant.id, name="Quarterly Assessment")
    db_session.add(assessment)
    await db_session.flush()

    run = AssessmentRun(assessment_id=assessment.id, status="completed")
    db_session.add(run)
    await db_session.flush()
    return run.id


class TestGenerateReport:
    async def test_requires_run_id(self, client: AsyncClient, auth_headers: dict):
        r = await client.post("/api/v1/reports/generate", json={"formats": ["pdf"]}, headers=auth_headers)
        assert r.status_code == 400
        assert "run_id" in r.json()["detail"]

    async def test_unknown_run_404(self, client: AsyncClient, auth_headers: dict):
        r = await client.post(
            "/api/v1/reports/generate",
            json={"run_id": "does-not-exist", "formats": ["pdf"]},
            headers=auth_headers,
        )
        assert r.status_code == 404

    async def test_dispatch_passes_run_formats_and_tenant(self, client: AsyncClient, auth_headers: dict, db_session, tenant, monkeypatch):
        run_id = await _make_run(db_session, tenant)
        captured: dict = {}

        import unimonitor.worker.tasks as tasks

        class _Task:
            id = "task-abc123"

        def fake_delay(**kwargs):
            captured.update(kwargs)
            return _Task()

        monkeypatch.setattr(tasks.generate_report_task, "delay", fake_delay)

        r = await client.post(
            "/api/v1/reports/generate",
            json={"run_id": run_id, "formats": ["pdf", "docx"], "report_type": "board"},
            headers=auth_headers,
        )
        assert r.status_code == 202, r.text
        body = r.json()
        assert body["report_format"] == "pdf"
        assert body["task_id"] == "task-abc123"

        assert captured["run_id"] == run_id
        assert captured["formats"] == ["pdf", "docx"]
        assert captured["tenant_id"] == tenant.id
        assert captured["report_type"] == "board"

    async def test_legacy_single_format_still_accepted(self, client: AsyncClient, auth_headers: dict, tenant, monkeypatch):
        import unimonitor.worker.tasks as tasks

        captured: dict = {}

        class _Task:
            id = "task-legacy"

        monkeypatch.setattr(tasks.generate_report_task, "delay", lambda **kw: (captured.update(kw), _Task())[1])

        r = await client.post(
            "/api/v1/reports/generate",
            json={"run_id": "run-1", "tenant_id": tenant.id, "report_format": "json"},
            headers=auth_headers,
        )
        assert r.status_code == 202, r.text
        assert captured["formats"] == ["json"]

    async def test_broker_less_install_runs_the_report_in_process(self, client: AsyncClient, auth_headers: dict, tenant, monkeypatch):
        """No Celery broker must not fail the request: the inline worker runs it."""
        import unimonitor.worker.tasks as tasks

        def boom(**kwargs):
            raise RuntimeError("no broker")

        monkeypatch.setattr(tasks.generate_report_task, "delay", boom)

        r = await client.post(
            "/api/v1/reports/generate",
            json={"run_id": "run-1", "tenant_id": tenant.id},
            headers=auth_headers,
        )
        assert r.status_code == 202
        assert r.json()["status"] == "queued"
        assert str(r.json()["task_id"]).startswith("inline:")

    async def test_dispatch_failure_is_reported_not_silently_queued(self, client: AsyncClient, auth_headers: dict, tenant, monkeypatch):
        import unimonitor.worker.inline as inline

        def boom(*args, **kwargs):
            raise RuntimeError("no queue")

        monkeypatch.setattr(inline, "dispatch", boom)

        r = await client.post(
            "/api/v1/reports/generate",
            json={"run_id": "run-1", "tenant_id": tenant.id},
            headers=auth_headers,
        )
        assert r.status_code == 202
        assert r.json()["status"] == "failed"
        assert "queue" in r.json()["error_message"].lower()


class TestReportRuns:
    async def test_a_completed_run_appears_in_the_report_picker(self, client: AsyncClient, auth_headers: dict, _session_factory):
        """Regression: the picker read AssessmentRun.tenant_id/created_at, which do
        not exist, so the handler returned an empty list for every install.

        The route opens its own session, so the fixture data has to be committed —
        and removed again so the shared SQLite file stays clean.
        """
        from sqlalchemy import delete

        from unimonitor.db.models.assessment import Assessment, AssessmentRun
        from unimonitor.db.models.tenant import Tenant

        tenant_pk = "reports-picker-tenant-00000000001"
        assessment_id = "reports-picker-assessment-0000001"
        run_id = "reports-picker-run-00000000000001"
        try:
            async with _session_factory() as session:
                session.add(Tenant(id=tenant_pk, tenant_id="reports-picker", name="Picker Org"))
                session.add(Assessment(id=assessment_id, tenant_id=tenant_pk, name="Quarterly Assessment"))
                session.add(AssessmentRun(id=run_id, assessment_id=assessment_id, status="completed"))
                await session.commit()

            r = await client.get("/api/v1/reports/runs", headers=auth_headers)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["total"] >= 1
            row = next(item for item in body["items"] if item["run_id"] == run_id)
            assert row["tenant_id"] == tenant_pk
            assert row["assessment_name"] == "Quarterly Assessment"
            assert row["started_at"]
        finally:
            async with _session_factory() as session:
                await session.execute(delete(AssessmentRun).where(AssessmentRun.id == run_id))
                await session.execute(delete(Assessment).where(Assessment.id == assessment_id))
                await session.execute(delete(Tenant).where(Tenant.id == tenant_pk))
                # The shared SQLite connection means this commit also persisted the
                # flushed fixture tenant; remove it so the next fixture can insert it.
                await session.execute(delete(Tenant).where(Tenant.id == "test-tenant-id-00000000000001"))
                await session.commit()


class TestScorecardDownload:
    async def test_pdf_scorecard_for_stored_findings(self, client: AsyncClient, auth_headers: dict, db_session, tenant):
        """The PDF branch must return a real PDF, not an error the page hides."""
        from unimonitor.db.models.finding import Finding

        db_session.add(
            Finding(
                tenant_id=tenant.id,
                external_control_id="CTRL-ENT-001",
                title="Require MFA for all users",
                description="mfa",
                severity="critical",
                state="not_implemented",
                category="identity",
                service="entra_id",
                risk_score=10,
            )
        )
        await db_session.flush()

        r = await client.get("/api/v1/reports/scorecard", params={"fmt": "pdf"}, headers=auth_headers)

        assert r.status_code == 200, r.text
        assert r.content.startswith(b"%PDF-")
        assert r.headers["content-type"] == "application/pdf"

    async def test_unknown_scorecard_format_is_rejected(self, client: AsyncClient, auth_headers: dict):
        r = await client.get("/api/v1/reports/scorecard", params={"fmt": "exe"}, headers=auth_headers)
        assert r.status_code == 422
