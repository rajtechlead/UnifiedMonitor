"""DOCX report generator using python-docx.

Keeps the aggregate single-org summary at the top and then breaks the report
down by cloud provider: a colour-coded coverage table followed by one section
per provider with its own score, control states and findings.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from unimonitor.reporting.base import BaseReportGenerator

try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor

    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

BRAND_BLUE = "1776D2"
DARK_TEXT = "1A1F2E"
SEVERITY_FILLS = {
    "CRITICAL": "FFCCCC",
    "HIGH": "FFE0CC",
    "MEDIUM": "FFFFCC",
    "LOW": "CCE0FF",
    "INFORMATIONAL": "E8E8E8",
}
SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFORMATIONAL": 4}
MAX_FINDINGS_PER_PROVIDER = 80


class DocxReportGenerator(BaseReportGenerator):
    """Generates Word documents using python-docx."""

    async def generate(self, report_type: str = "full") -> str:
        if not HAS_DOCX:
            raise RuntimeError("python-docx not installed; cannot generate DOCX reports")

        output_path = self._get_output_path("docx")
        stats = self._summary_stats()
        providers = self._provider_breakdown()

        doc = Document()

        title = doc.add_heading("UniMonitor Security Assessment Report", level=0)
        title.runs[0].font.color.rgb = RGBColor.from_string(BRAND_BLUE)

        meta = doc.add_paragraph()
        meta_run = meta.add_run(
            f"Tenant: {self.tenant_id}  |  Run: {self._get_run_id()}  |  Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}"
        )
        meta_run.font.size = Pt(9)
        meta_run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

        # ── Aggregate executive summary (single org, unchanged) ───────────────
        doc.add_heading("Executive Summary", level=1)
        score_rows = [
            ("Security Score", self._fmt(stats.get("security_score"))),
            ("Compliance Score", self._fmt(stats.get("compliance_score"))),
            ("Risk Score", self._fmt(stats.get("risk_score"))),
            ("Pass Rate", f"{stats['pass_rate']}%"),
            ("Total Findings", str(stats["total_findings"])),
        ]
        score_table = doc.add_table(rows=1, cols=2)
        score_table.style = "Table Grid"
        self._header_row(score_table, ["Metric", "Value"], BRAND_BLUE)
        for metric, value in score_rows:
            cells = score_table.add_row().cells
            cells[0].text = metric
            cells[1].text = value

        doc.add_heading("Finding Severity Breakdown", level=1)
        sev_table = doc.add_table(rows=1, cols=2)
        sev_table.style = "Table Grid"
        self._header_row(sev_table, ["Severity", "Count"], BRAND_BLUE)
        for sev, count in stats["severity_counts"].items():
            cells = sev_table.add_row().cells
            cells[0].text = sev
            cells[1].text = str(count)
            self._shade(cells[0], SEVERITY_FILLS.get(sev, "FFFFFF"))
            self._shade(cells[1], SEVERITY_FILLS.get(sev, "FFFFFF"))

        # ── Cloud provider coverage table (colour-coded per provider) ─────────
        if providers:
            doc.add_heading("Cloud Provider Coverage", level=1)
            prov_table = doc.add_table(rows=1, cols=6)
            prov_table.style = "Table Grid"
            self._header_row(
                prov_table,
                ["Provider", "Findings", "Critical", "High", "Coverage", "Score"],
                BRAND_BLUE,
            )
            for p in providers:
                cells = prov_table.add_row().cells
                cells[0].text = f"{p['short_name']} — {p['name']}"
                cells[1].text = str(p["total"])
                cells[2].text = str(p["severity_counts"]["CRITICAL"])
                cells[3].text = str(p["severity_counts"]["HIGH"])
                cells[4].text = f"{p['pass_rate']}%"
                cells[5].text = f"{p['security_score']:.1f}"
                self._shade(cells[0], p["colour"].lstrip("#"))
                for run in cells[0].paragraphs[0].runs:
                    run.font.bold = True
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

        # ── Per-provider sections ─────────────────────────────────────────────
        if report_type == "full" and providers:
            doc.add_heading("Findings by Cloud Provider", level=1)
            for p in providers:
                heading = doc.add_heading(p["name"], level=2)
                for run in heading.runs:
                    run.font.color.rgb = RGBColor.from_string(p["colour"].lstrip("#"))

                states = p["state_counts"]
                summary = doc.add_paragraph(
                    f"Score {p['security_score']:.1f}/100  |  Coverage {p['pass_rate']}%  |  "
                    f"{states['implemented']} implemented, {states['partially_implemented']} partial, "
                    f"{states['not_implemented']} not implemented, {states['not_applicable']} n/a  |  "
                    f"Severity: {p['severity_counts']['CRITICAL']} critical, "
                    f"{p['severity_counts']['HIGH']} high"
                )
                summary.runs[0].font.size = Pt(9)
                summary.runs[0].font.color.rgb = RGBColor(0x4B, 0x5A, 0x7A)

                findings = sorted(
                    p["findings"],
                    key=lambda f: SEVERITY_ORDER.get((self._get_finding_attr(f, "severity", "INFORMATIONAL") or "INFORMATIONAL").upper(), 5),
                )
                table = doc.add_table(rows=1, cols=4)
                table.style = "Table Grid"
                self._header_row(table, ["Control ID", "Title", "Severity", "Status"], p["colour"].lstrip("#"))
                for f in findings[:MAX_FINDINGS_PER_PROVIDER]:
                    severity = (self._get_finding_attr(f, "severity", "INFORMATIONAL") or "INFORMATIONAL").upper()
                    state = self._get_finding_attr(f, "state", "not_implemented") or "not_implemented"
                    cells = table.add_row().cells
                    cells[0].text = str(self._get_finding_attr(f, "external_control_id", "") or "")
                    cells[1].text = (self._get_finding_attr(f, "title", "") or "")[:200]
                    cells[2].text = severity
                    cells[3].text = state.replace("_", " ").title()
                    self._shade(cells[2], SEVERITY_FILLS.get(severity, "FFFFFF"))

        # ── Aggregate findings detail ─────────────────────────────────────────
        if report_type == "full":
            doc.add_heading("All Findings", level=1)
            table = doc.add_table(rows=1, cols=4)
            table.style = "Table Grid"
            self._header_row(table, ["Control ID", "Title", "Severity", "Status"], BRAND_BLUE)
            ordered = sorted(
                self.findings,
                key=lambda f: SEVERITY_ORDER.get((self._get_finding_attr(f, "severity", "INFORMATIONAL") or "INFORMATIONAL").upper(), 5),
            )
            for f in ordered[:200]:
                severity = (self._get_finding_attr(f, "severity", "INFORMATIONAL") or "INFORMATIONAL").upper()
                state = self._get_finding_attr(f, "state", "not_implemented") or "not_implemented"
                cells = table.add_row().cells
                cells[0].text = str(self._get_finding_attr(f, "external_control_id", "") or "")
                cells[1].text = (self._get_finding_attr(f, "title", "") or "")[:200]
                cells[2].text = severity
                cells[3].text = state.replace("_", " ").title()
                self._shade(cells[2], SEVERITY_FILLS.get(severity, "FFFFFF"))

        doc.save(str(output_path))
        return str(output_path)

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _fmt(value: Any) -> str:
        return f"{value:.1f}" if isinstance(value, int | float) else "N/A"

    def _header_row(self, table: Any, labels: list[str], fill: str) -> None:
        for idx, label in enumerate(labels):
            cell = table.rows[0].cells[idx]
            cell.text = label
            self._shade(cell, fill)
            for run in cell.paragraphs[0].runs:
                run.font.bold = True
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT

    @staticmethod
    def _shade(cell: Any, hex_fill: str) -> None:
        """Apply a solid background fill to a table cell."""
        shading = OxmlElement("w:shd")
        shading.set(qn("w:val"), "clear")
        shading.set(qn("w:color"), "auto")
        shading.set(qn("w:fill"), hex_fill.zfill(6).upper())
        cell._tc.get_or_add_tcPr().append(shading)
