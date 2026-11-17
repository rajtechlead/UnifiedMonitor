"""
Unit tests for the reporting generators.
"""

import csv
import json
from pathlib import Path

import pytest

SAMPLE_RUN = {
    "id": "run-00000001",
    "assessment_name": "Test Assessment",
    "tenant_name": "Test Corp",
    "started_at": "2026-01-01T00:00:00Z",
    "completed_at": "2026-01-01T00:05:00Z",
    "frameworks": ["iso_27001_2022"],
    "total_controls": 10,
    "findings_count": 3,
    "score": 72,
}

SAMPLE_FINDINGS = [
    {
        "id": "finding-001",
        "control_id": "CTRL-ENT-001",
        "title": "MFA not enabled",
        "description": "Multi-factor authentication is not enforced",
        "severity": "CRITICAL",
        "state": "not_implemented",
        "framework": "iso_27001_2022",
        "framework_control": "A.9.4.2",
        "evidence_summary": "15 accounts without MFA",
        "ai_remediation": {"summary": "Enable MFA via Conditional Access", "steps": ["Step 1"]},
        "created_at": "2026-01-01T00:00:00Z",
    },
    {
        "id": "finding-002",
        "control_id": "CTRL-DEV-001",
        "title": "Device compliance not configured",
        "description": "No compliance policies assigned",
        "severity": "HIGH",
        "state": "partially_implemented",
        "framework": "iso_27001_2022",
        "framework_control": "A.6.2.1",
        "evidence_summary": "Compliance policies exist but not assigned",
        "ai_remediation": None,
        "created_at": "2026-01-01T00:01:00Z",
    },
]


class TestCsvGenerator:
    def test_csv_generates_successfully(self, tmp_path: Path):
        """CSV generator produces a valid CSV file."""
        from unimonitor.reporting.csv_generator import CsvReportGenerator

        gen = CsvReportGenerator(
            run=SAMPLE_RUN,
            findings=SAMPLE_FINDINGS,
            output_dir=str(tmp_path),
            tenant_id="test-tenant",
        )
        path = gen.generate()
        assert Path(path).exists()

    def test_csv_has_header_row(self, tmp_path: Path):
        """CSV file has a header row with expected columns."""
        from unimonitor.reporting.csv_generator import CsvReportGenerator

        gen = CsvReportGenerator(
            run=SAMPLE_RUN,
            findings=SAMPLE_FINDINGS,
            output_dir=str(tmp_path),
            tenant_id="test-tenant",
        )
        path = gen.generate()
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []

        for col in ["control_id", "title", "severity", "state"]:
            assert col in headers, f"Missing column: {col}"

    def test_csv_contains_all_findings(self, tmp_path: Path):
        """CSV contains one data row per finding."""
        from unimonitor.reporting.csv_generator import CsvReportGenerator

        gen = CsvReportGenerator(
            run=SAMPLE_RUN,
            findings=SAMPLE_FINDINGS,
            output_dir=str(tmp_path),
            tenant_id="test-tenant",
        )
        path = gen.generate()
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == len(SAMPLE_FINDINGS)


class TestJsonGenerator:
    def test_json_generates_valid_file(self, tmp_path: Path):
        """JSON generator produces valid JSON."""
        from unimonitor.reporting.json_generator import JsonReportGenerator

        gen = JsonReportGenerator(
            run=SAMPLE_RUN,
            findings=SAMPLE_FINDINGS,
            output_dir=str(tmp_path),
            tenant_id="test-tenant",
        )
        path = gen.generate()
        assert Path(path).exists()
        with open(path) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_json_includes_run_and_findings(self, tmp_path: Path):
        """JSON output includes both run metadata and findings array."""
        from unimonitor.reporting.json_generator import JsonReportGenerator

        gen = JsonReportGenerator(
            run=SAMPLE_RUN,
            findings=SAMPLE_FINDINGS,
            output_dir=str(tmp_path),
            tenant_id="test-tenant",
        )
        path = gen.generate()
        with open(path) as f:
            data = json.load(f)

        assert "run" in data or "assessment" in data
        assert "findings" in data
        assert len(data["findings"]) == len(SAMPLE_FINDINGS)

    def test_json_includes_ai_remediation(self, tmp_path: Path):
        """JSON output preserves ai_remediation field."""
        from unimonitor.reporting.json_generator import JsonReportGenerator

        gen = JsonReportGenerator(
            run=SAMPLE_RUN,
            findings=SAMPLE_FINDINGS,
            output_dir=str(tmp_path),
            tenant_id="test-tenant",
        )
        path = gen.generate()
        with open(path) as f:
            data = json.load(f)

        finding_with_ai = next((f for f in data["findings"] if f.get("ai_remediation")), None)
        assert finding_with_ai is not None


