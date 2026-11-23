"""Report generation and download endpoints."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.auth.dependencies import get_current_user, require_role
from unimonitor.auth.tenant_scope import tenant_scope
from unimonitor.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────

ReportType = Literal["executive", "audit", "compliance", "board", "operational"]
ReportFormat = Literal["pdf", "docx", "excel", "csv", "json", "html"]


class ReportGenerateRequest(BaseModel):
    """Report request.

    The UI selects an assessment run and one or more formats; the legacy
    ``tenant_id`` / ``report_format`` fields are still accepted so existing
    API clients keep working. ``tenant_id`` is derived from the run otherwise.
    """

    run_id: str | None = None
    formats: list[ReportFormat] | None = None
    tenant_id: str | None = None
    report_type: ReportType = "executive"
    report_format: ReportFormat | None = None
    title: str | None = None
    # Optional date range for filtering findings
    start_date: datetime | None = None
    end_date: datetime | None = None
    # Optional framework filter
    framework_id: str | None = None
    # Include suppressed findings
    include_suppressed: bool = False


class ReportStatusResponse(BaseModel):
    """One report, in the shape both the API and the Reports page read.

    ``id``/``formats``/``requested_by``/``run_id`` are what the SPA renders; the
    original ``report_id``/``report_format`` names stay for existing clients.
    """

    report_id: str
    id: str | None = None
    task_id: str | None
    status: str
    report_type: str
    report_format: str = "pdf"
    tenant_id: str
    title: str = ""
    created_at: datetime
    completed_at: datetime | None
    file_size_bytes: int | None = None
    download_url: str | None = None
    error_message: str | None = None
    formats: list[str] = []
    file_paths: dict[str, str] = {}
    requested_by: str | None = None
    run_id: str | None = None


class ReportListResponse(BaseModel):
    items: list[ReportStatusResponse]
    total: int


# In-memory store fallback when DB reports table not yet available
_reports_store: dict[str, dict] = {}


# ── Endpoints ────────────────────────────────────────────────


async def _tenant_for_run(run_id: str) -> str | None:
    """Resolve the owning tenant for an assessment run (None when unknown)."""
    try:
        from sqlalchemy import select

        from unimonitor.db.base import async_session_factory
        from unimonitor.db.models.assessment import Assessment, AssessmentRun

        async with async_session_factory() as session:
            result = await session.execute(
                select(Assessment.tenant_id).join(AssessmentRun, AssessmentRun.assessment_id == Assessment.id).where(AssessmentRun.id == run_id)
            )
            return result.scalar_one_or_none()
    except Exception as exc:  # noqa: BLE001 - DB down means we cannot resolve the run
        logger.warning("report_run_lookup_failed", run_id=run_id, error=str(exc))
        return None


def _report_item(row: Any) -> ReportStatusResponse:
    """Map a stored `Report` row (JSON strings on disk) to the API shape."""
    formats = json.loads(row.formats) if isinstance(row.formats, str) and row.formats else (row.formats or [])
    if not isinstance(formats, list):
        formats = []
    paths = json.loads(row.file_paths) if isinstance(row.file_paths, str) and row.file_paths else (row.file_paths or {})
    if not isinstance(paths, dict):
        paths = {}
    return ReportStatusResponse(
        report_id=row.id,
        id=row.id,
        task_id=row.task_id,
        status=row.status,
        report_type=row.report_type,
        report_format=formats[0] if formats else "pdf",
        tenant_id=row.tenant_id,
        title=f"{row.report_type.title()} Report",
        created_at=row.created_at,
        completed_at=row.completed_at,
        formats=formats,
        file_paths=paths,
        requested_by=row.requested_by,
        run_id=row.assessment_run_id,
        download_url=f"/api/v1/reports/{row.id}/download",
    )


ScorecardFormat = Literal["csv", "xlsx", "pdf"]


@router.get(
    "/scorecard",
    responses={
        400: {"description": "Unsupported scorecard format"},
        401: {"description": "Not authenticated"},
    },
)
async def download_scorecard(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    fmt: Annotated[ScorecardFormat, Query(description="csv, xlsx or pdf")] = "xlsx",
    tenant_id: Annotated[str | None, Depends(tenant_scope)] = None,
    run_id: Annotated[str | None, Query()] = None,
) -> Response:
    """Download the control-level scorecard as a file.

    Generated synchronously from stored findings and framework coverage; a run id
    narrows the scorecard to one assessment, otherwise the current state is used.
    """
    from unimonitor.reporting.scorecard import export, gather

    scorecard = await gather(db, tenant_id=tenant_id, run_id=run_id)
    content, media_type, filename = export(scorecard, fmt)
    logger.info("scorecard_exported", fmt=fmt, tenant_id=tenant_id, run_id=run_id, by=current_user.id)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED, responses={400: {"description": "Bad request"}, 404: {"description": "Not found"}})
async def generate_report(
    body: ReportGenerateRequest,
    current_user: Annotated[Any, Depends(require_role("analyst"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReportStatusResponse:
    """Queue a report generation task for one assessment run."""
    if not body.run_id:
        raise HTTPException(status_code=400, detail="run_id is required to generate a report")

    from unimonitor.auth.tenant_scope import resolve_tenant

    formats = body.formats or ([body.report_format] if body.report_format else ["pdf"])
    tenant_id = await resolve_tenant(db, current_user, body.tenant_id) or await _tenant_for_run(body.run_id)
    if not tenant_id:
        raise HTTPException(status_code=404, detail=f"Assessment run '{body.run_id}' not found")

    report_id = str(uuid.uuid4())
    title = body.title or f"{body.report_type.title()} Report"
    now = datetime.now(UTC)

    report_record = {
        "report_id": report_id,
        "task_id": None,
        "status": "pending",
        "report_type": body.report_type,
        "report_format": formats[0],
        "tenant_id": tenant_id,
        "title": title,
        "created_at": now,
        "completed_at": None,
        "file_size_bytes": None,
        "download_url": None,
        "error_message": None,
        "config": body.model_dump(mode="json"),
    }

    # Celery when a broker answers, otherwise the same coroutine runs in-process.
    # The worker creates the report row inside its own transaction: there is no
    # `ReportRepository.create_report`, so the old code never persisted anything and
    # every download answered "Report not found".
    try:
        from unimonitor.worker.inline import dispatch
        from unimonitor.worker.tasks.reporting import generate_report_task, run_report_now

        task_id = dispatch(
            generate_report_task,
            run_report_now,
            report_id=report_id,
            tenant_id=tenant_id,
            run_id=body.run_id,
            formats=formats,
            report_type=body.report_type,
            requested_by=str(current_user.id),
        )
        report_record["task_id"] = task_id
        report_record["status"] = "queued"
    except Exception as exc:  # noqa: BLE001 - the row records the failure
        logger.warning("report_dispatch_failed", error=str(exc))
        report_record["status"] = "failed"
        report_record["error_message"] = f"Could not queue the report: {exc}"

    report_record["formats"] = formats
    report_record["requested_by"] = str(current_user.id)
    report_record["run_id"] = body.run_id
    report_record["id"] = report_id
    _reports_store[report_id] = report_record

    logger.info("report_queued", report_id=report_id, type=body.report_type, format=body.report_format)
    return ReportStatusResponse(**{k: v for k, v in report_record.items() if k in ReportStatusResponse.model_fields})


@router.get("")
async def list_reports(
    current_user: Annotated[Any, Depends(get_current_user)],
    tenant_id: Annotated[str | None, Depends(tenant_scope)] = None,
    report_type: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ReportListResponse:
    """List generated reports."""
    # Try DB first, fall back to in-memory
    try:
        from sqlalchemy import func, select

        from unimonitor.db.base import async_session_factory
        from unimonitor.db.models.report import Report

        async with async_session_factory() as session:
            stmt = select(Report)
            if tenant_id:
                stmt = stmt.where(Report.tenant_id == tenant_id)
            if report_type:
                stmt = stmt.where(Report.report_type == report_type)
            total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
            rows = (await session.execute(stmt.order_by(Report.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
        items = [_report_item(row) for row in rows]
        return ReportListResponse(items=items, total=total)
    except Exception:  # noqa: S110  # NOSONAR - the in-memory store below is the fallback
        pass

    # In-memory fallback
    all_records = list(_reports_store.values())
    if tenant_id:
        all_records = [r for r in all_records if r.get("tenant_id") == tenant_id]
    if report_type:
        all_records = [r for r in all_records if r.get("report_type") == report_type]
    total = len(all_records)
    start = (page - 1) * page_size
    page_records = all_records[start : start + page_size]
    items = [ReportStatusResponse(**{k: v for k, v in r.items() if k in ReportStatusResponse.model_fields}) for r in page_records]
    return ReportListResponse(items=items, total=total)


# ── Run summary schemas and route must appear BEFORE /{report_id} ─────────────
# FastAPI routes are matched in definition order; /runs must precede /{report_id}
# or the literal "runs" will be captured as a report_id path parameter.


class RunReportSummary(BaseModel):
    """Lightweight assessment-run record for the Reports page run picker."""

    run_id: str
    assessment_id: str
    assessment_name: str = ""
    trigger: str = "manual"
    tenant_id: str
    status: str
    security_score: float | None
    compliance_score: float | None
    risk_score: float | None
    total_controls_checked: int
    controls_passed: int
    critical_count: int
    high_count: int
    started_at: datetime
    completed_at: datetime | None
    report_id: str | None = None  # associated report if one exists
    report_status: str | None = None

    model_config = {"from_attributes": True}


class PaginatedRunReports(BaseModel):
    items: list[RunReportSummary]
    total: int
    page: int
    page_size: int


@router.get("/runs")
async def list_report_runs(
    current_user: Annotated[Any, Depends(get_current_user)],
    tenant_id: Annotated[str | None, Depends(tenant_scope)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedRunReports:
    """List assessment runs for the Reports page run picker.

    Returns completed/failed runs with their associated report (if one has been
    generated), enabling the frontend ReportsPage to show a run-to-report mapping.
    """
    try:
        from sqlalchemy import func, select

        from unimonitor.db.base import async_session_factory
        from unimonitor.db.models.assessment import Assessment, AssessmentRun
        from unimonitor.db.models.report import Report

        async with async_session_factory() as session:
            # `AssessmentRun` has no tenant or created_at column: the tenant lives on
            # the parent assessment. Reading those attributes raised, the handler
            # returned an empty list, and the Reports page only ever offered
            # "Select a run".
            stmt = (
                select(AssessmentRun, Assessment)
                .join(Assessment, AssessmentRun.assessment_id == Assessment.id)
                .where(AssessmentRun.status.in_(["completed", "failed"]))
            )
            if tenant_id:
                stmt = stmt.where(Assessment.tenant_id == tenant_id)
            elif hasattr(current_user, "tenant_id") and current_user.tenant_id and current_user.role != "admin":
                stmt = stmt.where(Assessment.tenant_id == current_user.tenant_id)

            total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
            rows = (
                await session.execute(
                    stmt.order_by(AssessmentRun.completed_at.desc().nullslast(), AssessmentRun.started_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()

            report_rows = (
                (await session.execute(select(Report).where(Report.assessment_run_id.in_([run.id for run, _ in rows])))).scalars().all()
                if rows
                else []
            )
            reports_by_run = {row.assessment_run_id: row for row in report_rows}

            items: list[RunReportSummary] = []
            for run, assessment in rows:
                report = reports_by_run.get(run.id)
                items.append(
                    RunReportSummary(
                        run_id=run.id,
                        assessment_id=run.assessment_id,
                        assessment_name=assessment.name,
                        trigger=run.trigger or "manual",
                        tenant_id=assessment.tenant_id,
                        status=run.status,
                        security_score=run.security_score,
                        compliance_score=run.compliance_score,
                        risk_score=run.risk_score,
                        total_controls_checked=run.total_controls_checked or 0,
                        controls_passed=run.controls_passed or 0,
                        critical_count=run.critical_count or 0,
                        high_count=run.high_count or 0,
                        started_at=run.started_at,
                        completed_at=run.completed_at,
                        report_id=report.id if report else None,
                        report_status=report.status if report else None,
                    )
                )

            return PaginatedRunReports(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
            )

    except Exception as exc:
        logger.warning("list_report_runs_db_error", error=str(exc))
        # Return empty list when DB not available
        return PaginatedRunReports(items=[], total=0, page=page, page_size=page_size)


@router.get("/{report_id}", responses={404: {"description": "Not found"}})
async def get_report_status(
    report_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
) -> ReportStatusResponse:
    """Get report status and metadata."""
    # Try DB
    try:
        from sqlalchemy import select

        from unimonitor.db.base import async_session_factory
        from unimonitor.db.models.report import Report

        async with async_session_factory() as session:
            report = (await session.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
            if report:
                return ReportStatusResponse.model_validate(report)
    except Exception:  # noqa: S110  # NOSONAR - the in-memory store below is the fallback
        pass

    # In-memory
    record = _reports_store.get(report_id)
    if not record:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportStatusResponse(**{k: v for k, v in record.items() if k in ReportStatusResponse.model_fields})


_FORMAT_EXT = {"pdf": "pdf", "docx": "docx", "excel": "xlsx", "csv": "csv", "json": "json", "html": "html"}
_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "json": "application/json",
    "html": "text/html",
}


async def _report_files(report_id: str) -> dict[str, str]:
    """Return ``{format: existing path}`` for a report, from its stored file map."""
    import json

    from sqlalchemy import select

    from unimonitor.db.base import async_session_factory
    from unimonitor.db.models.report import Report

    try:
        async with async_session_factory() as session:
            report = (await session.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
            if not report or not report.file_paths:
                return {}
            stored = json.loads(report.file_paths)
    # A missing database must yield an empty answer, not a 500.
    except Exception as exc:  # noqa: BLE001
        logger.warning("report_lookup_failed", report_id=report_id, error=str(exc))
        return {}
    return {str(fmt): str(path) for fmt, path in stored.items() if Path(str(path)).exists()}


def _file_response(fmt: str, path: str) -> FileResponse:
    return FileResponse(path=path, media_type=_MEDIA_TYPES[fmt], filename=Path(path).name)


@router.get("/{report_id}/download/{fmt}", responses={404: {"description": "Not found"}})
async def download_report_format(
    report_id: str,
    fmt: str,
    current_user: Annotated[Any, Depends(get_current_user)],
) -> FileResponse:
    """Download one generated format of a report."""
    if fmt not in _FORMAT_EXT:
        raise HTTPException(status_code=404, detail=f"Unknown report format: {fmt}")

    files = await _report_files(report_id)
    path = files.get(fmt)
    if not path:
        raise HTTPException(status_code=404, detail=f"Report has no {fmt} file yet")
    return _file_response(fmt, path)


@router.get("/{report_id}/download", responses={404: {"description": "Not found"}})
async def download_report(
    report_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
) -> FileResponse:
    """Download the first available format (legacy clients that omit the format)."""
    files = await _report_files(report_id)
    for fmt in _FORMAT_EXT:
        if fmt in files:
            return _file_response(fmt, files[fmt])

    raise HTTPException(status_code=404, detail="Report file not found or not yet generated")


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: str,
    current_user: Annotated[Any, Depends(require_role("admin"))],
) -> None:
    """Delete a report and its generated files."""
    for path in (await _report_files(report_id)).values():
        Path(path).unlink(missing_ok=True)

    # Remove from store
    _reports_store.pop(report_id, None)

    # Remove the database row
    try:
        from sqlalchemy import delete as sql_delete

        from unimonitor.db.base import async_session_factory
        from unimonitor.db.models.report import Report

        async with async_session_factory() as session:
            await session.execute(sql_delete(Report).where(Report.id == report_id))
            await session.commit()
    except Exception as exc:  # noqa: BLE001 - deletion still succeeds without a DB
        logger.warning("report_row_delete_failed", report_id=report_id, error=str(exc))

    logger.info("report_deleted", report_id=report_id, by=current_user.id)
