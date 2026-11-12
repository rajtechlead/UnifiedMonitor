"""Reporting Celery tasks — async report generation."""

from __future__ import annotations

import asyncio
from typing import Literal

from celery.utils.log import get_task_logger

from unimonitor.worker.celery_app import celery_app

logger = get_task_logger(__name__)

ReportFormat = Literal["pdf", "excel", "csv", "json"]


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


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

    async def _run():
        from unimonitor.db.base import async_session_factory
        from unimonitor.db.models.report import Report, ReportStatus
        from unimonitor.db.models.assessment import AssessmentRun
        from unimonitor.db.models.finding import Finding
        from unimonitor.reporting.pdf_generator import PdfReportGenerator
        from unimonitor.reporting.excel_generator import ExcelReportGenerator
        from unimonitor.reporting.csv_generator import CsvReportGenerator
        from unimonitor.reporting.json_generator import JsonReportGenerator
        from sqlalchemy import select

        async with async_session_factory() as db:
            # Load report record
            result = await db.execute(select(Report).where(Report.id == report_id))
            report = result.scalar_one_or_none()
            if not report:
                raise ValueError(f"Report {report_id} not found")

            # Load run
            result = await db.execute(select(AssessmentRun).where(AssessmentRun.id == run_id))
            run = result.scalar_one_or_none()
            if not run:
                raise ValueError(f"AssessmentRun {run_id} not found")

            # Load findings
            result = await db.execute(
                select(Finding).where(Finding.assessment_id == run.assessment_id)
            )
            findings = result.scalars().all()

            report.status = ReportStatus.GENERATING.value
            report.task_id = self.request.id
            await db.commit()

            generated_files: dict[str, str] = {}
            generators = {
                "pdf": PdfReportGenerator,
                "excel": ExcelReportGenerator,
                "csv": CsvReportGenerator,
                "json": JsonReportGenerator,
            }

            for fmt in formats:
                gen_cls = generators.get(fmt)
                if gen_cls is None:
                    logger.warning("Unknown report format", fmt=fmt)
                    continue
                try:
                    gen = gen_cls(tenant_id=tenant_id, run=run, findings=findings)
                    file_path = await gen.generate(report_type=report_type)
                    generated_files[fmt] = file_path
                except Exception as exc:
                    logger.error("Report generation failed", fmt=fmt, error=str(exc))

            report.status = ReportStatus.COMPLETED.value if generated_files else ReportStatus.FAILED.value
            report.file_paths = generated_files
            await db.commit()

            return {
                "report_id": report_id,
                "status": report.status,
                "files": generated_files,
            }

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error("Report task failed", extra={"report_id": report_id, "error": str(exc)})
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"report_id": report_id, "status": "failed", "error": str(exc)[:500]}
