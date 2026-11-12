"""CSV report generator."""

from __future__ import annotations

import csv

from unimonitor.reporting.base import BaseReportGenerator


class CsvReportGenerator(BaseReportGenerator):
    """Generates CSV reports with all finding data."""

    def generate(self, report_type: str = "full") -> str:
        output_path = self._get_output_path("csv")
        fieldnames = [
            "id", "control_id", "title", "severity", "state",
            "category", "service", "description", "first_detected_at",
            "last_seen_at", "resolved_at",
        ]

        with output_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for f in self.findings:
                g = self._get_finding_attr
                f_id = g(f, "id", "")
                writer.writerow({
                    "id": f_id,
                    "control_id": g(f, "control_id") or g(f, "external_control_id", f_id),
                    "title": g(f, "title", ""),
                    "severity": (g(f, "severity", "") or "").upper(),
                    "state": g(f, "state", ""),
                    "category": g(f, "category", ""),
                    "service": g(f, "service", ""),
                    "description": g(f, "description", ""),
                    "first_detected_at": str(g(f, "first_detected_at", "") or ""),
                    "last_seen_at": str(g(f, "last_seen_at", "") or ""),
                    "resolved_at": str(g(f, "resolved_at", "") or ""),
                })
        return str(output_path)
