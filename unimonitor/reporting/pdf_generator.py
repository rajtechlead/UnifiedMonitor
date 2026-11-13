"""PDF report generator using ReportLab."""

from __future__ import annotations

from datetime import UTC, datetime

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

UNIMONITOR_BLUE = (0.09, 0.46, 0.82)  # #1776D2
UNIMONITOR_DARK = (0.1, 0.12, 0.18)  # #1A1F2E


class PdfReportGenerator(BaseReportGenerator):
    """Generates PDF reports using ReportLab Platypus."""

    async def generate(self, report_type: str = "full") -> str:
        if not HAS_REPORTLAB:
            # Fallback: produce a minimal text-based PDF substitute
            return await self._generate_text_fallback()

        output_path = self._get_output_path("pdf")
        stats = self._summary_stats()

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        story = []

        # ── Cover / header ──────────────────────────────────────────────────
        title_style = ParagraphStyle(
            "Title",
            parent=styles["Heading1"],
            fontSize=24,
            textColor=colors.Color(*UNIMONITOR_BLUE),
            spaceAfter=6,
        )
        story.append(Paragraph("UniMonitor Security Assessment Report", title_style))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.Color(*UNIMONITOR_BLUE)))
        story.append(Spacer(1, 0.4 * cm))

        sub_style = ParagraphStyle("Sub", parent=styles["Normal"], fontSize=10, textColor=colors.grey)
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        story.append(Paragraph(f"Tenant: {self.tenant_id}  |  Run: {self.run.id}  |  Generated: {now}", sub_style))
        story.append(Spacer(1, 0.6 * cm))

        # ── Score summary table ──────────────────────────────────────────────
        h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=14, textColor=colors.Color(*UNIMONITOR_DARK))
        story.append(Paragraph("Executive Summary", h2))
        story.append(Spacer(1, 0.3 * cm))

        def score_cell(label: str, val: float | None) -> list:
            score_str = f"{val:.1f}" if val is not None else "N/A"
            return [label, score_str]

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

        # ── Severity breakdown ───────────────────────────────────────────────
        story.append(Paragraph("Finding Severity Breakdown", h2))
        story.append(Spacer(1, 0.3 * cm))
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
            rgb = SEVERITY_COLORS.get(sev, (1, 1, 1))
            sev_style.append(("BACKGROUND", (0, i), (0, i), colors.Color(*rgb, alpha=0.3)))
        sev_table.setStyle(TableStyle(sev_style))
        story.append(sev_table)
        story.append(Spacer(1, 0.8 * cm))

        # ── Findings table ───────────────────────────────────────────────────
        if report_type == "full":
            story.append(Paragraph("Findings Detail", h2))
            story.append(Spacer(1, 0.3 * cm))

            col_widths = [2.5 * cm, 7 * cm, 2.5 * cm, 4 * cm]
            findings_data = [["Control ID", "Title", "Severity", "Status"]]
            sorted_findings = sorted(
                self.findings,
                key=lambda f: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFORMATIONAL": 4}.get((f.severity or "INFORMATIONAL").upper(), 5),
            )
            cell_style = ParagraphStyle("cell", fontSize=8, wordWrap="CJK")
            for f in sorted_findings[:200]:  # cap at 200 rows
                sev = (getattr(f, "severity", "INFORMATIONAL") or "INFORMATIONAL").upper()
                state = getattr(f, "state", "not_implemented") or "not_implemented"
                findings_data.append(
                    [
                        Paragraph(getattr(f, "external_control_id", f.id[:8]), cell_style),
                        Paragraph(getattr(f, "title", "")[:120], cell_style),
                        Paragraph(sev, cell_style),
                        Paragraph(state.replace("_", " ").title(), cell_style),
                    ]
                )

            findings_table = Table(findings_data, colWidths=col_widths, repeatRows=1)
            f_style = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.Color(*UNIMONITOR_BLUE)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.97, 0.97)]),
            ]
            for i, row in enumerate(findings_data[1:], start=1):
                sev_text = row[2].text if hasattr(row[2], "text") else str(row[2])
                rgb = SEVERITY_COLORS.get(sev_text, (1, 1, 1))
                f_style.append(("BACKGROUND", (2, i), (2, i), colors.Color(*rgb, alpha=0.3)))
            findings_table.setStyle(TableStyle(f_style))
            story.append(findings_table)

        doc.build(story)
        return str(output_path)

    async def _generate_text_fallback(self) -> str:
        """Minimal text fallback when ReportLab not available."""
        output_path = self._get_output_path("txt")
        stats = self._summary_stats()
        lines = [
            "UniMonitor Security Assessment Report",
            "=" * 50,
            f"Tenant: {self.tenant_id}",
            f"Run ID: {self.run.id}",
            f"Security Score: {stats.get('security_score')}",
            f"Compliance Score: {stats.get('compliance_score')}",
            f"Total Findings: {stats['total_findings']}",
            "",
            "Severity Breakdown:",
        ]
        for sev, cnt in stats["severity_counts"].items():
            lines.append(f"  {sev}: {cnt}")
        output_path.write_text("\n".join(lines))
        return str(output_path)
