"""
Unit tests for unimonitor/grc/engine.py — AssessmentEngine.

All external dependencies (ControlLoader, CollectorRegistry, DB) are mocked.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_engine(db=None):
    from unimonitor.grc.engine import AssessmentEngine

    db = db or AsyncMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    return AssessmentEngine(
        db=db,
        tenant_id="tenant-001",
        entra_tenant_id="entra-001",
        client_id="client-001",
        client_secret="secret",
    ), db


def _make_control_def(
    ctrl_id="CC1.1",
    title="Test Control",
    severity="HIGH",
    service="identity",
    category="Access Control",
    result="implemented",
    compliance_mapping=None,
):
    """Build a minimal ControlDefinition-like mock."""
    ctrl = MagicMock()
    ctrl.id = ctrl_id
    ctrl.title = title
    ctrl.severity = severity
    ctrl.service = service
    ctrl.category = category
    ctrl.description = "Test description"
    ctrl.compliance_mapping = compliance_mapping or {"iso_27001": ["A.9.1"]}
    ctrl.run_evaluate = MagicMock(return_value=result)
    return ctrl


def _make_run(run_id="run-001"):
    run = MagicMock()
    run.id = run_id
    run.status = "pending"
    run.security_score = None
    run.compliance_score = None
    run.risk_score = None
    return run


# ---------------------------------------------------------------------------
# _evaluate_control — the core logic unit
# ---------------------------------------------------------------------------


class TestEvaluateControl:
    def test_implemented_state(self):
        engine, _ = _make_engine()
        ctrl = _make_control_def(result="implemented", severity="HIGH")
        finding = _run(engine._evaluate_control(ctrl, {}, "run-001"))
        from unimonitor.db.models.finding import FindingState

        assert finding.state == FindingState.IMPLEMENTED.value
        assert finding.risk_score == 0  # implemented → no risk

    def test_pass_maps_to_implemented(self):
        engine, _ = _make_engine()
        ctrl = _make_control_def(result="pass")
        finding = _run(engine._evaluate_control(ctrl, {}, "run-001"))
        from unimonitor.db.models.finding import FindingState

        assert finding.state == FindingState.IMPLEMENTED.value

    def test_not_implemented_state(self):
        engine, _ = _make_engine()
        ctrl = _make_control_def(result="not_implemented", severity="CRITICAL")
        finding = _run(engine._evaluate_control(ctrl, {}, "run-001"))
        from unimonitor.db.models.finding import FindingSeverity, FindingState

        assert finding.state == FindingState.NOT_IMPLEMENTED.value
        assert finding.severity == FindingSeverity.CRITICAL.value
        assert finding.risk_score == 10  # critical full risk

    def test_fail_maps_to_not_implemented(self):
        engine, _ = _make_engine()
        ctrl = _make_control_def(result="fail")
        finding = _run(engine._evaluate_control(ctrl, {}, "run-001"))
        from unimonitor.db.models.finding import FindingState

        assert finding.state == FindingState.NOT_IMPLEMENTED.value

    def test_partially_implemented_state(self):
        engine, _ = _make_engine()
        ctrl = _make_control_def(result="partially_implemented", severity="HIGH")
        finding = _run(engine._evaluate_control(ctrl, {}, "run-001"))
        from unimonitor.db.models.finding import FindingState

        assert finding.state == FindingState.PARTIALLY_IMPLEMENTED.value
        assert finding.risk_score == 4  # HIGH=8 // 2

    def test_warning_maps_to_partially_implemented(self):
        engine, _ = _make_engine()
        ctrl = _make_control_def(result="warning")
        finding = _run(engine._evaluate_control(ctrl, {}, "run-001"))
        from unimonitor.db.models.finding import FindingState

        assert finding.state == FindingState.PARTIALLY_IMPLEMENTED.value

    def test_not_applicable_state(self):
        engine, _ = _make_engine()
        ctrl = _make_control_def(result="not_applicable")
        finding = _run(engine._evaluate_control(ctrl, {}, "run-001"))
        from unimonitor.db.models.finding import FindingState

        assert finding.state == FindingState.NOT_APPLICABLE.value
        assert finding.risk_score == 0

    def test_unknown_result_defaults_to_not_implemented(self):
        engine, _ = _make_engine()
        ctrl = _make_control_def(result="something_weird")
        finding = _run(engine._evaluate_control(ctrl, {}, "run-001"))
        from unimonitor.db.models.finding import FindingState

        assert finding.state == FindingState.NOT_IMPLEMENTED.value

    def test_evaluate_exception_produces_not_implemented(self):
        engine, _ = _make_engine()
        ctrl = _make_control_def()
        ctrl.run_evaluate.side_effect = RuntimeError("boom")
        finding = _run(engine._evaluate_control(ctrl, {}, "run-001"))
        from unimonitor.db.models.finding import FindingState

        assert finding.state == FindingState.NOT_IMPLEMENTED.value
        # Evidence should capture the error
        assert finding.evidence is not None and len(finding.evidence) > 0
        assert "boom" in finding.evidence[0].content

    def test_severity_mapping_medium(self):
        engine, _ = _make_engine()
        ctrl = _make_control_def(result="not_implemented", severity="MEDIUM")
        finding = _run(engine._evaluate_control(ctrl, {}, "run-001"))
        from unimonitor.db.models.finding import FindingSeverity

        assert finding.severity == FindingSeverity.MEDIUM.value
        assert finding.risk_score == 5

    def test_severity_mapping_low(self):
        engine, _ = _make_engine()
        ctrl = _make_control_def(result="not_implemented", severity="LOW")
        finding = _run(engine._evaluate_control(ctrl, {}, "run-001"))
        assert finding.risk_score == 3

    def test_severity_mapping_informational(self):
        engine, _ = _make_engine()
        ctrl = _make_control_def(result="not_implemented", severity="INFORMATIONAL")
        finding = _run(engine._evaluate_control(ctrl, {}, "run-001"))
        assert finding.risk_score == 1

    def test_finding_fields_populated(self):
        engine, _ = _make_engine()
        ctrl = _make_control_def(ctrl_id="ISO.A.9.1", service="identity", category="Access Control")
        finding = _run(engine._evaluate_control(ctrl, {}, "run-123"))
        assert finding.external_control_id == "ISO.A.9.1"
        assert finding.tenant_id == "tenant-001"
        assert finding.assessment_run_id == "run-123"
        assert finding.service == "identity"
        assert finding.category == "Access Control"
        assert finding.title == "Test Control"


# ---------------------------------------------------------------------------
# run() — full assessment orchestration
# ---------------------------------------------------------------------------


class TestAssessmentEngineRun:
    def _mock_loader(self, controls):
        loader = MagicMock()
        loader.load_all.return_value = controls
        return loader

    def _mock_registry(self, data=None):
        reg = MagicMock()
        reg.collect_all = AsyncMock(return_value=data or {})
        return reg

    def test_run_completes_successfully(self):
        engine, db = _make_engine()
        run = _make_run()
        ctrl = _make_control_def(result="implemented")
        loader = self._mock_loader([ctrl])
        registry = self._mock_registry()

        with (
            patch("unimonitor.grc.engine.ControlLoader", return_value=loader),
            patch("unimonitor.grc.engine.CollectorRegistry", return_value=registry),
            patch(
                "unimonitor.grc.engine.calculate_scores",
                return_value={
                    "security_score": 85.0,
                    "compliance_score": 90.0,
                    "risk_score": 2.5,
                    "critical_count": 0,
                    "high_count": 0,
                    "medium_count": 0,
                    "low_count": 0,
                    "informational_count": 0,
                },
            ),
        ):
            result = _run(engine.run(run, frameworks=["iso_27001"]))

        assert result.status == "completed"
        assert result.security_score == 85.0
        db.commit.assert_called()

    def test_run_filters_by_framework(self):
        engine, db = _make_engine()
        run = _make_run()
        ctrl_match = _make_control_def(ctrl_id="ISO.1", compliance_mapping={"iso_27001": ["A.1"]})
        ctrl_other = _make_control_def(ctrl_id="SOC.1", compliance_mapping={"soc2": ["CC1.1"]})
        loader = self._mock_loader([ctrl_match, ctrl_other])
        registry = self._mock_registry()

        with (
            patch("unimonitor.grc.engine.ControlLoader", return_value=loader),
            patch("unimonitor.grc.engine.CollectorRegistry", return_value=registry),
            patch(
                "unimonitor.grc.engine.calculate_scores",
                return_value={
                    "security_score": 100.0,
                    "compliance_score": 100.0,
                    "risk_score": 0.0,
                    "critical_count": 0,
                    "high_count": 0,
                    "medium_count": 0,
                    "low_count": 0,
                    "informational_count": 0,
                },
            ),
        ):
            _run(engine.run(run, frameworks=["iso_27001"]))

        # Only the iso_27001 control should be evaluated
        assert ctrl_match.run_evaluate.called
        assert not ctrl_other.run_evaluate.called

    def test_run_no_framework_uses_all_controls(self):
        engine, db = _make_engine()
        run = _make_run()
        ctrls = [_make_control_def(ctrl_id=f"C{i}") for i in range(3)]
        loader = self._mock_loader(ctrls)
        registry = self._mock_registry()

        with (
            patch("unimonitor.grc.engine.ControlLoader", return_value=loader),
            patch("unimonitor.grc.engine.CollectorRegistry", return_value=registry),
            patch(
                "unimonitor.grc.engine.calculate_scores",
                return_value={
                    "security_score": 70.0,
                    "compliance_score": 70.0,
                    "risk_score": 3.0,
                    "critical_count": 0,
                    "high_count": 1,
                    "medium_count": 0,
                    "low_count": 0,
                    "informational_count": 0,
                },
            ),
        ):
            _run(engine.run(run, frameworks=[]))

        for c in ctrls:
            assert c.run_evaluate.called

    def test_run_with_progress_callback(self):
        engine, db = _make_engine()
        run = _make_run()
        ctrl = _make_control_def()
        loader = self._mock_loader([ctrl])
        registry = self._mock_registry()
        progress_calls = []

        async def progress(evaluated, total):
            progress_calls.append((evaluated, total))

        with (
            patch("unimonitor.grc.engine.ControlLoader", return_value=loader),
            patch("unimonitor.grc.engine.CollectorRegistry", return_value=registry),
            patch(
                "unimonitor.grc.engine.calculate_scores",
                return_value={
                    "security_score": 100.0,
                    "compliance_score": 100.0,
                    "risk_score": 0.0,
                    "critical_count": 0,
                    "high_count": 0,
                    "medium_count": 0,
                    "low_count": 0,
                    "informational_count": 0,
                },
            ),
        ):
            _run(engine.run(run, frameworks=[], progress_callback=progress))

        assert len(progress_calls) == 1
        assert progress_calls[0] == (1, 1)

    def test_run_control_error_does_not_abort_others(self):
        """A single control evaluation failure should not stop remaining controls."""
        engine, db = _make_engine()
        run = _make_run()
        ctrl_ok = _make_control_def(ctrl_id="C1", result="implemented")
        ctrl_bad = _make_control_def(ctrl_id="C2")
        ctrl_bad.run_evaluate.side_effect = RuntimeError("boom")
        loader = self._mock_loader([ctrl_ok, ctrl_bad])
        registry = self._mock_registry()

        with (
            patch("unimonitor.grc.engine.ControlLoader", return_value=loader),
            patch("unimonitor.grc.engine.CollectorRegistry", return_value=registry),
            patch(
                "unimonitor.grc.engine.calculate_scores",
                return_value={
                    "security_score": 50.0,
                    "compliance_score": 50.0,
                    "risk_score": 5.0,
                    "critical_count": 0,
                    "high_count": 1,
                    "medium_count": 0,
                    "low_count": 0,
                    "informational_count": 0,
                },
            ),
        ):
            result = _run(engine.run(run, frameworks=[]))

        assert result.status == "completed"
        assert result.total_controls_checked >= 1  # C1 counted

    def test_run_collector_failure_marks_run_failed(self):
        """If the collector raises, the run should be marked failed."""
        engine, db = _make_engine()
        run = _make_run()
        loader = self._mock_loader([])
        registry = self._mock_registry()
        registry.collect_all = AsyncMock(side_effect=RuntimeError("Graph API down"))

        with (
            patch("unimonitor.grc.engine.ControlLoader", return_value=loader),
            patch("unimonitor.grc.engine.CollectorRegistry", return_value=registry),
        ):
            with pytest.raises(RuntimeError, match="Graph API down"):
                _run(engine.run(run, frameworks=[]))

        assert run.status == "failed"
        assert "Graph API down" in run.error_message

    def test_run_framework_fallback_when_no_match(self):
        """If framework filter matches nothing, fall back to all controls."""
        engine, db = _make_engine()
        run = _make_run()
        ctrl = _make_control_def(ctrl_id="C1", compliance_mapping={"soc2": ["CC1.1"]})
        loader = self._mock_loader([ctrl])
        registry = self._mock_registry()

        with (
            patch("unimonitor.grc.engine.ControlLoader", return_value=loader),
            patch("unimonitor.grc.engine.CollectorRegistry", return_value=registry),
            patch(
                "unimonitor.grc.engine.calculate_scores",
                return_value={
                    "security_score": 100.0,
                    "compliance_score": 100.0,
                    "risk_score": 0.0,
                    "critical_count": 0,
                    "high_count": 0,
                    "medium_count": 0,
                    "low_count": 0,
                    "informational_count": 0,
                },
            ),
        ):
            _run(engine.run(run, frameworks=["nonexistent_fw"]))

        # Fallback: all controls should run
        assert ctrl.run_evaluate.called
