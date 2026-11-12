"""
Unit tests for scoring utilities.
"""
import pytest


class TestFindingScoring:
    def test_severity_order(self):
        """Higher severities have higher weights than lower ones."""
        from unimonitor.grc.scoring import SEVERITY_WEIGHTS
        assert SEVERITY_WEIGHTS["CRITICAL"] > SEVERITY_WEIGHTS["HIGH"]
        assert SEVERITY_WEIGHTS["HIGH"] > SEVERITY_WEIGHTS["MEDIUM"]
        assert SEVERITY_WEIGHTS["MEDIUM"] > SEVERITY_WEIGHTS["LOW"]
        assert SEVERITY_WEIGHTS["LOW"] > SEVERITY_WEIGHTS["INFORMATIONAL"]

    def test_partial_gives_half_credit(self):
        """Partially implemented gives 50% of the control's weight."""
        from unimonitor.grc.scoring import compute_score

        full = compute_score([{"severity": "HIGH", "state": "implemented"}])
        partial = compute_score([{"severity": "HIGH", "state": "partially_implemented"}])
        none = compute_score([{"severity": "HIGH", "state": "not_implemented"}])

        assert full == 100
        assert none == 0
        assert partial == 50

    def test_score_clamps_0_100(self):
        """Score never exceeds 100 or goes below 0."""
        from unimonitor.grc.scoring import compute_score

        s1 = compute_score([{"severity": "CRITICAL", "state": "implemented"}] * 100)
        s2 = compute_score([{"severity": "CRITICAL", "state": "not_implemented"}] * 100)
        assert 0 <= s1 <= 100
        assert 0 <= s2 <= 100

    def test_framework_score_calculation(self):
        """Framework score aggregates correctly across controls."""
        from unimonitor.grc.scoring import compute_framework_score

        framework_findings = [
            {"framework_control": "A.9.1.1", "state": "implemented", "severity": "HIGH"},
            {"framework_control": "A.9.1.2", "state": "not_implemented", "severity": "CRITICAL"},
            {"framework_control": "A.9.2.1", "state": "partially_implemented", "severity": "MEDIUM"},
        ]
        result = compute_framework_score(framework_findings)
        assert isinstance(result, dict)
        assert "score" in result
        assert "implemented" in result
        assert "partial" in result
        assert "not_implemented" in result
        assert result["implemented"] == 1
        assert result["partial"] == 1
        assert result["not_implemented"] == 1
        assert 0 <= result["score"] <= 100
