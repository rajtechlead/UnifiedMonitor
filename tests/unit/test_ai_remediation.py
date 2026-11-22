"""
Unit tests for grc/ai_remediation.py

Tests AIRemediationEngine, _normalise, _rule_based_remediation,
module-level generate_remediation, and _openai_remediation.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


FINDING_DICT = {
    "title": "MFA Enforcement",
    "description": "MFA is not enabled for all users.",
    "severity": "high",
    "category": "Identity",
    "state": "not_implemented",
    "control_id": "ENT-001",
}

FINDING_ORM = MagicMock(
    title="MFA Enforcement",
    description="MFA is not enabled.",
    severity="HIGH",
    category="Identity",
    state="not_implemented",
    control_id="ENT-001",
)


# ---------------------------------------------------------------------------
# AIRemediationEngine.generate_remediation (use_fallback=True)
# ---------------------------------------------------------------------------


class TestAIRemediationEngineFallback:
    def test_returns_9_field_dict(self):
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        engine = AIRemediationEngine(use_fallback=True)
        result = _run(engine.generate_remediation(FINDING_DICT))
        expected_keys = {"summary", "steps", "priority", "effort", "risk_if_ignored", "references", "automation_script", "estimated_time", "source"}
        assert expected_keys == set(result.keys())

    def test_source_is_rule_based(self):
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        engine = AIRemediationEngine(use_fallback=True)
        result = _run(engine.generate_remediation(FINDING_DICT))
        assert result["source"] == "rule_based"

    def test_steps_is_list(self):
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        engine = AIRemediationEngine(use_fallback=True)
        result = _run(engine.generate_remediation(FINDING_DICT))
        assert isinstance(result["steps"], list)
        assert len(result["steps"]) > 0

    def test_references_are_strings(self):
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        engine = AIRemediationEngine(use_fallback=True)
        result = _run(engine.generate_remediation(FINDING_DICT))
        for ref in result["references"]:
            assert isinstance(ref, str)

    def test_works_with_orm_object(self):
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        engine = AIRemediationEngine(use_fallback=True)
        result = _run(engine.generate_remediation(FINDING_ORM))
        assert result["source"] == "rule_based"
        assert "MFA" in result["summary"]

    def test_severity_affects_priority(self):
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        engine = AIRemediationEngine(use_fallback=True)
        critical_finding = {**FINDING_DICT, "severity": "critical"}
        result = _run(engine.generate_remediation(critical_finding))
        # critical severity maps to 'high' complexity → 'critical' priority
        assert result["priority"] == "critical"

    def test_low_severity(self):
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        engine = AIRemediationEngine(use_fallback=True)
        low_finding = {**FINDING_DICT, "severity": "low"}
        result = _run(engine.generate_remediation(low_finding))
        assert result["source"] == "rule_based"


# ---------------------------------------------------------------------------
# AIRemediationEngine._call_openai path
# ---------------------------------------------------------------------------


class TestAIRemediationEngineOpenAI:
    def test_ai_disabled_uses_fallback(self):
        """When AI_ENABLED=False, falls back to rule_based."""
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        engine = AIRemediationEngine(use_fallback=False)
        mock_settings = MagicMock()
        mock_settings.AI_ENABLED = False
        with patch("unimonitor.grc.ai_remediation.get_settings", return_value=mock_settings):
            result = _run(engine.generate_remediation(FINDING_DICT))
        assert result["source"] == "rule_based"

    def test_ai_enabled_uses_openai_result(self):
        """When AI returns a result, source is azure_openai."""
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        engine = AIRemediationEngine(use_fallback=False)
        ai_result = {
            "executive_summary": "AI summary",
            "remediation_plan": ["Step 1", "Step 2"],
            "complexity": "medium",
            "estimated_effort_hours": 3.0,
            "risk_reduction_estimate": "Reduces risk",
            "microsoft_references": [{"title": "MS Doc", "url": "https://learn.microsoft.com"}],
        }
        with patch.object(engine, "_call_openai", new=AsyncMock(return_value=ai_result)):
            result = _run(engine.generate_remediation(FINDING_DICT))
        assert result["source"] == "ai"
        assert result["summary"] == "AI summary"
        assert result["steps"] == ["Step 1", "Step 2"]

    def test_openai_exception_falls_back(self):
        """If OpenAI call raises, rule-based fallback is used."""
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        engine = AIRemediationEngine(use_fallback=False)
        with patch.object(engine, "_call_openai", new=AsyncMock(side_effect=RuntimeError("timeout"))):
            result = _run(engine.generate_remediation(FINDING_DICT))
        assert result["source"] == "rule_based"

    def test_openai_returns_none_falls_back(self):
        """If OpenAI returns None (not configured), rule-based fallback."""
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        engine = AIRemediationEngine(use_fallback=False)
        with patch.object(engine, "_call_openai", new=AsyncMock(return_value=None)):
            result = _run(engine.generate_remediation(FINDING_DICT))
        assert result["source"] == "rule_based"


# ---------------------------------------------------------------------------
# AIRemediationEngine._normalise edge cases
# ---------------------------------------------------------------------------


class TestNormalise:
    def test_steps_as_string_becomes_list(self):
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        raw = {"steps": "single step", "complexity": "low"}
        result = AIRemediationEngine._normalise(raw, source="test")
        assert result["steps"] == ["single step"]

    def test_dict_reference_extracts_url(self):
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        raw = {
            "microsoft_references": [{"title": "MS", "url": "https://learn.microsoft.com"}],
            "complexity": "medium",
        }
        result = AIRemediationEngine._normalise(raw, source="test")
        assert result["references"] == ["https://learn.microsoft.com"]

    def test_string_reference_preserved(self):
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        raw = {
            "references": ["https://example.com"],
            "complexity": "low",
        }
        result = AIRemediationEngine._normalise(raw, source="test")
        assert result["references"] == ["https://example.com"]

    def test_effort_from_hours(self):
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        raw = {"estimated_effort_hours": 4.0, "complexity": "high"}
        result = AIRemediationEngine._normalise(raw, source="test")
        assert "4" in result["effort"]

    def test_missing_fields_dont_raise(self):
        from unimonitor.grc.ai_remediation import AIRemediationEngine

        result = AIRemediationEngine._normalise({}, source="test")
        assert result["source"] == "test"
        assert isinstance(result["steps"], list)


# ---------------------------------------------------------------------------
# Module-level generate_remediation function
# ---------------------------------------------------------------------------


class TestModuleLevelGenerateRemediation:
    def test_ai_disabled_returns_rule_based(self):
        from unimonitor.grc.ai_remediation import generate_remediation

        mock_settings = MagicMock()
        mock_settings.AI_ENABLED = False
        with patch("unimonitor.grc.ai_remediation.get_settings", return_value=mock_settings):
            result = _run(
                generate_remediation(
                    finding_title="Test",
                    finding_description="Description",
                    severity="medium",
                    category="Identity",
                    state="not_implemented",
                    control_id="C1",
                )
            )
        assert isinstance(result, dict)
        # rule_based returns dict (not normalised, so has executive_summary etc)
        assert "executive_summary" in result or "summary" in result

    def test_ai_enabled_calls_openai(self):
        from unimonitor.grc.ai_remediation import generate_remediation

        mock_settings = MagicMock()
        mock_settings.AI_ENABLED = True
        mock_settings.AZURE_OPENAI_ENDPOINT = "https://api.openai.azure.com"
        mock_settings.AZURE_OPENAI_API_KEY = "key123"
        openai_result = {"executive_summary": "AI result", "complexity": "medium", "estimated_effort_hours": 2.0}
        with patch("unimonitor.grc.ai_remediation.get_settings", return_value=mock_settings):
            with patch("unimonitor.grc.ai_remediation._openai_remediation", new=AsyncMock(return_value=openai_result)):
                result = _run(
                    generate_remediation(
                        finding_title="Test",
                        finding_description="Desc",
                        severity="high",
                        category="Identity",
                        state="not_implemented",
                        control_id="C1",
                    )
                )
        assert result.get("executive_summary") == "AI result"

    def test_ai_exception_falls_back(self):
        from unimonitor.grc.ai_remediation import generate_remediation

        mock_settings = MagicMock()
        mock_settings.AI_ENABLED = True
        mock_settings.AZURE_OPENAI_ENDPOINT = "https://api.openai.azure.com"
        mock_settings.AZURE_OPENAI_API_KEY = "key"
        with patch("unimonitor.grc.ai_remediation.get_settings", return_value=mock_settings):
            with patch("unimonitor.grc.ai_remediation._openai_remediation", new=AsyncMock(side_effect=RuntimeError("conn"))):
                result = _run(
                    generate_remediation(
                        finding_title="Test",
                        finding_description="",
                        severity="medium",
                        category="",
                        state="not_implemented",
                        control_id="",
                    )
                )
        # fell back to rule-based
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# _rule_based_remediation
# ---------------------------------------------------------------------------


class TestRuleBasedRemediation:
    def test_all_severity_levels(self):
        from unimonitor.grc.ai_remediation import _rule_based_remediation

        for sev in ["critical", "high", "medium", "low", "informational"]:
            result = _rule_based_remediation(finding_title="Test", finding_description="", severity=sev, category="Identity", control_id="C1")
            assert isinstance(result, dict)
            assert "remediation_plan" in result
            assert "executive_summary" in result

    def test_identity_category_adds_entra_refs(self):
        from unimonitor.grc.ai_remediation import _rule_based_remediation

        result = _rule_based_remediation(finding_title="MFA", finding_description="", severity="high", category="Identity", control_id="ENT-001")
        urls = [r["url"] for r in result["microsoft_references"]]
        assert any("entra" in u.lower() for u in urls)

    def test_devices_category_adds_intune_refs(self):
        from unimonitor.grc.ai_remediation import _rule_based_remediation

        result = _rule_based_remediation(
            finding_title="Compliance", finding_description="", severity="medium", category="Devices", control_id="INT-001"
        )
        urls = [r["url"] for r in result["microsoft_references"]]
        assert any("intune" in u.lower() or "mem" in u.lower() for u in urls)

    def test_unknown_category_uses_base_refs(self):
        from unimonitor.grc.ai_remediation import _rule_based_remediation

        result = _rule_based_remediation(finding_title="Test", finding_description="", severity="medium", category="UnknownCategory", control_id="X1")
        assert len(result["microsoft_references"]) >= 2

    def test_description_truncated_in_summary(self):
        from unimonitor.grc.ai_remediation import _rule_based_remediation

        long_desc = "X" * 500
        result = _rule_based_remediation(finding_title="T", finding_description=long_desc, severity="low", category="", control_id="C")
        # technical_summary should truncate at 300 chars
        assert len(result["technical_summary"]) < 400
