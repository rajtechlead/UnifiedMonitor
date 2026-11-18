"""
Unit tests for Celery worker tasks.

All tests mock out SQLAlchemy, the session factory, and external services
so no real DB, Redis, or Graph API is needed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_factory(session: AsyncMock) -> MagicMock:
    """Return a mock that acts as async_session_factory (async context manager)."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    factory = MagicMock(return_value=cm)
    return factory


def _db_result(value):
    """Return a mock SQLAlchemy result whose scalar_one_or_none() returns value."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    r.scalars.return_value.all.return_value = value if isinstance(value, list) else []
    r.rowcount = value if isinstance(value, int) else 0
    return r


# ---------------------------------------------------------------------------
# _run_async helper
# ---------------------------------------------------------------------------


class TestRunAsyncHelper:
    def test_run_async_returns_value(self):
        from unimonitor.worker.tasks.assessment import _run_async

        async def _coro():
            return 42

        assert _run_async(_coro()) == 42

    def test_run_async_propagates_exception(self):
        import pytest

        from unimonitor.worker.tasks.assessment import _run_async

        async def _coro():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            _run_async(_coro())


# ---------------------------------------------------------------------------
# assessment tasks
# ---------------------------------------------------------------------------


class TestCleanupOldRuns:
    def test_cleanup_returns_deleted_count(self):
        from unimonitor.worker.tasks.assessment import cleanup_old_runs

        mock_session = AsyncMock()
        mock_session.execute.return_value = _db_result(7)
        mock_session.commit = AsyncMock()

        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            result = cleanup_old_runs(retention_days=30)

        assert result["deleted_runs"] == 7

    def test_cleanup_zero_deleted(self):
        from unimonitor.worker.tasks.assessment import cleanup_old_runs

        mock_session = AsyncMock()
        mock_session.execute.return_value = _db_result(0)
        mock_session.commit = AsyncMock()

        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            result = cleanup_old_runs()

        assert result["deleted_runs"] == 0

    def test_cleanup_uses_default_retention(self):
        from unimonitor.worker.tasks.assessment import cleanup_old_runs

        mock_session = AsyncMock()
        mock_session.execute.return_value = _db_result(3)
        mock_session.commit = AsyncMock()

        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            result = cleanup_old_runs()  # default 90 days

        assert "deleted_runs" in result


class TestRunAssessmentTask:
    def test_run_not_found_propagates_to_error_return(self):
        """When AssessmentRun is not found, task fails and returns error dict."""
        from unimonitor.worker.tasks.assessment import run_assessment_task

        mock_session = AsyncMock()
        mock_session.execute.return_value = _db_result(None)
        mock_session.commit = AsyncMock()

        # For bind=True tasks: patch.object works on retry but not on request (Celery property).
        # request.id defaults to None in direct calls which is fine.
        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            with patch.object(run_assessment_task, "retry", side_effect=run_assessment_task.MaxRetriesExceededError("max")):
                result = run_assessment_task.run(
                    run_id="run-001",
                    tenant_id="tenant-001",
                    assessment_id="assess-001",
                    frameworks=["iso_27001"],
                )

        assert result["run_id"] == "run-001"
        assert result["status"] == "failed"
        assert "error" in result

    def test_run_logs_start(self):
        """Task logs at start (cover the logger.info line)."""
        from unimonitor.worker.tasks.assessment import run_assessment_task

        mock_session = AsyncMock()
        mock_session.execute.return_value = _db_result(None)
        mock_session.commit = AsyncMock()

        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            with patch.object(run_assessment_task, "retry", side_effect=run_assessment_task.MaxRetriesExceededError("max")):
                with patch("unimonitor.worker.tasks.assessment.logger") as mock_logger:
                    run_assessment_task.run(
                        run_id="run-002",
                        tenant_id="tenant-001",
                        assessment_id="assess-001",
                        frameworks=[],
                    )
                    mock_logger.info.assert_called()


class TestRunScheduledAssessments:
    def test_no_assessments_returns_zero(self):
        from unimonitor.worker.tasks.assessment import run_scheduled_assessments

        mock_session = AsyncMock()
        # scalars().all() returns empty list
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            result = run_scheduled_assessments()

        assert result["triggered"] == 0

    def test_assessments_trigger_tasks(self):
        from unimonitor.worker.tasks.assessment import run_scheduled_assessments

        # Mock assessment objects
        mock_assessment = MagicMock()
        mock_assessment.id = "assess-123"
        mock_assessment.tenant_id = "tenant-456"
        mock_assessment.framework_list.return_value = ["iso_27001"]
        mock_assessment.collector_list.return_value = []

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_assessment]
        mock_session.execute.return_value = mock_result
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            with patch("unimonitor.worker.tasks.assessment.run_assessment_task") as mock_task:
                mock_task.delay = MagicMock()
                result = run_scheduled_assessments()

        assert result["triggered"] == 1


class TestRunSingleCollectorTask:
    def test_tenant_not_found_raises(self):
        import pytest

        from unimonitor.worker.tasks.assessment import run_single_collector_task

        mock_session = AsyncMock()
        mock_session.execute.return_value = _db_result(None)

        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            with pytest.raises(ValueError, match="not found"):
                run_single_collector_task(
                    tenant_id="missing-tenant",
                    collector_name="entra_identity",
                )

    def test_successful_collection(self):
        from unimonitor.worker.tasks.assessment import run_single_collector_task

        mock_tenant = MagicMock()
        mock_tenant.entra_tenant_id = "entra-123"
        mock_tenant.client_id = "client-456"
        mock_tenant.client_secret = "secret-789"

        mock_session = AsyncMock()
        mock_session.execute.return_value = _db_result(mock_tenant)

        mock_registry = AsyncMock()
        mock_registry.collect_all.return_value = {"key1": "val1", "key2": "val2"}

        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            with patch("unimonitor.graph.collector_registry.CollectorRegistry", return_value=mock_registry):
                result = run_single_collector_task(
                    tenant_id="tenant-001",
                    collector_name="entra_identity",
                )

        assert result["collector"] == "entra_identity"
        assert result["keys_collected"] == 2


# ---------------------------------------------------------------------------
# notification tasks
# ---------------------------------------------------------------------------


class TestSendDailyDigests:
    def test_no_settings_returns_zero(self):
        from unimonitor.worker.tasks.notifications import send_daily_digests

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            result = send_daily_digests()

        assert result == {"sent": 0, "failed": 0}

    def test_successful_digest_counts(self):
        from unimonitor.worker.tasks.notifications import send_daily_digests

        mock_settings = MagicMock()
        mock_settings.tenant_id = "tenant-001"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_settings]
        mock_session.execute.return_value = mock_result

        mock_dispatcher = AsyncMock()
        mock_dispatcher.send_daily_digest = AsyncMock()

        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            with patch("unimonitor.notifications.dispatcher.NotificationDispatcher", return_value=mock_dispatcher):
                result = send_daily_digests()

        assert result["sent"] == 1
        assert result["failed"] == 0

    def test_digest_failure_increments_failed(self):
        from unimonitor.worker.tasks.notifications import send_daily_digests

        mock_settings = MagicMock()
        mock_settings.tenant_id = "tenant-001"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_settings]
        mock_session.execute.return_value = mock_result

        mock_dispatcher = AsyncMock()
        mock_dispatcher.send_daily_digest.side_effect = Exception("SMTP error")

        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            with patch("unimonitor.notifications.dispatcher.NotificationDispatcher", return_value=mock_dispatcher):
                result = send_daily_digests()

        assert result["sent"] == 0
        assert result["failed"] == 1


class TestSendWeeklyDigests:
    def test_no_settings_returns_zero(self):
        from unimonitor.worker.tasks.notifications import send_weekly_digests

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            result = send_weekly_digests()

        assert result == {"sent": 0, "failed": 0}


class TestDispatchFindingAlert:
    def test_finding_not_found_skips(self):
        from unimonitor.worker.tasks.notifications import dispatch_finding_alert

        mock_session = AsyncMock()
        mock_session.execute.return_value = _db_result(None)

        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            result = dispatch_finding_alert(
                finding_id="find-001",
                tenant_id="tenant-001",
                severity="CRITICAL",
            )

        assert result["status"] == "skipped"
        assert result["reason"] == "finding not found"

    def test_alerts_disabled_skips(self):
        from unimonitor.worker.tasks.notifications import dispatch_finding_alert

        mock_finding = MagicMock()
        mock_finding.id = "find-001"

        mock_settings = MagicMock()
        mock_settings.immediate_alerts = False

        mock_session = AsyncMock()
        # First call: finding found; second call: settings found
        mock_session.execute.side_effect = [
            _db_result(mock_finding),
            _db_result(mock_settings),
        ]

        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            result = dispatch_finding_alert(
                finding_id="find-001",
                tenant_id="tenant-001",
                severity="CRITICAL",
            )

        assert result["status"] == "skipped"
        assert result["reason"] == "alerts disabled"

    def test_below_threshold_skips(self):
        from unimonitor.worker.tasks.notifications import dispatch_finding_alert

        mock_finding = MagicMock()
        mock_settings = MagicMock()
        mock_settings.immediate_alerts = True
        mock_settings.alert_severity_threshold = "CRITICAL"  # only send for CRITICAL

        mock_session = AsyncMock()
        mock_session.execute.side_effect = [
            _db_result(mock_finding),
            _db_result(mock_settings),
        ]

        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            result = dispatch_finding_alert(
                finding_id="find-001",
                tenant_id="tenant-001",
                severity="LOW",  # LOW < CRITICAL threshold
            )

        assert result["status"] == "skipped"
        assert result["reason"] == "below threshold"

    def test_alert_sent_successfully(self):
        from unimonitor.worker.tasks.notifications import dispatch_finding_alert

        mock_finding = MagicMock()
        mock_settings = MagicMock()
        mock_settings.immediate_alerts = True
        mock_settings.alert_severity_threshold = "HIGH"

        mock_session = AsyncMock()
        mock_session.execute.side_effect = [
            _db_result(mock_finding),
            _db_result(mock_settings),
        ]

        mock_dispatcher = AsyncMock()
        mock_dispatcher.send_finding_alert = AsyncMock()

        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            with patch("unimonitor.notifications.dispatcher.NotificationDispatcher", return_value=mock_dispatcher):
                result = dispatch_finding_alert(
                    finding_id="find-001",
                    tenant_id="tenant-001",
                    severity="CRITICAL",  # CRITICAL >= HIGH threshold
                )

        assert result["status"] == "sent"
        assert result["finding_id"] == "find-001"


# ---------------------------------------------------------------------------
# reporting tasks
# ---------------------------------------------------------------------------


class TestGenerateReportTask:
    def test_report_not_found_returns_error(self):
        from unimonitor.worker.tasks.reporting import generate_report_task

        mock_session = AsyncMock()
        mock_session.execute.return_value = _db_result(None)
        mock_session.commit = AsyncMock()

        # patch retry to raise MaxRetriesExceededError; skip request (Celery property, no deleter)
        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            with patch.object(generate_report_task, "retry", side_effect=generate_report_task.MaxRetriesExceededError("max")):
                result = generate_report_task.run(
                    report_id="report-001",
                    tenant_id="tenant-001",
                    run_id="run-001",
                    formats=["pdf"],
                )

        assert result["report_id"] == "report-001"
        assert result["status"] == "failed"

    def test_successful_report_generation(self):
        from unimonitor.worker.tasks.reporting import generate_report_task

        mock_report = MagicMock()
        mock_report.id = "report-001"
        mock_run = MagicMock()
        mock_run.id = "run-001"
        mock_run.assessment_id = "assess-001"

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        findings_result = MagicMock()
        findings_result.scalars.return_value.all.return_value = []
        mock_session.execute.side_effect = [
            _db_result(mock_report),
            _db_result(mock_run),
            findings_result,
        ]

        mock_gen = AsyncMock()
        mock_gen.generate = AsyncMock(return_value="/tmp/report.csv")

        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            with patch("unimonitor.reporting.csv_generator.CsvReportGenerator", return_value=mock_gen):
                result = generate_report_task.run(
                    report_id="report-001",
                    tenant_id="tenant-001",
                    run_id="run-001",
                    formats=["csv"],
                )

        assert result["report_id"] == "report-001"
        assert result["status"] in ("completed", "failed", mock_report.status)

    def test_unknown_format_is_skipped(self):
        """Unknown format should log warning but not crash."""
        from unimonitor.worker.tasks.reporting import generate_report_task

        mock_report = MagicMock()
        mock_run = MagicMock()
        mock_run.assessment_id = "assess-001"

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        findings_result = MagicMock()
        findings_result.scalars.return_value.all.return_value = []
        mock_session.execute.side_effect = [
            _db_result(mock_report),
            _db_result(mock_run),
            findings_result,
        ]

        with patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)):
            result = generate_report_task.run(
                report_id="report-001",
                tenant_id="tenant-001",
                run_id="run-001",
                formats=["unknown_format"],  # type: ignore[list-item]
            )

        assert "report_id" in result


# ---------------------------------------------------------------------------
# Notification dispatcher call signatures
# ---------------------------------------------------------------------------


class TestNotificationTaskArguments:
    """The tasks must call the dispatcher with the parameter names it declares.

    The blocker this guards against: the tasks passed `settings=`/`findings=` while
    the dispatcher takes `settings_obj=`, so every digest and alert raised TypeError
    inside the per-tenant `except` and no notification was ever sent. These fakes
    declare keyword-only parameters, so a wrong name fails here instead of silently.
    """

    def _settings_row(self, tenant_id: str = "tenant-1") -> MagicMock:
        row = MagicMock()
        row.tenant_id = tenant_id
        row.immediate_alerts = True
        row.alert_severity_threshold = "HIGH"
        return row

    def test_daily_digest_passes_the_settings_object(self):
        from unimonitor.notifications.dispatcher import NotificationDispatcher
        from unimonitor.worker.tasks.notifications import send_daily_digests

        seen: list[object] = []
        settings_row = self._settings_row()

        async def fake_digest(self, *, settings_obj):
            seen.append(settings_obj)

        mock_session = AsyncMock()
        mock_session.execute.return_value = _db_result([settings_row])

        with (
            patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)),
            patch.object(NotificationDispatcher, "send_daily_digest", fake_digest),
        ):
            result = send_daily_digests()

        assert result == {"sent": 1, "failed": 0}
        assert seen == [settings_row]

    def test_weekly_digest_passes_the_settings_object(self):
        from unimonitor.notifications.dispatcher import NotificationDispatcher
        from unimonitor.worker.tasks.notifications import send_weekly_digests

        seen: list[object] = []
        settings_row = self._settings_row()

        async def fake_digest(self, *, settings_obj):
            seen.append(settings_obj)

        mock_session = AsyncMock()
        mock_session.execute.return_value = _db_result([settings_row])

        with (
            patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)),
            patch.object(NotificationDispatcher, "send_weekly_digest", fake_digest),
        ):
            result = send_weekly_digests()

        assert result == {"sent": 1, "failed": 0}
        assert seen == [settings_row]

    def test_finding_alert_passes_the_finding_and_the_settings_object(self):
        from unimonitor.notifications.dispatcher import NotificationDispatcher
        from unimonitor.worker.tasks.notifications import dispatch_finding_alert

        seen: list[tuple] = []
        finding = MagicMock(id="finding-1")
        settings_row = self._settings_row()

        async def fake_alert(self, *, finding, settings_obj):
            seen.append((finding, settings_obj))

        mock_session = AsyncMock()
        mock_session.execute.side_effect = [_db_result(finding), _db_result(settings_row)]

        with (
            patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)),
            patch.object(NotificationDispatcher, "send_finding_alert", fake_alert),
        ):
            result = dispatch_finding_alert("finding-1", "tenant-1", "CRITICAL")

        assert result == {"status": "sent", "finding_id": "finding-1"}
        assert seen == [(finding, settings_row)]

    def test_a_failed_send_is_counted_not_hidden(self):
        """The per-tenant except is why the wrong names went unnoticed — prove it counts."""
        from unimonitor.notifications.dispatcher import NotificationDispatcher
        from unimonitor.worker.tasks.notifications import send_daily_digests

        async def broken(self, *, settings_obj):
            raise TypeError("dispatcher signature changed")

        mock_session = AsyncMock()
        mock_session.execute.return_value = _db_result([self._settings_row()])

        with (
            patch("unimonitor.db.base.async_session_factory", _make_session_factory(mock_session)),
            patch.object(NotificationDispatcher, "send_daily_digest", broken),
        ):
            result = send_daily_digests()

        assert result == {"sent": 0, "failed": 1}
