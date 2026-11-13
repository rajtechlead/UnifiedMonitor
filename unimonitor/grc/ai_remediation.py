"""
AI Remediation Engine — generates structured remediation content for findings
using Azure OpenAI (GPT-4o) when configured, with a rule-based fallback.
"""

from __future__ import annotations

import json
from typing import Any

from unimonitor.config import get_settings
from unimonitor.core.logging import get_logger

logger = get_logger(__name__)


# ── AIRemediationEngine class ─────────────────────────────────


class AIRemediationEngine:
    """Generate structured remediation guidance for security findings.

    ``use_fallback=True`` forces rule-based generation regardless of AI
    configuration — useful in tests and air-gapped environments.

    The result dict always contains these 9 keys:
    ``summary``, ``steps``, ``priority``, ``effort``, ``risk_if_ignored``,
    ``references``, ``automation_script``, ``estimated_time``, ``source``.
    """

    def __init__(self, use_fallback: bool = False) -> None:
        self.use_fallback = use_fallback

    async def generate_remediation(self, finding: dict) -> dict[str, Any]:
        """Generate remediation for *finding* (a plain dict or ORM-like object).

        Returns a normalised 9-field dict with key ``source`` set to
        ``"rule_based"`` when the fallback path is used or ``"azure_openai"``
        when the AI path succeeds.
        """

        # Extract fields from the finding (supports dicts and ORM objects)
        def _get(key: str, default: Any = "") -> Any:
            if isinstance(finding, dict):
                return finding.get(key, default)
            return getattr(finding, key, default)

        title = _get("title") or _get("control_id", "Unknown Control")
        description = _get("description", "")
        severity = (_get("severity") or "medium").lower()
        category = _get("category", "")
        state = _get("state", "not_implemented")
        control_id = _get("control_id") or _get("external_control_id", "")

        if not self.use_fallback:
            try:
                result = await self._call_openai(
                    finding_title=title,
                    finding_description=description,
                    severity=severity,
                    category=category,
                    state=state,
                    control_id=control_id,
                )
                if result is not None:
                    return self._normalise(result, source="azure_openai")
            except Exception as exc:
                logger.warning("ai_remediation_failed_fallback", error=str(exc))

        raw = _rule_based_remediation(
            finding_title=title,
            finding_description=description,
            severity=severity,
            category=category,
            control_id=control_id,
        )
        return self._normalise(raw, source="rule_based")

    async def _call_openai(
        self,
        finding_title: str,
        finding_description: str,
        severity: str,
        category: str,
        state: str,
        control_id: str,
    ) -> dict[str, Any] | None:
        """Call Azure OpenAI to generate structured remediation.

        Separated as a named method so tests can patch it cleanly via
        ``patch('unimonitor.grc.ai_remediation.AIRemediationEngine._call_openai')``.

        Returns ``None`` when OpenAI is not configured (triggers rule-based fallback).
        """
        settings = get_settings()
        if not settings.AI_ENABLED or not getattr(settings, "AZURE_OPENAI_ENDPOINT", None):
            return None
        return await _openai_remediation(
            finding_title=finding_title,
            finding_description=finding_description,
            severity=severity,
            category=category,
            state=state,
            control_id=control_id,
        )

    @staticmethod
    def _normalise(raw: dict, source: str) -> dict[str, Any]:
        """Map the internal dict fields to the standard 9-field output schema."""
        severity = (raw.get("complexity") or "medium").lower()
        priority_map = {"high": "critical", "medium": "high", "low": "medium"}
        priority = priority_map.get(severity, "high")

        # Build steps list from remediation_plan if present
        steps: list[str] = raw.get("remediation_plan") or raw.get("steps") or []
        if isinstance(steps, str):
            steps = [steps]

        # effort as human string
        effort_hours = raw.get("estimated_effort_hours") or 2.0
        effort = raw.get("effort") or f"{effort_hours:.0f} hours"

        # references as list of URL strings or title/url dicts
        refs_raw: list = raw.get("microsoft_references") or raw.get("references") or []
        references: list[str] = []
        for r in refs_raw:
            if isinstance(r, dict):
                references.append(r.get("url") or r.get("title", ""))
            else:
                references.append(str(r))

        return {
            "summary": raw.get("executive_summary") or raw.get("summary", ""),
            "steps": steps,
            "priority": raw.get("priority") or priority,
            "effort": effort,
            "risk_if_ignored": raw.get("risk_reduction_estimate") or raw.get("risk_if_ignored", ""),
            "references": references,
            "automation_script": raw.get("automation_script", ""),
            "estimated_time": raw.get("estimated_time") or f"{effort_hours:.0f} hours",
            "source": source,
        }


REMEDIATION_SCHEMA = {
    "executive_summary": "str",
    "technical_summary": "str",
    "root_cause_analysis": "str",
    "remediation_plan": "list[str]",
    "validation_steps": "list[str]",
    "microsoft_references": "list[{title: str, url: str}]",
    "risk_reduction_estimate": "str",
    "estimated_effort_hours": "float",
    "complexity": "str",  # low | medium | high
}


async def generate_remediation(
    finding_title: str,
    finding_description: str,
    severity: str,
    category: str,
    state: str,
    control_id: str,
    tenant_context: dict | None = None,
) -> dict[str, Any]:
    """
    Generate AI-powered remediation for a finding.
    Falls back to rule-based generation if AI is not configured.
    """
    settings = get_settings()

    if settings.AI_ENABLED and settings.AZURE_OPENAI_ENDPOINT and settings.AZURE_OPENAI_API_KEY:
        try:
            return await _openai_remediation(
                finding_title=finding_title,
                finding_description=finding_description,
                severity=severity,
                category=category,
                state=state,
                control_id=control_id,
            )
        except Exception as exc:
            logger.warning("AI remediation failed, falling back to rule-based", error=str(exc))

    return _rule_based_remediation(
        finding_title=finding_title,
        finding_description=finding_description,
        severity=severity,
        category=category,
        control_id=control_id,
    )


