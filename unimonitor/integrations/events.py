"""One canonical event shape for SIEM and ticketing integrations.

The export endpoint, the syslog connector and the HTTP connectors all describe a
finding the same way, so a finding looks identical whichever way it leaves the
product.
"""

from __future__ import annotations

from typing import Any

# CEF severity is 0–10; map the finding's severity band onto it.
_CEF_SEVERITY = {
    "CRITICAL": "10",
    "HIGH": "8",
    "MEDIUM": "5",
    "LOW": "3",
    "INFORMATIONAL": "1",
}


def _cef_escape(value: object) -> str:
    """Escape a CEF header/extension value."""
    text = str(value if value is not None else "")
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _cef_severity(severity: str | None) -> str:
    return _CEF_SEVERITY.get((severity or "").upper(), "5")


def finding_event(finding: Any) -> dict[str, Any]:
    """Render a finding as the JSON event every connector sends."""
    return {
        "id": finding.id,
        "tenant_id": finding.tenant_id,
        "control": finding.external_control_id,
        "title": finding.title,
        "severity": finding.severity,
        "state": finding.state,
        "category": finding.category,
        "service": finding.service,
        "risk_score": finding.risk_score,
        "triage_status": getattr(finding, "triage_status", "open"),
        "first_detected_at": finding.first_detected_at.isoformat() if finding.first_detected_at else None,
        "last_seen_at": finding.last_seen_at.isoformat() if finding.last_seen_at else None,
    }


def finding_cef(finding: Any) -> str:
    """Render a finding as a CEF line (ArcSight/Splunk/QRadar syslog format)."""
    return (
        "CEF:0|UniMonitor|UniMonitor|1.0|"
        f"{_cef_escape(finding.external_control_id)}|{_cef_escape(finding.title)}|"
        f"{_cef_severity(finding.severity)}|"
        f"src=unimonitor cs1Label=TenantId cs1={_cef_escape(finding.tenant_id)} "
        f"cs2Label=Category cs2={_cef_escape(finding.category)} "
        f"cs3Label=Service cs3={_cef_escape(finding.service)} "
        f"cs4Label=State cs4={_cef_escape(finding.state)} "
        f"cn1Label=RiskScore cn1={finding.risk_score} "
        f"end={int(finding.last_seen_at.timestamp() * 1000) if finding.last_seen_at else 0}"
    )
