"""
Unit tests for the AI remediation engine (rule-based fallback path).
"""
from unittest.mock import AsyncMock, patch

import pytest


class TestRuleBasedRemediation:
    """Test the rule-based fallback when Azure OpenAI is unavailable."""

    def _make_finding(self, **kwargs):
        defaults = {
            "id": "test-finding-id",
            "control_id": "CTRL-ENT-001",
            "title": "MFA not enabled for all users",
            "description": "MFA is not enforced for all user accounts",
            "severity": "CRITICAL",
            "framework": "iso_27001_2022",
            "framework_control": "A.9.4.2",
            "state": "not_implemented",
            "evidence_summary": "15 accounts without MFA",
        }
        defaults.update(kwargs)
        return defaults

    @pytest.mark.asyncio
    async def test_fallback_returns_structured_dict(self):
        """Rule-based fallback returns all 9 required fields."""
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        engine = AIRemediationEngine(use_fallback=True)
        finding = self._make_finding()
        result = await engine.generate_remediation(finding)

        required_fields = [
            "summary", "steps", "priority", "effort",
            "risk_if_ignored", "references", "automation_script",
            "estimated_time", "source",
        ]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_fallback_source_is_rule_based(self):
        """Fallback remediation is tagged as rule-based."""
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        engine = AIRemediationEngine(use_fallback=True)
        result = await engine.generate_remediation(self._make_finding())
        assert result["source"] == "rule_based"

    @pytest.mark.asyncio
    async def test_fallback_priority_matches_severity(self):
        """High-severity findings get higher priority in fallback."""
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        engine = AIRemediationEngine(use_fallback=True)
        critical = await engine.generate_remediation(self._make_finding(severity="CRITICAL"))
        low = await engine.generate_remediation(self._make_finding(severity="LOW"))

        priority_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        assert priority_order.get(critical["priority"].lower(), 0) >= \
               priority_order.get(low["priority"].lower(), 0)

    @pytest.mark.asyncio
    async def test_fallback_steps_are_non_empty_list(self):
        """Remediation steps are a non-empty list of strings."""
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        engine = AIRemediationEngine(use_fallback=True)
        result = await engine.generate_remediation(self._make_finding())
        assert isinstance(result["steps"], list)
        assert len(result["steps"]) > 0
        for step in result["steps"]:
            assert isinstance(step, str)
            assert len(step.strip()) > 0

    @pytest.mark.asyncio
    async def test_azure_openai_called_when_configured(self):
        """When Azure OpenAI is configured, the AI path is attempted."""
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        mock_response = {
            "summary": "Enable MFA via Conditional Access",
            "steps": ["Step 1", "Step 2"],
            "priority": "critical",
            "effort": "low",
            "risk_if_ignored": "Account compromise",
            "references": [],
            "automation_script": "",
            "estimated_time": "1 hour",
            "source": "azure_openai",
        }

        with patch(
            "unimonitor.grc.ai_remediation.AIRemediationEngine._call_openai",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            engine = AIRemediationEngine(use_fallback=False)
            result = await engine.generate_remediation(self._make_finding())
            assert result["source"] == "azure_openai"

    @pytest.mark.asyncio
    async def test_falls_back_on_openai_error(self):
        """Falls back to rule-based when Azure OpenAI raises an exception."""
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        with patch(
            "unimonitor.grc.ai_remediation.AIRemediationEngine._call_openai",
            new_callable=AsyncMock,
            side_effect=Exception("API rate limit"),
        ):
            engine = AIRemediationEngine(use_fallback=False)
            result = await engine.generate_remediation(self._make_finding())
            assert result["source"] == "rule_based"
