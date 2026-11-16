"""
Unit tests for grc/crosswalk.py and additional calculate_scores / calculate_framework_coverage
in grc/scoring.py that aren't yet covered by test_scoring.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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


class TestFrameworkCrosswalk:
    def test_find_by_reference_match(self):
        from unimonitor.grc.crosswalk import FrameworkCrosswalk

        ctrl = _make_ctrl("ISO.C1", {"iso_27001": ["A.9.1", "A.9.2"]})
        cw = FrameworkCrosswalk([ctrl])
        found = cw.find_by_reference("iso_27001", "A.9.1")
        assert len(found) == 1
        assert found[0].id == "ISO.C1"

    def test_find_by_reference_no_match(self):
        from unimonitor.grc.crosswalk import FrameworkCrosswalk

        ctrl = _make_ctrl("ISO.C1", {"iso_27001": ["A.9.1"]})
        cw = FrameworkCrosswalk([ctrl])
        found = cw.find_by_reference("iso_27001", "A.99.99")
        assert found == []

    def test_find_by_reference_unknown_framework(self):
        from unimonitor.grc.crosswalk import FrameworkCrosswalk

        ctrl = _make_ctrl("ISO.C1", {"iso_27001": ["A.9.1"]})
        cw = FrameworkCrosswalk([ctrl])
        found = cw.find_by_reference("soc2", "CC1.1")
        assert found == []

    def test_all_frameworks(self):
        from unimonitor.grc.crosswalk import FrameworkCrosswalk

        ctrl = _make_ctrl("C1", {"iso_27001": ["A.1"], "soc2": ["CC1"]})
        cw = FrameworkCrosswalk([ctrl])
        fws = cw.all_frameworks()
        assert "iso_27001" in fws
        assert "soc2" in fws

    def test_coverage_for_framework(self):
        from unimonitor.grc.crosswalk import FrameworkCrosswalk

        ctrl = _make_ctrl("C1", {"iso_27001": ["A.1", "A.2"]})
        cw = FrameworkCrosswalk([ctrl])
        coverage = cw.coverage_for_framework("iso_27001")
        assert "A.1" in coverage
        assert "A.2" in coverage

    def test_coverage_for_missing_framework(self):
        from unimonitor.grc.crosswalk import FrameworkCrosswalk

        ctrl = _make_ctrl("C1", {"iso_27001": ["A.1"]})
        cw = FrameworkCrosswalk([ctrl])
        coverage = cw.coverage_for_framework("nonexistent")
        assert coverage == {}

    def test_string_ref_handled(self):
        """compliance_mapping refs given as a plain string (not list) should work."""
        from unimonitor.grc.crosswalk import FrameworkCrosswalk

        ctrl = _make_ctrl("C1", {"iso_27001": "A.9.1"})
        cw = FrameworkCrosswalk([ctrl])
        found = cw.find_by_reference("iso_27001", "A.9.1")
        assert len(found) == 1

    def test_multiple_controls_same_reference(self):
        from unimonitor.grc.crosswalk import FrameworkCrosswalk

        ctrl_a = _make_ctrl("C1", {"iso_27001": ["A.9.1"]})
        ctrl_b = _make_ctrl("C2", {"iso_27001": ["A.9.1"]})
        cw = FrameworkCrosswalk([ctrl_a, ctrl_b])
        found = cw.find_by_reference("iso_27001", "A.9.1")
        assert len(found) == 2

    def test_empty_controls(self):
        from unimonitor.grc.crosswalk import FrameworkCrosswalk

        cw = FrameworkCrosswalk([])
        assert cw.all_frameworks() == []
        assert cw.find_by_reference("iso_27001", "A.1") == []


# ---------------------------------------------------------------------------
# Module-level functions in crosswalk.py
# ---------------------------------------------------------------------------


class TestCrosswalkFunctions:
    def test_crosswalk_for_control_returns_dict(self):
        """crosswalk_for_control should return a dict (even for unknown IDs)."""
        from unimonitor.grc.crosswalk import crosswalk_for_control

        result = crosswalk_for_control("NONEXISTENT_ID")
        assert isinstance(result, dict)

    def test_get_crosswalk_index_caches(self):
        """get_crosswalk_index returns same object on second call (caching)."""
        import unimonitor.grc.crosswalk as cw_module

        # Reset cache
        cw_module._crosswalk_index = None
        from unimonitor.grc.crosswalk import get_crosswalk_index

        idx1 = get_crosswalk_index()
        idx2 = get_crosswalk_index()
        assert idx1 is idx2

    def test_controls_for_framework_returns_list(self):
        from unimonitor.grc.crosswalk import controls_for_framework

        result = controls_for_framework("nonexistent_fw")
        assert isinstance(result, list)

    def test_gap_analysis_returns_structure(self):
        from unimonitor.grc.crosswalk import gap_analysis

        result = gap_analysis({}, "nonexistent_fw")
        assert "framework_id" in result
        assert "coverage_percent" in result
        assert "gaps_by_severity" in result

    def test_gap_analysis_counts_implementations(self):
        from unimonitor.grc.crosswalk import gap_analysis

        # Build minimal mock controls
        mock_ctrl = {"id": "C1", "name": "Test", "category": "cat", "severity": "high", "frameworks": ["test_fw"]}
        with patch("unimonitor.grc.crosswalk.controls_for_framework", return_value=[mock_ctrl]):
            result = gap_analysis({"C1": "implemented"}, "test_fw")
        assert result["implemented"] == 1
        assert result["not_implemented"] == 0

    def test_gap_analysis_identifies_gaps(self):
        from unimonitor.grc.crosswalk import gap_analysis

        mock_ctrl = {
            "id": "C1",
            "name": "MFA",
            "category": "access",
            "severity": "critical",
            "remediation_summary": "Enable MFA",
            "frameworks": ["test_fw"],
        }
        with patch("unimonitor.grc.crosswalk.controls_for_framework", return_value=[mock_ctrl]):
            result = gap_analysis({}, "test_fw")  # no findings → all not_implemented
        assert result["not_implemented"] == 1
        assert len(result["gaps_by_severity"]["critical"]) == 1
