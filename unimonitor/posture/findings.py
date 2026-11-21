"""Shared finding shape and scoring for the posture analysers.

Every analyser returns the same structure so the API, the UI and the scorecard
export can treat them uniformly. The score is a relative prioritisation number
derived from severity weights — it is not a compliance percentage and is never
used to claim that a platform is "secure".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SEVERITY_ORDER = ("critical", "high", "medium", "low", "informational")

# Cost of one finding at each severity, subtracted from 100.
SEVERITY_WEIGHT = {
    "critical": 25,
    "high": 15,
    "medium": 8,
    "low": 3,
    "informational": 1,
}


@dataclass(frozen=True, slots=True)
class PostureFinding:
    id: str
    title: str
    severity: str
    category: str
    resource: str
    detail: str
    remediation: str = ""
    steps: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "severity": self.severity,
            "category": self.category,
            "resource": self.resource,
            "detail": self.detail,
            "remediation": self.remediation,
        }
        if self.steps:
            payload["steps"] = list(self.steps)
        return payload


def resource_name(resource: dict[str, Any]) -> str:
    """Stable human label for a resource."""
    return str(resource.get("name") or resource.get("id") or resource.get("arn") or "unnamed")


def _penalty(findings: list[dict[str, Any]]) -> int:
    return sum(SEVERITY_WEIGHT.get(str(finding.get("severity", "")).lower(), 0) for finding in findings)


def risk_score(findings: list[dict[str, Any]]) -> int:
    """0–100, where 100 means no finding was raised by this engine."""
    return max(0, 100 - _penalty(findings))


def summarise(findings: list[dict[str, Any]]) -> dict[str, Any]:
    by_severity = dict.fromkeys(SEVERITY_ORDER, 0)
    by_category: dict[str, int] = {}
    for finding in findings:
        severity = str(finding.get("severity", "informational")).lower()
        by_severity[severity] = by_severity.get(severity, 0) + 1
        category = str(finding.get("category", "other"))
        by_category[category] = by_category.get(category, 0) + 1
    return {
        "total": len(findings),
        "by_severity": by_severity,
        "by_category": by_category,
    }


def sort_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {severity: index for index, severity in enumerate(SEVERITY_ORDER)}
    return sorted(
        findings,
        key=lambda finding: (order.get(str(finding.get("severity", "")).lower(), len(order)), str(finding.get("title", ""))),
    )


def result(category: str, label: str, findings: list[PostureFinding], *, empty_note: str = "") -> dict[str, Any]:
    """Package one analyser's output."""
    serialised = [finding.as_dict() for finding in findings]
    payload: dict[str, Any] = {
        "category": category,
        "label": label,
        "risk_score": risk_score(serialised),
        "summary": summarise(serialised),
        "findings": sort_findings(serialised),
    }
    if not serialised and empty_note:
        payload["note"] = empty_note
    return payload


__all__ = [
    "PostureFinding",
    "SEVERITY_ORDER",
    "SEVERITY_WEIGHT",
    "resource_name",
    "result",
    "risk_score",
    "sort_findings",
    "summarise",
]
