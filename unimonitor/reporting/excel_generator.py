"""Excel report generator using openpyxl."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from unimonitor.reporting.base import BaseReportGenerator

try:
    import openpyxl
    from openpyxl.styles import (
        Alignment,
        Font,
        PatternFill,
    )
    from openpyxl.utils import get_column_letter

    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

SEVERITY_FILLS = {
    "CRITICAL": "FFCCCC",
    "HIGH": "FFE0CC",
    "MEDIUM": "FFFFCC",
    "LOW": "CCE0FF",
    "INFORMATIONAL": "E8E8E8",
}
HEADER_FILL = "1776D2"
HEADER_FONT_COLOR = "FFFFFF"


class ExcelReportGenerator(BaseReportGenerator):
    """Generates Excel workbooks using openpyxl."""

    def generate(self, report_type: str = "full") -> str:
        if not HAS_OPENPYXL:
            raise RuntimeError("openpyxl not installed; cannot generate Excel reports")

        output_path = self._get_output_path("xlsx")
        stats = self._summary_stats()
        wb = openpyxl.Workbook()

        self._write_summary_sheet(wb, stats)
        self._write_findings_sheet(wb)
        self._write_framework_sheet(wb)

        # Remove default empty sheet
        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

        wb.save(str(output_path))
        return str(output_path)

    def _header_style(self, ws, row: int, columns: list[str]) -> None:
        fill = PatternFill(fill_type="solid", fgColor=HEADER_FILL)
        font = Font(color=HEADER_FONT_COLOR, bold=True)
        for col_idx, header in enumerate(columns, 1):
            cell = ws.cell(row=row, column=col_idx, value=header)
            cell.fill = fill
            cell.font = font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    def _auto_width(self, ws) -> None:
        for column in ws.columns:
            max_len = 0
            col_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    max_len = max(max_len, len(str(cell.value or "")))
                except Exception:  # noqa: S110
                    pass
            ws.column_dimensions[col_letter].width = min(max_len + 4, 50)

    def _write_summary_sheet(self, wb, stats: dict) -> None:
        ws = wb.create_sheet("Executive Summary")
        ws.sheet_view.showGridLines = False

        # Title
        ws["A1"] = "UniMonitor Security Assessment Report"
        ws["A1"].font = Font(size=16, bold=True, color="1776D2")
        ws.merge_cells("A1:D1")

        ws["A2"] = f"Tenant: {self.tenant_id}  |  Run: {self._get_run_id()}"
        ws["A2"].font = Font(size=10, color="666666")
        ws.merge_cells("A2:D2")

        ws["A3"] = f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}"
        ws["A3"].font = Font(size=10, color="666666")
        ws.merge_cells("A3:D3")

        # Scores section
        row = 5
        self._header_style(ws, row, ["Metric", "Value"])
        score_rows = [
            ("Security Score", f"{stats.get('security_score') or 0:.1f} / 100"),
            ("Compliance Score", f"{stats.get('compliance_score') or 0:.1f} / 100"),
            ("Risk Score", f"{stats.get('risk_score') or 0:.1f} / 100"),
            ("Pass Rate", f"{stats['pass_rate']}%"),
            ("Total Findings", stats["total_findings"]),
        ]
        for i, (metric, val) in enumerate(score_rows, start=row + 1):
            ws.cell(row=i, column=1, value=metric)
            ws.cell(row=i, column=2, value=val)
            if i % 2 == 0:
                for col in [1, 2]:
                    ws.cell(row=i, column=col).fill = PatternFill(fill_type="solid", fgColor="F0F4FF")

        # Severity breakdown
        row = 13
        ws.cell(row=row - 1, column=1, value="Severity Breakdown").font = Font(bold=True, size=12)
        self._header_style(ws, row, ["Severity", "Count"])
        for i, (sev, cnt) in enumerate(stats["severity_counts"].items(), start=row + 1):
            ws.cell(row=i, column=1, value=sev)
            ws.cell(row=i, column=2, value=cnt)
            fill_color = SEVERITY_FILLS.get(sev, "FFFFFF")
            for col in [1, 2]:
                ws.cell(row=i, column=col).fill = PatternFill(fill_type="solid", fgColor=fill_color)

        self._auto_width(ws)

    def _write_findings_sheet(self, wb) -> None:
        ws = wb.create_sheet("Findings")
        headers = ["Control ID", "Title", "Severity", "Status", "Category", "Service", "Description", "Remediation"]
        self._header_style(ws, 1, headers)

        sorted_findings = sorted(
            self.findings,
            key=lambda f: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFORMATIONAL": 4}.get(
                (self._get_finding_attr(f, "severity", "INFORMATIONAL") or "INFORMATIONAL").upper(), 5
            ),
        )

        for row_idx, f in enumerate(sorted_findings, start=2):
            g = self._get_finding_attr
            f_id = g(f, "id", "unknown")
            sev = (g(f, "severity", "INFORMATIONAL") or "INFORMATIONAL").upper()
            row = [
                g(f, "control_id") or g(f, "external_control_id", f_id[:8]),
                g(f, "title", ""),
                sev,
                (g(f, "state", "") or "").replace("_", " ").title(),
                g(f, "category", ""),
                g(f, "service", ""),
                g(f, "description", ""),
                g(f, "remediation_text", "") or "",
            ]
            fill_color = SEVERITY_FILLS.get(sev, "FFFFFF")
            for col_idx, val in enumerate(row, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=str(val or ""))
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                if col_idx == 3:  # Severity column
                    cell.fill = PatternFill(fill_type="solid", fgColor=fill_color)

        ws.row_dimensions[1].height = 20
        self._auto_width(ws)
        ws.freeze_panes = "A2"

    def _write_framework_sheet(self, wb) -> None:
        ws = wb.create_sheet("Framework Coverage")
        headers = ["Framework", "Total Controls", "Implemented", "Partial", "Not Implemented", "N/A", "Coverage %"]
        self._header_style(ws, 1, headers)

        # Aggregate by framework_ids field
        framework_stats: dict[str, dict[str, int]] = {}
        for f in self.findings:
            fw_ids_raw = self._get_finding_attr(f, "framework_ids", "[]") or "[]"
            try:
                fw_ids = json.loads(fw_ids_raw) if isinstance(fw_ids_raw, str) else fw_ids_raw
            except Exception:
                fw_ids = []
            state = getattr(f, "state", "not_implemented") or "not_implemented"
            for fw in fw_ids:
                if fw not in framework_stats:
                    framework_stats[fw] = {"total": 0, "implemented": 0, "partially_implemented": 0, "not_implemented": 0, "not_applicable": 0}
                framework_stats[fw]["total"] += 1
                framework_stats[fw][state] = framework_stats[fw].get(state, 0) + 1

        for row_idx, (fw, counts) in enumerate(sorted(framework_stats.items()), start=2):
            total = counts["total"]
            impl = counts.get("implemented", 0)
            partial = counts.get("partially_implemented", 0)
            not_impl = counts.get("not_implemented", 0)
            na = counts.get("not_applicable", 0)
            coverage = round((impl + na) / total * 100, 1) if total else 0
            row_vals = [fw.upper(), total, impl, partial, not_impl, na, f"{coverage}%"]
            for col_idx, val in enumerate(row_vals, 1):
                ws.cell(row=row_idx, column=col_idx, value=val)
            if row_idx % 2 == 0:
                for col in range(1, len(row_vals) + 1):
                    ws.cell(row=row_idx, column=col).fill = PatternFill(fill_type="solid", fgColor="F0F4FF")

        self._auto_width(ws)
