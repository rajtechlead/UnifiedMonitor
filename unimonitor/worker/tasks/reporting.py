"""Reporting Celery tasks — async report generation."""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import Literal

from celery.utils.log import get_task_logger

from unimonitor.worker.celery_app import celery_app

logger = get_task_logger(__name__)

ReportFormat = Literal["pdf", "docx", "excel", "csv", "json"]


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def run_report_now(
    *,
    report_id: str,
    tenant_id: str,
    run_id: str,
    formats: list[ReportFormat],
    report_type: str = "executive",
    requested_by: str | None = None,
) -> dict:
    """In-process report generation for installs without a Celery broker.

    `worker.inline.dispatch` calls this when the broker is unreachable, so a
    single-process Windows install can still generate a report from the UI.
    """
    return await _generate_report(
        report_id=report_id,
        tenant_id=tenant_id,
        run_id=run_id,
        formats=formats,
        report_type=report_type,
        task_id="inline",
        requested_by=requested_by,
    )


@celery_app.task(
    bind=True,
    name="unimonitor.worker.tasks.reporting.generate_report_task",
    max_retries=1,
    default_retry_delay=30,
    queue="reports",
)
def generate_report_task(
    self,
    report_id: str,
    tenant_id: str,
    run_id: str,
    formats: list[ReportFormat],
    report_type: str = "full",
    requested_by: str | None = None,
) -> dict:
    """Generate a report for an assessment run."""
    logger.info(
        "Report task started",
        extra={"report_id": report_id, "run_id": run_id, "formats": formats},
    )

    try:
        return _run_async(
            _generate_report(
                report_id=report_id,
                tenant_id=tenant_id,
                run_id=run_id,
                formats=formats,
                report_type=report_type,
                task_id=self.request.id,
                requested_by=requested_by,
            )
        )
    except Exception as exc:
        logger.error("Report task failed", extra={"report_id": report_id, "error": str(exc)})
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"report_id": report_id, "status": "failed", "error": str(exc)[:500]}


async def _load_report_context(
    db,
    report_id: str,
    run_id: str,
    *,
    tenant_id: str | None = None,
    formats: list[str] | None = None,
    report_type: str = "executive",
    requested_by: str | None = None,
):
    """Load the report, its run and that run's findings, creating the row if needed.

    The API only knows the request, so the worker owns the row: it is created here in
    the same transaction that stores the generated files.
    """
    from sqlalchemy import select

    from unimonitor.db.models.assessment import AssessmentRun
    from unimonitor.db.models.finding import Finding
    from unimonitor.db.models.report import Report, ReportStatus

    report = (await db.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if report is None:
        if not tenant_id:
            raise ValueError(f"Report {report_id} not found")
        report = Report(
            id=report_id,
            tenant_id=tenant_id,
            assessment_run_id=run_id,
            status=ReportStatus.PENDING.value,
            formats=json.dumps(formats or []),
            report_type=report_type,
            requested_by=requested_by,
        )
        db.add(report)
        await db.flush()

    run = (await db.execute(select(AssessmentRun).where(AssessmentRun.id == run_id))).scalar_one_or_none()
    if not run:
        raise ValueError(f"AssessmentRun {run_id} not found")

    findings = (await db.execute(select(Finding).where(Finding.assessment_run_id == run.id))).scalars().all()

    # A run can carry rows for a platform that has since been disconnected (or was
    # never connected on this install). Those are not evidence this tenant produced,
    # so a report must not present them as findings.
    from unimonitor.grc.providers import provider_for_service
    from unimonitor.onboarding.service import connected_providers

    connected = await connected_providers(db, tenant_id)
    if connected:
        findings = [f for f in findings if (provider := provider_for_service(f.service)) is not None and provider.id in connected]
    return report, run, findings


async def _generate_files(tenant_id: str, run, findings, formats: list[ReportFormat], report_type: str) -> dict[str, str]:
    """Render each requested format, skipping unknown ones and logging failures."""
    from unimonitor.reporting.csv_generator import CsvReportGenerator
    from unimonitor.reporting.docx_generator import DocxReportGenerator
    from unimonitor.reporting.excel_generator import ExcelReportGenerator
    from unimonitor.reporting.html_generator import HtmlReportGenerator
    from unimonitor.reporting.json_generator import JsonReportGenerator
    from unimonitor.reporting.pdf_generator import PdfReportGenerator

    generators = {
        "pdf": PdfReportGenerator,
        "docx": DocxReportGenerator,
        "excel": ExcelReportGenerator,
        "csv": CsvReportGenerator,
        "json": JsonReportGenerator,
        "html": HtmlReportGenerator,
    }

    generated_files: dict[str, str] = {}
    for fmt in formats:
        gen_cls = generators.get(fmt)
        if gen_cls is None:
            logger.warning("Unknown report format", extra={"fmt": fmt})
            continue
        try:
            output = gen_cls(tenant_id=tenant_id, run=run, findings=findings).generate(report_type=report_type)
            # DOCX and PDF generation are async; CSV/Excel/JSON/HTML are not.
            generated_files[fmt] = await output if inspect.isawaitable(output) else output
        except Exception as exc:
            logger.error("Report generation failed", extra={"fmt": fmt, "error": str(exc)})
    return generated_files


async def _generate_report(
    *,
    report_id: str,
    tenant_id: str,
    run_id: str,
    formats: list[ReportFormat],
    report_type: str,
    task_id: str,
    requested_by: str | None = None,
) -> dict:
    from unimonitor.db.base import async_session_factory
    from unimonitor.db.models.report import ReportStatus

    async with async_session_factory() as db:
        report, run, findings = await _load_report_context(
            db,
            report_id,
            run_id,
            tenant_id=tenant_id,
            formats=list(formats),
            report_type=report_type,
            requested_by=requested_by,
        )

        report.status = ReportStatus.GENERATING.value
        report.task_id = task_id
        await db.commit()

        generated_files = await _generate_files(tenant_id, run, findings, formats, report_type)

        report.status = ReportStatus.COMPLETED.value if generated_files else ReportStatus.FAILED.value
        report.file_paths = json.dumps(generated_files)
        await db.commit()

    return {"report_id": report_id, "status": report.status, "files": generated_files}