class TestExcelGenerator:
    def test_excel_generates_successfully(self, tmp_path: Path):
        """Excel generator produces a .xlsx file without errors."""
        pytest.importorskip("openpyxl")
        from unimonitor.reporting.excel_generator import ExcelReportGenerator

        gen = ExcelReportGenerator(
            run=SAMPLE_RUN,
            findings=SAMPLE_FINDINGS,
            output_dir=str(tmp_path),
            tenant_id="test-tenant",
        )
        path = gen.generate()
        assert Path(path).exists()
        assert path.endswith(".xlsx")

    def test_excel_has_multiple_sheets(self, tmp_path: Path):
        """Excel workbook contains multiple sheets."""
        pytest.importorskip("openpyxl")
        import openpyxl

        from unimonitor.reporting.excel_generator import ExcelReportGenerator

        gen = ExcelReportGenerator(
            run=SAMPLE_RUN,
            findings=SAMPLE_FINDINGS,
            output_dir=str(tmp_path),
            tenant_id="test-tenant",
        )
        path = gen.generate()
        wb = openpyxl.load_workbook(path)
        assert len(wb.sheetnames) >= 2


# ── Multi-cloud sections ──────────────────────────────────────────────────────

MULTI_CLOUD_FINDINGS = [
    {
        "id": "f-ent",
        "external_control_id": "CTRL-ENT-001",
        "title": "MFA not enabled",
        "description": "mfa",
        "severity": "CRITICAL",
        "state": "not_implemented",
        "category": "identity",
        "service": "entra_id",
    },
    {
        "id": "f-aws",
        "external_control_id": "CTRL-AWS-001",
        "title": "Root MFA enabled",
        "description": "root",
        "severity": "HIGH",
        "state": "implemented",
        "category": "cloud_security",
        "service": "aws",
    },
    {
        "id": "f-gcp",
        "external_control_id": "CTRL-GCP-003",
        "title": "Firewall open to internet",
        "description": "fw",
        "severity": "HIGH",
        "state": "partially_implemented",
        "category": "cloud_security",
        "service": "gcp",
    },
]


def _generator(cls, tmp_path: Path):
    return cls(
        run=SAMPLE_RUN,
        findings=MULTI_CLOUD_FINDINGS,
        output_dir=str(tmp_path),
        tenant_id="test-tenant",
    )


class TestProviderBreakdown:
    def test_groups_findings_by_cloud(self, tmp_path: Path):
        from unimonitor.reporting.pdf_generator import PdfReportGenerator

        rows = _generator(PdfReportGenerator, tmp_path)._provider_breakdown()
        assert [r["id"] for r in rows] == ["microsoft", "aws", "gcp"]

        microsoft = rows[0]
        assert microsoft["total"] == 1
        assert microsoft["severity_counts"]["CRITICAL"] == 1
        assert microsoft["pass_rate"] == 0.0

        aws = rows[1]
        assert aws["colour"] == "#FF9900"
        assert aws["security_score"] == 100.0
        assert aws["findings"][0]["id"] == "f-aws"

    def test_provider_without_findings_is_omitted(self, tmp_path: Path):
        from unimonitor.reporting.pdf_generator import PdfReportGenerator

        rows = _generator(PdfReportGenerator, tmp_path)._provider_breakdown()
        assert "google_workspace" not in {r["id"] for r in rows}

    def test_unmapped_service_is_ignored(self, tmp_path: Path):
        from unimonitor.reporting.pdf_generator import PdfReportGenerator

        gen = PdfReportGenerator(
            run=SAMPLE_RUN,
            findings=[{"id": "x", "severity": "LOW", "state": "not_implemented", "service": "on_prem_ad"}],
            output_dir=str(tmp_path),
            tenant_id="test-tenant",
        )
        assert gen._provider_breakdown() == []


class TestPdfProviderSections:
    def test_pdf_renders_with_multiple_providers(self, tmp_path: Path):
        import asyncio

        from unimonitor.reporting.pdf_generator import PdfReportGenerator

        path = asyncio.run(_generator(PdfReportGenerator, tmp_path).generate("full"))
        assert Path(path).exists()
        assert Path(path).stat().st_size > 1000


class TestDocxGenerator:
    def test_docx_generates_with_provider_sections(self, tmp_path: Path):
        pytest.importorskip("docx")
        import asyncio

        from docx import Document

        from unimonitor.reporting.docx_generator import DocxReportGenerator

        path = asyncio.run(_generator(DocxReportGenerator, tmp_path).generate("full"))
        assert Path(path).exists()

        doc = Document(path)
        text = "\n".join(p.text for p in doc.paragraphs)
        for table in doc.tables:
            for row in table.rows:
                text += "\n" + " | ".join(cell.text for cell in row.cells)

        assert "Cloud Provider Coverage" in text
        assert "Findings by Cloud Provider" in text
        assert "Microsoft 365" in text
        assert "Amazon Web Services" in text
        assert "Google Cloud Platform" in text
        # aggregate summary is retained for the single org
        assert "Executive Summary" in text

    def test_docx_requires_python_docx(self, tmp_path: Path, monkeypatch):
        from unimonitor.reporting import docx_generator

        monkeypatch.setattr(docx_generator, "HAS_DOCX", False)
        gen = _generator(docx_generator.DocxReportGenerator, tmp_path)
        import asyncio

        with pytest.raises(RuntimeError):
            asyncio.run(gen.generate())
