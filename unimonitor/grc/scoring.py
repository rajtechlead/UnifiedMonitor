"""
GRC scoring algorithms.

Security Score  — weighted pass/fail ratio across controls, severity-weighted.
Compliance Score — percentage of controls in Implemented or Partially Implemented state.
Risk Score      — aggregate weighted risk (0–100, inverted: 100 = no risk).
"""

from __future__ import annotations

from unimonitor.db.models.finding import Finding, FindingSeverity, FindingState

SEVERITY_WEIGHT = {
    FindingSeverity.CRITICAL.value: 10,
    FindingSeverity.HIGH.value: 8,
    FindingSeverity.MEDIUM.value: 5,
    FindingSeverity.LOW.value: 3,
    FindingSeverity.INFORMATIONAL.value: 1,
}

# Canonical alias used by tests and external consumers
SEVERITY_WEIGHTS = {
    "CRITICAL": 10,
    "HIGH": 8,
    "MEDIUM": 5,
    "LOW": 3,
    "INFORMATIONAL": 1,
}

STATE_COMPLIANCE_CREDIT = {
    FindingState.IMPLEMENTED.value: 1.0,
    FindingState.PARTIALLY_IMPLEMENTED.value: 0.5,
    FindingState.NOT_IMPLEMENTED.value: 0.0,
    FindingState.NOT_APPLICABLE.value: None,  # excluded from scoring
}


def calculate_scores(findings: list[Finding]) -> dict:
    """
    Returns:
        security_score   : 0–100 (100 = all controls passing)
        compliance_score : 0–100 (100 = all controls implemented)
        risk_score       : 0–100 (100 = no residual risk)
        critical_count, high_count, medium_count, low_count, informational_count
    """
    if not findings:
        return {
            "security_score": 100.0,
            "compliance_score": 100.0,
            "risk_score": 100.0,
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "informational_count": 0,
        }

    severity_counts: dict[str, int] = {
        FindingSeverity.CRITICAL.value: 0,
        FindingSeverity.HIGH.value: 0,
        FindingSeverity.MEDIUM.value: 0,
        FindingSeverity.LOW.value: 0,
        FindingSeverity.INFORMATIONAL.value: 0,
    }

    total_weight = 0.0
    passed_weight = 0.0
    compliance_applicable = 0
    compliance_credit = 0.0
    total_risk = 0.0
    max_risk = 0.0

    for f in findings:
        if f.is_suppressed:
            continue

        sev = f.severity
        weight = SEVERITY_WEIGHT.get(sev, 5)
        total_weight += weight
        max_risk += weight

        # Severity counts (only non-implemented findings for dashboard KPI tiles)
        if f.state != FindingState.IMPLEMENTED.value:
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # Security score: pass = fully implemented
        if f.state == FindingState.IMPLEMENTED.value:
            passed_weight += weight

        # Compliance score
        credit = STATE_COMPLIANCE_CREDIT.get(f.state)
        if credit is not None:  # skip NA
            compliance_applicable += 1
            compliance_credit += credit * weight

        # Risk score
        total_risk += f.risk_score

    security_score = round((passed_weight / total_weight) * 100, 2) if total_weight else 100.0
    compliance_score = round((compliance_credit / total_weight) * 100, 2) if total_weight else 100.0

    # Risk score: invert (lower accumulated risk = higher score)
    # Normalise to 0-100 using max possible (every control at max severity = 10)
    theoretical_max_risk = max_risk * 10 / max(SEVERITY_WEIGHT.values())
    if theoretical_max_risk > 0:
        risk_score = max(0.0, round(100.0 - (total_risk / theoretical_max_risk) * 100, 2))
    else:
        risk_score = 100.0

    return {
        "security_score": security_score,
        "compliance_score": compliance_score,
        "risk_score": risk_score,
        "critical_count": severity_counts[FindingSeverity.CRITICAL.value],
        "high_count": severity_counts[FindingSeverity.HIGH.value],
        "medium_count": severity_counts[FindingSeverity.MEDIUM.value],
        "low_count": severity_counts[FindingSeverity.LOW.value],
        "informational_count": severity_counts[FindingSeverity.INFORMATIONAL.value],
    }