async def _openai_remediation(
    finding_title: str,
    finding_description: str,
    severity: str,
    category: str,
    state: str,
    control_id: str,
) -> dict[str, Any]:
    """Call Azure OpenAI to generate structured remediation."""
    settings = get_settings()

    system_prompt = """You are a Microsoft 365 security expert and GRC consultant.
Generate structured remediation guidance for a security finding.
Respond ONLY with valid JSON matching this schema exactly:
{
  "executive_summary": "1-2 sentence non-technical summary for executives",
  "technical_summary": "2-3 sentence technical description of the issue",
  "root_cause_analysis": "explanation of why this control is failing",
  "remediation_plan": ["step 1", "step 2", ...],
  "validation_steps": ["how to verify step 1", ...],
  "microsoft_references": [{"title": "...", "url": "https://..."}],
  "risk_reduction_estimate": "description of risk reduced when remediated",
  "estimated_effort_hours": 2.0,
  "complexity": "low|medium|high"
}"""

    user_prompt = f"""Finding: {finding_title}
Control ID: {control_id}
Severity: {severity}
Category: {category}
Current State: {state}
Description: {finding_description}

Generate remediation guidance for this Microsoft 365 security finding."""

    import httpx

    url = f"{settings.AZURE_OPENAI_ENDPOINT}/openai/deployments/{settings.AZURE_OPENAI_DEPLOYMENT}/chat/completions?api-version=2024-02-01"
    headers = {
        "api-key": settings.AZURE_OPENAI_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1500,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)


def _rule_based_remediation(
    finding_title: str,
    finding_description: str,
    severity: str,
    category: str,
    control_id: str,
) -> dict[str, Any]:
    """Generate structured remediation using rule-based templates."""
    severity_risk_map = {
        "critical": "eliminates an actively exploitable attack path",
        "high": "significantly reduces attack surface and exposure",
        "medium": "reduces risk of privilege escalation or data exposure",
        "low": "improves security posture and defence-in-depth",
        "informational": "hardens configuration and reduces future risk",
    }

    effort_map = {"critical": 4.0, "high": 3.0, "medium": 2.0, "low": 1.0, "informational": 0.5}
    complexity_map = {"critical": "high", "high": "medium", "medium": "medium", "low": "low", "informational": "low"}

    base_refs = [
        {
            "title": "Microsoft 365 Security Best Practices",
            "url": "https://learn.microsoft.com/en-us/microsoft-365/security/",
        },
        {
            "title": "Microsoft Secure Score",
            "url": "https://learn.microsoft.com/en-us/microsoft-365/security/defender/microsoft-secure-score",
        },
    ]

    # Category-specific references
    category_refs = {
        "Identity": [
            {"title": "Entra ID Security", "url": "https://learn.microsoft.com/en-us/entra/identity/"},
            {
                "title": "Conditional Access Best Practices",
                "url": "https://learn.microsoft.com/en-us/entra/identity/conditional-access/plan-conditional-access",
            },
        ],
        "Devices": [
            {"title": "Intune Security", "url": "https://learn.microsoft.com/en-us/mem/intune/protect/"},
            {"title": "Device Compliance", "url": "https://learn.microsoft.com/en-us/mem/intune/protect/device-compliance-get-started"},
        ],
        "Defender": [
            {"title": "Microsoft Defender XDR", "url": "https://learn.microsoft.com/en-us/microsoft-365/security/defender/"},
        ],
        "Applications": [
            {"title": "App Governance", "url": "https://learn.microsoft.com/en-us/microsoft-365/app-governance/"},
        ],
    }

    refs = base_refs + category_refs.get(category, [])

    return {
        "executive_summary": (
            f"The control '{finding_title}' ({severity} severity) is currently not implemented "
            f"in the {category} domain. Remediating this finding will {severity_risk_map.get(severity, 'improve security posture')}."
        ),
        "technical_summary": (
            f"Control {control_id} evaluated as not implemented. "
            f"{finding_description[:300] if finding_description else 'Review the Microsoft documentation to understand the required configuration.'}"
        ),
        "root_cause_analysis": (
            f"The required security configuration for '{finding_title}' has not been applied to this tenant. "
            f"This may be due to default settings not meeting security requirements, "
            f"or deliberate configuration choices that did not account for the security implications."
        ),
        "remediation_plan": [
            f"Review the current configuration for {finding_title} in the Microsoft 365 admin center.",
            f"Identify all affected resources and policies in the {category} domain.",
            "Apply the required security configuration following Microsoft best practices.",
            "Test the change in a pilot group before broad deployment.",
            "Document the change and update your security runbooks.",
        ],
        "validation_steps": [
            "Verify the configuration has been applied via Microsoft 365 Admin Center.",
            "Run a UniMonitor assessment to confirm the control now shows 'Implemented'.",
            "Review audit logs to confirm no unintended side effects.",
            "Check Microsoft Secure Score for the expected improvement.",
        ],
        "microsoft_references": refs,
        "risk_reduction_estimate": f"Remediating this {severity} finding will {severity_risk_map.get(severity, 'reduce risk')}.",
        "estimated_effort_hours": effort_map.get(severity, 2.0),
        "complexity": complexity_map.get(severity, "medium"),
    }
