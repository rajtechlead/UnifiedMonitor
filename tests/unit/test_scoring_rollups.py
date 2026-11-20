"""Additional calculate_scores / calculate_framework_coverage coverage.

The core finding-scoring cases live in ``test_scoring.py``; these are the run-level
roll-up branches that file does not exercise.
"""

from __future__ import annotations

from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(state, severity="MEDIUM", ctrl_id="C1", risk_score=5, suppressed=False):
    f = MagicMock()
    from unimonitor.db.models.finding import FindingSeverity, FindingState

    state_map = {
        "implemented": FindingState.IMPLEMENTED.value,
        "partially_implemented": FindingState.PARTIALLY_IMPLEMENTED.value,
        "not_implemented": FindingState.NOT_IMPLEMENTED.value,
        "not_applicable": FindingState.NOT_APPLICABLE.value,
    }
    sev_map = {
        "CRITICAL": FindingSeverity.CRITICAL.value,
        "HIGH": FindingSeverity.HIGH.value,
        "MEDIUM": FindingSeverity.MEDIUM.value,
        "LOW": FindingSeverity.LOW.value,
        "INFORMATIONAL": FindingSeverity.INFORMATIONAL.value,
    }
    f.state = state_map.get(state, state)
    f.severity = sev_map.get(severity.upper(), severity)
    f.external_control_id = ctrl_id
    f.risk_score = risk_score
    f.is_suppressed = suppressed
    return f


# ---------------------------------------------------------------------------
# calculate_scores (ORM-based, full function)
# ---------------------------------------------------------------------------


class TestCalculateScores:
    def test_empty_findings_returns_perfect_score(self):
        from unimonitor.grc.scoring import calculate_scores

        result = calculate_scores([])
        assert result["security_score"] == 100.0
        assert result["compliance_score"] == 100.0
        assert result["risk_score"] == 100.0
        assert result["critical_count"] == 0

    def test_all_implemented(self):
        from unimonitor.grc.scoring import calculate_scores

        findings = [
            _make_finding("implemented", "HIGH", risk_score=0),
            _make_finding("implemented", "MEDIUM", risk_score=0),
        ]
        result = calculate_scores(findings)
        assert result["security_score"] == 100.0

    def test_all_not_implemented_lowers_scores(self):
        from unimonitor.grc.scoring import calculate_scores

        findings = [
            _make_finding("not_implemented", "CRITICAL", risk_score=10),
            _make_finding("not_implemented", "HIGH", risk_score=8),
        ]
        result = calculate_scores(findings)
        assert result["security_score"] == 0.0
        assert result["critical_count"] == 1
        assert result["high_count"] == 1

    def test_mixed_state_produces_intermediate_score(self):
        from unimonitor.grc.scoring import calculate_scores

        findings = [
            _make_finding("implemented", "HIGH", risk_score=0),
            _make_finding("not_implemented", "HIGH", risk_score=8),
        ]
        result = calculate_scores(findings)
        assert 0 < result["security_score"] < 100

    def test_suppressed_findings_excluded(self):
        from unimonitor.grc.scoring import calculate_scores

        findings = [
            _make_finding("not_implemented", "CRITICAL", risk_score=10, suppressed=True),
            _make_finding("implemented", "HIGH", risk_score=0),
        ]
        # Only the implemented HIGH finding counts
        result = calculate_scores(findings)
        assert result["security_score"] == 100.0

    def test_not_applicable_excluded_from_compliance_credit(self):
        """NA findings are included in total_weight but excluded from compliance credit."""
        from unimonitor.grc.scoring import calculate_scores

        findings = [
            _make_finding("not_applicable", "HIGH", risk_score=0),
            _make_finding("implemented", "MEDIUM", risk_score=0),
        ]
        result = calculate_scores(findings)
        # Both findings contribute to total_weight; compliance credit only for MEDIUM implemented
        # security_score = 5/13 ≈ 38.46 (not_applicable does not contribute to passed_weight)
        assert result["security_score"] < 100.0

    def test_partially_implemented_not_in_security_score(self):
        """calculate_scores only counts fully IMPLEMENTED for security_score."""
        from unimonitor.grc.scoring import calculate_scores

        findings = [
            _make_finding("partially_implemented", "HIGH", risk_score=4),
            _make_finding("not_implemented", "HIGH", risk_score=8),
        ]
        result = calculate_scores(findings)
        # Neither is fully implemented → 0% security_score
        assert result["security_score"] == 0.0

    def test_severity_counts_only_non_implemented(self):
        from unimonitor.grc.scoring import calculate_scores

        findings = [
            _make_finding("not_implemented", "CRITICAL", risk_score=10),
            _make_finding("implemented", "CRITICAL", risk_score=0),
            _make_finding("not_implemented", "LOW", risk_score=3),
        ]
        result = calculate_scores(findings)
        assert result["critical_count"] == 1  # only non-implemented
        assert result["low_count"] == 1


# ---------------------------------------------------------------------------
# calculate_framework_coverage
# ---------------------------------------------------------------------------


class TestCalculateFrameworkCoverage:
    def test_empty_framework_returns_zero(self):
        from unimonitor.grc.scoring import calculate_framework_coverage

        result = calculate_framework_coverage([], [])
        assert result["coverage_percent"] == 0.0
        assert result["total"] == 0

    def test_all_implemented(self):
        from unimonitor.grc.scoring import calculate_framework_coverage

        findings = [
            _make_finding("implemented", ctrl_id="C1"),
            _make_finding("implemented", ctrl_id="C2"),
        ]
        result = calculate_framework_coverage(findings, ["C1", "C2"])
        assert result["coverage_percent"] == 100.0
        assert result["implemented"] == 2

    def test_missing_finding_counts_as_not_implemented(self):
        from unimonitor.grc.scoring import calculate_framework_coverage

        findings = [_make_finding("implemented", ctrl_id="C1")]
        result = calculate_framework_coverage(findings, ["C1", "C2"])
        assert result["not_implemented"] == 1
        assert result["implemented"] == 1

    def test_not_applicable_excluded_from_total(self):
        from unimonitor.grc.scoring import calculate_framework_coverage

        findings = [
            _make_finding("not_applicable", ctrl_id="C1"),
            _make_finding("implemented", ctrl_id="C2"),
        ]
        result = calculate_framework_coverage(findings, ["C1", "C2"])
        # C1 excluded from denominator → total=1, 100% coverage
        assert result["coverage_percent"] == 100.0

    def test_partial_gives_half_coverage(self):
        from unimonitor.grc.scoring import calculate_framework_coverage

        findings = [
            _make_finding("partially_implemented", ctrl_id="C1"),
            _make_finding("not_implemented", ctrl_id="C2"),
        ]
        result = calculate_framework_coverage(findings, ["C1", "C2"])
        # 0.5/2 = 25%
        assert result["coverage_percent"] == 25.0

    def test_all_not_applicable_returns_100(self):
        from unimonitor.grc.scoring import calculate_framework_coverage

        findings = [_make_finding("not_applicable", ctrl_id="C1")]
        result = calculate_framework_coverage(findings, ["C1"])
        assert result["coverage_percent"] == 100.0


# ---------------------------------------------------------------------------
# FrameworkCrosswalk (class-based)
# ---------------------------------------------------------------------------


def _make_ctrl(ctrl_id, compliance_mapping):
    ctrl = MagicMock()
    ctrl.id = ctrl_id
    ctrl.compliance_mapping = compliance_mapping
    return ctrl