def calculate_framework_coverage(
    findings: list[Finding],
    framework_control_ids: list[str],
) -> dict:
    """Calculate coverage for a specific framework."""
    mapped_findings = {f.external_control_id: f for f in findings}

    total = len(framework_control_ids)
    if total == 0:
        return {"coverage_percent": 0.0, "implemented": 0, "partial": 0, "not_implemented": 0, "total": 0}

    implemented = 0
    partial = 0
    not_implemented = 0

    for ctrl_id in framework_control_ids:
        f = mapped_findings.get(ctrl_id)
        if f is None:
            not_implemented += 1
        elif f.state == FindingState.IMPLEMENTED.value:
            implemented += 1
        elif f.state == FindingState.PARTIALLY_IMPLEMENTED.value:
            partial += 1
        elif f.state == FindingState.NOT_APPLICABLE.value:
            total -= 1  # exclude NA from denominator
        else:
            not_implemented += 1

    if total <= 0:
        return {"coverage_percent": 100.0, "implemented": 0, "partial": 0, "not_implemented": 0, "total": 0}

    coverage = round(((implemented + partial * 0.5) / total) * 100, 2)
    return {
        "coverage_percent": coverage,
        "implemented": implemented,
        "partial": partial,
        "not_implemented": not_implemented,
        "total": total,
    }


# ---------------------------------------------------------------------------
# Lightweight dict-based API (used by tests and engine without ORM objects)
# ---------------------------------------------------------------------------

def compute_score(raw_findings: list[dict]) -> float:
    """
    Compute a 0–100 security score from a list of raw finding dicts.

    Each dict must have:
        severity : str  ("CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFORMATIONAL")
        state    : str  ("implemented" | "partially_implemented" | "not_implemented" | "not_applicable")

    Returns a float in [0.0, 100.0].
    """
    if not raw_findings:
        return 100.0

    total_weight = 0.0
    passed_weight = 0.0

    for f in raw_findings:
        sev = (f.get("severity") or "MEDIUM").upper()
        state = (f.get("state") or "not_implemented").lower()

        # not_applicable findings are excluded from denominator entirely
        if state == "not_applicable":
            continue

        weight = SEVERITY_WEIGHTS.get(sev, 5)
        total_weight += weight
        if state == "implemented":
            passed_weight += weight
        elif state == "partially_implemented":
            passed_weight += weight * 0.5

    if total_weight == 0:
        return 100.0
    return round((passed_weight / total_weight) * 100, 2)


def compute_framework_score(raw_findings: list[dict]) -> dict:
    """
    Compute pass/fail stats for a list of finding dicts scoped to one framework.

    Each dict must have:
        severity : str
        state    : str
        control_id (optional, for reference)

    Returns:
        {
            score          : float 0–100,
            total          : int,
            implemented    : int,
            partial        : int,
            not_implemented: int,
            not_applicable : int,
        }
    """
    total = len(raw_findings)
    if total == 0:
        return {
            "score": 100.0,
            "total": 0,
            "implemented": 0,
            "partial": 0,
            "not_implemented": 0,
            "not_applicable": 0,
        }

    implemented = partial = not_implemented = not_applicable = 0
    total_weight = 0.0
    passed_weight = 0.0

    for f in raw_findings:
        sev = (f.get("severity") or "MEDIUM").upper()
        state = (f.get("state") or "not_implemented").lower()
        weight = SEVERITY_WEIGHTS.get(sev, 5)

        if state == "not_applicable":
            not_applicable += 1
            continue

        total_weight += weight

        if state == "implemented":
            implemented += 1
            passed_weight += weight
        elif state == "partially_implemented":
            partial += 1
            passed_weight += weight * 0.5
        else:
            not_implemented += 1

    score = round((passed_weight / total_weight) * 100, 2) if total_weight else 100.0
    return {
        "score": score,
        "total": total,
        "implemented": implemented,
        "partial": partial,
        "not_implemented": not_implemented,
        "not_applicable": not_applicable,
    }
