"""JSON report generator."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from unimonitor.reporting.base import BaseReportGenerator


class JsonReportGenerator(BaseReportGenerator):
    """Generates machine-readable JSON reports."""

    def generate(self, report_type: str = "full") -> str:
        output_path = self._get_output_path("json")
        stats = self._summary_stats()

        findings_data: list[dict[str, Any]] = []
        for f in self.findings:
            g = self._get_finding_attr
            f_id = g(f, "id", "")
            ai_rem = None
            ai_raw = g(f, "ai_remediation", None)
            if ai_raw:
                try:
                    ai_rem = json.loads(ai_raw) if isinstance(ai_raw, str) else ai_raw
                except Exception:
                    ai_rem = {"raw": str(ai_raw)}

            findings_data.append({
                "id": f_id,
                "control_id": g(f, "control_id") or g(f, "external_control_id", f_id),
                "title": g(f, "title", ""),
                "severity": (g(f, "severity", "") or "").upper(),
                "state": g(f, "state", ""),
                "category": g(f, "category", ""),
                "service": g(f, "service", ""),
                "description": g(f, "description", ""),
                "ai_remediation": ai_rem,
                "first_detected_at": str(g(f, "first_detected_at", "") or ""),
                "last_seen_at": str(g(f, "last_seen_at", "") or ""),
                "resolved_at": str(g(f, "resolved_at", "") or ""),
            })

        report = {
            "report_type": report_type,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tenant_id": self.tenant_id,
            "run_id": self._get_run_id(),
            "assessment": self.run if isinstance(self.run, dict) else None,
            "scores": {
                "security": self._get_run_attr("security_score"),
                "compliance": self._get_run_attr("compliance_score"),
                "risk": self._get_run_attr("risk_score"),
            },
            "summary": stats,
            "findings": findings_data,
        }

        output_path.write_text(
            json.dumps(report, indent=2, default=str),
            encoding="utf-8",
        )
        return str(output_path)
