"""Report generation and download endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from unimonitor.auth.dependencies import get_current_user, require_role

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────

ReportType = Literal["executive", "audit", "compliance", "board", "operational"]
ReportFormat = Literal["pdf", "excel", "csv", "json"]


class ReportGenerateRequest(BaseModel):
    tenant_id: str
    report_type: ReportType
    report_format: ReportFormat
    title: str | None = None
    # Optional date range for filtering findings
    start_date: datetime | None = None
    end_date: datetime | None = None
    # Optional framework filter
    framework_id: str | None = None
    # Include suppressed findings
    include_suppressed: bool = False


class ReportStatusResponse(BaseModel):
    report_id: str
    task_id: str | None
    status: str
    report_type: str
    report_format: str
    tenant_id: str
    title: str
    created_at: datetime
    completed_at: datetime | None
    file_size_bytes: int | None
    download_url: str | None
    error_message: str | None


class ReportListResponse(BaseModel):
    items: list[ReportStatusResponse]
    total: int


# In-memory store fallback when DB reports table not yet available
_reports_store: dict[str, dict] = {}


# ── Endpoints ────────────────────────────────────────────────


@router.post("/generate", response_model=ReportStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_report(
    body: ReportGenerateRequest,
    current_user: Annotated[Any, Depends(require_role("analyst"))],
) -> ReportStatusResponse:
    """Queue a report generation task."""
    report_id = str(uuid.uuid4())
    title = body.title or f"{body.report_type.title()} Report"
    now = datetime.now(UTC)

    report_record = {
        "report_id": report_id,
        "task_id": None,
        "status": "pending",
        "report_type": body.report_type,
        "report_format": body.report_format,
        "tenant_id": body.tenant_id,
        "title": title,
        "created_at": now,
        "completed_at": None,
        "file_size_bytes": None,
        "download_url": None,
        "error_message": None,
        "config": body.model_dump(mode="json"),
    }

    # Try Celery dispatch
    try:
        from unimonitor.worker.tasks import generate_report_task

        task = generate_report_task.delay(
            report_id=report_id,
            report_type=body.report_type,
            report_format=body.report_format,
            tenant_id=body.tenant_id,
            title=title,
            config=body.model_dump(mode="json"),
        )
        report_record["task_id"] = task.id
        report_record["status"] = "queued"
    except Exception as exc:
        logger.warning("report_celery_unavailable", error=str(exc))
        # Synchronous fallback
        report_record["status"] = "queued"

    # Persist to DB if available, else in-memory
    try:
        from unimonitor.db.base import async_session_factory
        from unimonitor.db.repositories.assessment_repo import ReportRepository

        async with async_session_factory() as session:
            repo = ReportRepository(session)
            await repo.create_report(**{k: v for k, v in report_record.items() if k not in ("config",)})
    except Exception:
        _reports_store[report_id] = report_record

    logger.info("report_queued", report_id=report_id, type=body.report_type, format=body.report_format)
    return ReportStatusResponse(**{k: v for k, v in report_record.items() if k in ReportStatusResponse.model_fields})


@router.get("", response_model=ReportListResponse)
async def list_reports(
    current_user: Annotated[Any, Depends(get_current_user)],
    tenant_id: str | None = Query(default=None),
    report_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ReportListResponse:
    """List generated reports."""
    # Try DB first, fall back to in-memory
    try:
        from unimonitor.db.base import async_session_factory
        from unimonitor.db.repositories.assessment_repo import ReportRepository

        async with async_session_factory() as session:
            repo = ReportRepository(session)
            reports, total = await repo.list_reports(
                tenant_id=tenant_id,
                report_type=report_type,
                page=page,
                page_size=page_size,
            )
        items = [ReportStatusResponse.model_validate(r) for r in reports]
        return ReportListResponse(items=items, total=total)
    except Exception:  # noqa: S110
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


@router.get("/runs", response_model=PaginatedRunReports)
async def list_report_runs(
    current_user: Annotated[Any, Depends(get_current_user)],
    tenant_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedRunReports:
    """List assessment runs for the Reports page run picker.

    Returns completed/failed runs with their associated report (if one has been
    generated), enabling the frontend ReportsPage to show a run-to-report mapping.
    """
    try:
        from sqlalchemy import func, select

        from unimonitor.db.base import async_session_factory
        from unimonitor.db.models.assessment import AssessmentRun

        async with async_session_factory() as session:
            stmt = select(AssessmentRun).where(AssessmentRun.status.in_(["completed", "failed"]))
            if tenant_id:
                stmt = stmt.where(AssessmentRun.tenant_id == tenant_id)
            elif hasattr(current_user, "tenant_id") and current_user.tenant_id and current_user.role != "admin":
                stmt = stmt.where(AssessmentRun.tenant_id == current_user.tenant_id)

            # Total count
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total_result = await session.execute(count_stmt)
            total = total_result.scalar_one()

            # Paginate, most recent first
            stmt = stmt.order_by(AssessmentRun.completed_at.desc().nullslast())
            stmt = stmt.offset((page - 1) * page_size).limit(page_size)
            result = await session.execute(stmt)
            runs = result.scalars().all()

            # Resolve associated reports from in-memory store (or DB)
            items: list[RunReportSummary] = []
            for run in runs:
                rpt_id = None
                rpt_status = None
                # Check in-memory store
                for rid, rec in _reports_store.items():
                    if rec.get("config", {}).get("run_id") == run.id:
                        rpt_id = rid
                        rpt_status = rec.get("status")
                        break
                items.append(
                    RunReportSummary(
                        run_id=run.id,
                        assessment_id=run.assessment_id,
                        tenant_id=run.tenant_id,
                        status=run.status,
                        security_score=run.security_score,
                        compliance_score=run.compliance_score,
                        risk_score=run.risk_score,
                        total_controls_checked=run.total_controls_checked or 0,
                        controls_passed=run.controls_passed or 0,
                        critical_count=run.critical_count or 0,
                        high_count=run.high_count or 0,
                        started_at=run.created_at,
                        completed_at=run.completed_at,
                        report_id=rpt_id,
                        report_status=rpt_status,
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


@router.get("/{report_id}", response_model=ReportStatusResponse)
async def get_report_status(
    report_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
) -> ReportStatusResponse:
    """Get report status and metadata."""
    # Try DB
    try:
        from unimonitor.db.base import async_session_factory
        from unimonitor.db.repositories.assessment_repo import ReportRepository

        async with async_session_factory() as session:
            repo = ReportRepository(session)
            report = await repo.get_report_by_id(report_id)
            if report:
                return ReportStatusResponse.model_validate(report)
    except Exception:  # noqa: S110
        pass

    # In-memory
    record = _reports_store.get(report_id)
    if not record:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportStatusResponse(**{k: v for k, v in record.items() if k in ReportStatusResponse.model_fields})


@router.get("/{report_id}/download")
async def download_report(
    report_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
) -> FileResponse:
    """Download a completed report file."""
    from unimonitor.config import get_settings

    settings = get_settings()

    # Locate file
    report_dir = Path(settings.REPORT_STORAGE_PATH)
    for ext in ("pdf", "xlsx", "csv", "json"):
        file_path = report_dir / f"{report_id}.{ext}"
        if file_path.exists():
            media_types = {
                "pdf": "application/pdf",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "csv": "text/csv",
                "json": "application/json",
            }
            return FileResponse(
                path=str(file_path),
                media_type=media_types[ext],
                filename=file_path.name,
            )

    raise HTTPException(status_code=404, detail="Report file not found or not yet generated")


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: str,
    current_user: Annotated[Any, Depends(require_role("admin"))],
) -> None:
    """Delete a report and its file."""
    from unimonitor.config import get_settings

    settings = get_settings()

    # Remove file
    report_dir = Path(settings.REPORT_STORAGE_PATH)
    for ext in ("pdf", "xlsx", "csv", "json"):
        file_path = report_dir / f"{report_id}.{ext}"
        if file_path.exists():
            file_path.unlink()

    # Remove from store
    _reports_store.pop(report_id, None)

    # Try DB removal
    try:
        from unimonitor.db.base import async_session_factory
        from unimonitor.db.repositories.assessment_repo import ReportRepository

        async with async_session_factory() as session:
            repo = ReportRepository(session)
            await repo.delete_report(report_id)
    except Exception:  # noqa: S110
        pass

    logger.info("report_deleted", report_id=report_id, by=current_user.id)
