"""PDF report generator using ReportLab."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from unimonitor.reporting.base import BaseReportGenerator

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

SEVERITY_COLORS = {
    "CRITICAL": (0.9, 0.1, 0.1),
    "HIGH": (0.95, 0.5, 0.1),
    "MEDIUM": (0.95, 0.85, 0.1),
    "LOW": (0.4, 0.6, 0.9),
    "INFORMATIONAL": (0.7, 0.7, 0.7),
}

SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFORMATIONAL": 4}

MAX_FINDINGS = 200
MAX_PROVIDER_FINDINGS = 80

UNIMONITOR_BLUE = (0.09, 0.46, 0.82)  # #1776D2
UNIMONITOR_DARK = (0.1, 0.12, 0.18)  # #1A1F2E


def _severity_of(value: Any) -> str:
    return (value or "INFORMATIONAL").upper()


def _finding_table(rows: list[list[Any]], header_colour: tuple[float, float, float]) -> Any:
    """A findings table: coloured header, severity-tinted third column."""
    table = Table(rows, colWidths=[2.5 * cm, 7 * cm, 2.5 * cm, 4 * cm], repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(*header_colour)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.97, 0.97)]),
    ]
    for i, row in enumerate(rows[1:], start=1):
        severity = row[2].text if hasattr(row[2], "text") else str(row[2])
        style.append(("BACKGROUND", (2, i), (2, i), colors.Color(*SEVERITY_COLORS.get(severity, (1, 1, 1)), alpha=0.3)))
    table.setStyle(TableStyle(style))
    return table


class PdfReportGenerator(BaseReportGenerator):
    """Generates PDF reports using ReportLab Platypus."""

    async def generate(self, report_type: str = "full") -> str:
        if not HAS_REPORTLAB:
            # Fallback: produce a minimal text-based PDF substitute
            return self._generate_text_fallback()

        output_path = self._get_output_path("pdf")
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        story: list[Any] = []

        h2 = self._add_cover(story, styles)
        self._add_score_summary(story, self._summary_stats(), h2)

        providers = self._provider_breakdown()
        self._add_provider_summary(story, providers, h2)

        if report_type == "full":
            self._add_findings_detail(story, h2)

        if providers:
            self._add_provider_sections(story, providers, h2)

        doc.build(story)
        return str(output_path)

    # ── Sections ─────────────────────────────────────────────────────────────

    def _add_cover(self, story: list[Any], styles: Any) -> Any:
        """Title block and tenant/run metadata; returns the section heading style."""
        title_style = ParagraphStyle(
            "Title",
            parent=styles["Heading1"],
            fontSize=24,
            textColor=colors.Color(*UNIMONITOR_BLUE),
            spaceAfter=6,
        )
        story.extend(
            [
                Paragraph("UniMonitor Security Assessment Report", title_style),
                HRFlowable(width="100%", thickness=2, color=colors.Color(*UNIMONITOR_BLUE)),
                Spacer(1, 0.4 * cm),
            ]
        )

        sub_style = ParagraphStyle("Sub", parent=styles["Normal"], fontSize=10, textColor=colors.grey)
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        story.append(Paragraph(f"Tenant: {self.tenant_id}  |  Run: {self._get_run_id()}  |  Generated: {now}", sub_style))
        story.append(Spacer(1, 0.6 * cm))

        return ParagraphStyle("H2", parent=styles["Heading2"], fontSize=14, textColor=colors.Color(*UNIMONITOR_DARK))

    def _add_score_summary(self, story: list[Any], stats: dict[str, Any], h2: Any) -> None:
        """Executive summary table plus the severity breakdown."""
        story.extend([Paragraph("Executive Summary", h2), Spacer(1, 0.3 * cm)])

        def score_cell(label: str, val: float | None) -> list:
            return [label, f"{val:.1f}" if val is not None else "N/A"]

        score_data = [
            ["Metric", "Score"],
            score_cell("Security Score", stats.get("security_score")),
            score_cell("Compliance Score", stats.get("compliance_score")),
            score_cell("Risk Score", stats.get("risk_score")),
            ["Pass Rate", f"{stats['pass_rate']}%"],
            ["Total Findings", str(stats["total_findings"])],
        ]
        score_table = Table(score_data, colWidths=[8 * cm, 4 * cm])
        score_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.Color(*UNIMONITOR_BLUE)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.97, 1)]),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(score_table)
        story.append(Spacer(1, 0.6 * cm))

        story.extend([Paragraph("Finding Severity Breakdown", h2), Spacer(1, 0.3 * cm)])
        sev_data = [["Severity", "Count"]] + [[sev, str(cnt)] for sev, cnt in stats["severity_counts"].items()]
        sev_table = Table(sev_data, colWidths=[8 * cm, 4 * cm])
        sev_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.Color(*UNIMONITOR_BLUE)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]
        for i, (sev, _) in enumerate(stats["severity_counts"].items(), start=1):
            sev_style.append(("BACKGROUND", (0, i), (0, i), colors.Color(*SEVERITY_COLORS.get(sev, (1, 1, 1)), alpha=0.3)))
        sev_table.setStyle(TableStyle(sev_style))
        story.append(sev_table)
        story.append(Spacer(1, 0.8 * cm))

    @staticmethod
    def _add_provider_summary(story: list[Any], providers: list[dict[str, Any]], h2: Any) -> None:
        """Cloud coverage table; the aggregate figures above stay as they are."""
        if not providers:
            return

        story.append(Paragraph("Cloud Provider Coverage", h2))
        story.append(Spacer(1, 0.3 * cm))
        prov_cell_style = ParagraphStyle("provcell", fontSize=9, wordWrap="CJK")
        rows = [["Provider", "Findings", "Critical", "High", "Coverage", "Score"]]
        for p in providers:
            rows.append(
                [
                    Paragraph(f"<b>{p['short_name']}</b> — {p['name']}", prov_cell_style),
                    str(p["total"]),
                    str(p["severity_counts"]["CRITICAL"]),
                    str(p["severity_counts"]["HIGH"]),
                    f"{p['pass_rate']}%",
                    f"{p['security_score']:.1f}",
                ]
            )
        table = Table(rows, colWidths=[6.2 * cm, 2 * cm, 1.9 * cm, 1.6 * cm, 2.1 * cm, 1.9 * cm])
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.Color(*UNIMONITOR_BLUE)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        for i, p in enumerate(providers, start=1):
            style.append(("LINEBEFORE", (0, i), (0, i), 6, colors.Color(*p["rgb"])))
            style.append(("BACKGROUND", (0, i), (0, i), colors.Color(*p["rgb"], alpha=0.12)))
        table.setStyle(TableStyle(style))
        story.append(table)
        story.append(Spacer(1, 0.8 * cm))

    def _finding_rows(self, findings: list[Any], limit: int, getter: Any) -> list[list[Any]]:
        """Header row plus one row per finding, using *getter* to read attributes."""
        cell_style = ParagraphStyle("cell", fontSize=8, wordWrap="CJK")
        rows: list[list[Any]] = [["Control ID", "Title", "Severity", "Status"]]
        for f in findings[:limit]:
            severity = _severity_of(getter(f, "severity", "INFORMATIONAL"))
            state = getter(f, "state", "not_implemented") or "not_implemented"
            control_ref = getter(f, "external_control_id", "") or str(getter(f, "id", ""))[:8]
            rows.append(
                [
                    Paragraph(control_ref, cell_style),
                    Paragraph((getter(f, "title", "") or "")[:120], cell_style),
                    Paragraph(severity, cell_style),
                    Paragraph(state.replace("_", " ").title(), cell_style),
                ]
            )
        return rows

    def _add_findings_detail(self, story: list[Any], h2: Any) -> None:
        """The aggregate findings table for a full report."""
        story.append(Paragraph("Findings Detail", h2))
        story.append(Spacer(1, 0.3 * cm))
        ordered = sorted(self.findings, key=lambda f: SEVERITY_RANK.get(_severity_of(self._get_finding_attr(f, "severity", "INFORMATIONAL")), 5))
        story.append(_finding_table(self._finding_rows(ordered, MAX_FINDINGS, self._get_finding_attr), UNIMONITOR_BLUE))

    def _add_provider_sections(self, story: list[Any], providers: list[dict[str, Any]], h2: Any) -> None:
        """One heading, score line and findings table per cloud provider."""
        sub_style = ParagraphStyle("Sub", fontSize=10, textColor=colors.grey)
        story.append(Spacer(1, 0.8 * cm))
        story.append(Paragraph("Findings by Cloud Provider", h2))

        for p in providers:
            story.append(Spacer(1, 0.4 * cm))
            heading = ParagraphStyle(f"prov-{p['id']}", parent=h2, fontSize=12, textColor=colors.Color(*p["rgb"]))
            story.append(Paragraph(p["name"], heading))

            states = p["state_counts"]
            story.append(
                Paragraph(
                    f"Score {p['security_score']:.1f}/100  |  Coverage {p['pass_rate']}%  |  "
                    f"{states['implemented']} implemented, {states['partially_implemented']} partial, "
                    f"{states['not_implemented']} not implemented, {states['not_applicable']} n/a  |  "
                    f"Severity: {p['severity_counts']['CRITICAL']} critical, {p['severity_counts']['HIGH']} high",
                    sub_style,
                )
            )
            story.append(Spacer(1, 0.2 * cm))

            ordered = sorted(p["findings"], key=lambda f: SEVERITY_RANK.get(_severity_of(getattr(f, "severity", "INFORMATIONAL")), 5))
            story.append(_finding_table(self._finding_rows(ordered, MAX_PROVIDER_FINDINGS, getattr), p["rgb"]))

    def _generate_text_fallback(self) -> str:
        """Minimal text fallback when ReportLab not available."""
        output_path = self._get_output_path("txt")
        stats = self._summary_stats()
        lines = [
            "UniMonitor Security Assessment Report",
            "=" * 50,
            f"Tenant: {self.tenant_id}",
            f"Run ID: {self._get_run_id()}",
            f"Security Score: {stats.get('security_score')}",
            f"Compliance Score: {stats.get('compliance_score')}",
            f"Total Findings: {stats['total_findings']}",
            "",
            "Severity Breakdown:",
        ]
        for sev, cnt in stats["severity_counts"].items():
            lines.append(f"  {sev}: {cnt}")
        providers = self._provider_breakdown()
        if providers:
            lines.extend(["", "Cloud Provider Breakdown:"])
            for p in providers:
                lines.append(
                    f"  {p['name']}: {p['total']} findings, score {p['security_score']:.1f},"
                    f" coverage {p['pass_rate']}%, {p['severity_counts']['CRITICAL']} critical,"
                    f" {p['severity_counts']['HIGH']} high"
                )
        output_path.write_text("\n".join(lines))
        return str(output_path)
