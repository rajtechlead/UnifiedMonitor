"""Scorecard export — a control-level file in CSV, XLSX or PDF.

The scorecard is generated synchronously because it reads what is already stored:
a worker hop would only delay a file the user is waiting for. Every value comes
from persisted findings and framework coverage; nothing is recalculated from a
template or filled with placeholder numbers.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import Any

SEVERITIES = ("critical", "high", "medium", "low", "informational")
CONTROL_COLUMNS = (
    "control_id",
    "external_control_id",
    "title",
    "severity",
    "category",
    "service",
    "state",
    "risk_score",
    "triage_status",
    "first_detected_at",
)

TABLE_STYLE = [("GRID", (0, 0), (-1, -1), 0.25, "grey"), ("BACKGROUND", (0, 0), (-1, 0), "whitesmoke")]

SCORECARD_TITLE = "UniMonitor scorecard"

MEDIA_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


async def gather(session: Any, tenant_id: str | None = None, run_id: str | None = None) -> dict[str, Any]:
    """Collect the data every exporter shares."""
    from sqlalchemy import select

    from unimonitor.db.models.finding import Finding
    from unimonitor.grc.scoring import calculate_scores, compute_framework_coverage

    stmt = select(Finding)
    if run_id:
        stmt = stmt.where(Finding.assessment_run_id == run_id)
    elif tenant_id:
        stmt = stmt.where(Finding.tenant_id == tenant_id)
    findings = list((await session.execute(stmt)).scalars())

    coverage = await compute_framework_coverage(session, tenant_id=tenant_id)
    frameworks = [
        {
            "framework_id": framework_id,
            "coverage_pct": round(float(values.get("coverage_pct", 0.0)), 2),
            "controls_total": values.get("controls_total", 0),
            "controls_implemented": values.get("controls_implemented", 0),
            "controls_partially_implemented": values.get("controls_partially_implemented", values.get("controls_partial", 0)),
            "controls_not_implemented": values.get("controls_not_implemented", 0),
            "controls_not_applicable": values.get("controls_not_applicable", 0),
        }
        for framework_id, values in sorted(coverage.items())
    ]

    controls = [
        {
            "control_id": finding.control_id or "",
            "external_control_id": finding.external_control_id,
            "title": finding.title,
            "severity": str(finding.severity).lower(),
            "category": finding.category,
            "service": finding.service,
            "state": finding.state,
            "risk_score": finding.risk_score,
            "triage_status": finding.triage_status,
            "first_detected_at": finding.first_detected_at.isoformat() if finding.first_detected_at else "",
        }
        for finding in findings
    ]

    scores = calculate_scores(findings)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "tenant_id": tenant_id,
        "run_id": run_id,
        "scores": {key: scores[key] for key in scores if key.endswith("_score")},
        "counts": {severity: sum(1 for row in controls if row["severity"] == severity) for severity in SEVERITIES},
        "controls": controls,
        "frameworks": frameworks,
    }


def to_csv(scorecard: dict[str, Any]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(CONTROL_COLUMNS), extrasaction="ignore")
    writer.writeheader()
    for row in scorecard["controls"]:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def to_xlsx(scorecard: dict[str, Any]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    workbook = Workbook()
    summary = workbook.active
    summary.title = "Summary"
    summary.append([SCORECARD_TITLE])
    summary["A1"].font = Font(bold=True, size=14)
    summary.append(["Generated", scorecard["generated_at"]])
    summary.append(["Tenant", scorecard["tenant_id"] or "all"])
    summary.append(["Assessment run", scorecard["run_id"] or "current state"])
    summary.append([])
    summary.append(["Score", "Value"])
    for key, value in scorecard["scores"].items():
        summary.append([key, value])
    summary.append([])
    summary.append(["Severity", "Findings"])
    for severity, count in scorecard["counts"].items():
        summary.append([severity, count])

    controls = workbook.create_sheet("Controls")
    controls.append(list(CONTROL_COLUMNS))
    for cell in controls[1]:
        cell.font = Font(bold=True)
    for row in scorecard["controls"]:
        controls.append([row[column] for column in CONTROL_COLUMNS])
    controls.freeze_panes = "A2"

    frameworks = workbook.create_sheet("Frameworks")
    framework_columns = (
        "framework_id",
        "coverage_pct",
        "controls_total",
        "controls_implemented",
        "controls_partially_implemented",
        "controls_not_implemented",
        "controls_not_applicable",
    )
    frameworks.append(list(framework_columns))
    for cell in frameworks[1]:
        cell.font = Font(bold=True)
    for row in scorecard["frameworks"]:
        frameworks.append([row[column] for column in framework_columns])

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def to_pdf(scorecard: dict[str, Any]) -> bytes:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=landscape(A4), title=SCORECARD_TITLE)
    styles = getSampleStyleSheet()
    story: list[Any] = [
        Paragraph(SCORECARD_TITLE, styles["Title"]),
        Paragraph(f"Generated {scorecard['generated_at']}", styles["Normal"]),
        Spacer(1, 12),
    ]

    score_rows = [[key, f"{value:.2f}" if isinstance(value, float) else str(value)] for key, value in scorecard["scores"].items()]
    summary_rows = [["Score", "Value"], *score_rows]
    summary_rows.append(["---", "---"])
    summary_rows.extend([["findings " + severity, str(count)] for severity, count in scorecard["counts"].items()])
    summary_table = Table(summary_rows, hAlign="LEFT")
    summary_table.setStyle(TableStyle(TABLE_STYLE))
    story.append(summary_table)
    story.append(Spacer(1, 16))

    framework_rows = [["Framework", "Coverage %", "Total", "Implemented", "Partial", "Open"]]
    framework_rows.extend(
        [
            [
                row["framework_id"],
                f"{row['coverage_pct']:.2f}",
                str(row["controls_total"]),
                str(row["controls_implemented"]),
                str(row["controls_partially_implemented"]),
                str(row["controls_not_implemented"]),
            ]
            for row in scorecard["frameworks"]
        ]
    )
    if len(framework_rows) > 1:
        table = Table(framework_rows, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle(TABLE_STYLE))
        story.extend([Paragraph("Framework coverage", styles["Heading2"]), table, Spacer(1, 16)])

    control_rows = [["Control", "Severity", "State", "Title"]]
    ordered = sorted(
        scorecard["controls"],
        key=lambda row: (SEVERITIES.index(row["severity"]) if row["severity"] in SEVERITIES else len(SEVERITIES), row["control_id"]),
    )
    for row in ordered[:300]:
        control_rows.append([row["external_control_id"], row["severity"], row["state"], row["title"][:80]])
    if len(control_rows) > 1:
        table = Table(control_rows, repeatRows=1, colWidths=[100, 60, 90, 420], hAlign="LEFT")
        table.setStyle(TableStyle(TABLE_STYLE))
        story.extend([Paragraph("Controls", styles["Heading2"]), table])

    document.build(story)
    return buffer.getvalue()


def export(scorecard: dict[str, Any], fmt: str) -> tuple[bytes, str, str]:
    """Return ``(content, media_type, filename)`` for one format."""
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    filename = f"unimonitor-scorecard-{stamp}.{fmt}"
    if fmt == "csv":
        return to_csv(scorecard), MEDIA_TYPES["csv"], filename
    if fmt == "xlsx":
        return to_xlsx(scorecard), MEDIA_TYPES["xlsx"], filename
    if fmt == "pdf":
        return to_pdf(scorecard), MEDIA_TYPES["pdf"], filename
    raise ValueError(f"Unsupported scorecard format: {fmt}")


__all__ = ["CONTROL_COLUMNS", "MEDIA_TYPES", "export", "gather", "to_csv", "to_pdf", "to_xlsx"]
