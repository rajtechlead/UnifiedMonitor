"""Scorecard exporters produce real files from the gathered document."""

from __future__ import annotations

import csv
import io

import pytest

from unimonitor.reporting.scorecard import CONTROL_COLUMNS, export, to_csv, to_pdf, to_xlsx


def _scorecard() -> dict:
    return {
        "generated_at": "2026-11-21T00:00:00+00:00",
        "tenant_id": "tenant-1",
        "run_id": None,
        "scores": {"security_score": 72.5, "compliance_score": 68.0, "risk_score": 70.0},
        "counts": {"critical": 1, "high": 0, "medium": 1, "low": 0, "informational": 0},
        "controls": [
            {
                "control_id": "CTRL-1",
                "external_control_id": "CIS-1.1",
                "title": "MFA enforced",
                "severity": "critical",
                "category": "Identity",
                "service": "entra_id",
                "state": "not_implemented",
                "risk_score": 90,
                "triage_status": "open",
                "first_detected_at": "2026-11-01T00:00:00+00:00",
            }
        ],
        "frameworks": [
            {
                "framework_id": "iso27001",
                "coverage_pct": 62.5,
                "controls_total": 8,
                "controls_implemented": 5,
                "controls_partially_implemented": 0,
                "controls_not_implemented": 3,
                "controls_not_applicable": 0,
            }
        ],
    }


def test_csv_round_trips_the_control_rows():
    rows = list(csv.DictReader(io.StringIO(to_csv(_scorecard()).decode("utf-8"))))
    assert list(rows[0]) == list(CONTROL_COLUMNS)
    assert rows[0]["external_control_id"] == "CIS-1.1"
    assert rows[0]["severity"] == "critical"


def test_xlsx_is_a_real_workbook():
    content = to_xlsx(_scorecard())
    assert content[:2] == b"PK", "an xlsx file is a zip container"
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(content))
    assert set(workbook.sheetnames) == {"Summary", "Controls", "Frameworks"}


def test_pdf_is_a_real_document():
    content = to_pdf(_scorecard())
    assert content.startswith(b"%PDF")


def test_export_returns_media_type_and_filename():
    content, media_type, filename = export(_scorecard(), "csv")
    assert content and media_type == "text/csv"
    assert filename.endswith(".csv")


def test_export_rejects_unknown_format():
    with pytest.raises(ValueError):
        export(_scorecard(), "docx")
