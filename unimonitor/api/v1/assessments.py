"""Assessment management endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.auth.dependencies import get_current_user, require_role
from unimonitor.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────


class AssessmentCreate(BaseModel):
    tenant_id: str = ""
    name: str = Field(..., min_length=1, max_length=256)
    description: str | None = None
    frameworks: list[str] = Field(default_factory=list, description="Framework IDs to include")
    collectors: list[str] = Field(default_factory=list, description="Collector names to run")


class AssessmentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    frameworks: list[str] | None = None
    collectors: list[str] | None = None
    is_active: bool | None = None


class RunSummary(BaseModel):
    id: str
    status: str
    trigger: str
    security_score: float | None
    compliance_score: float | None
    risk_score: float | None
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    informational_count: int
    total_controls_checked: int
    controls_passed: int
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: float | None
    error_message: str | None

    model_config = {"from_attributes": True}


class AssessmentResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str | None
    frameworks: list[str]
    collectors: list[str]
    is_active: bool
    created_at: datetime
    latest_run: RunSummary | None = None

    model_config = {"from_attributes": True}


class PaginatedAssessments(BaseModel):
    items: list[AssessmentResponse]
    total: int = 0
    page: int = 1
    page_size: int = 20


class TriggerRunResponse(BaseModel):
    run_id: str
    task_id: str
    status: str
    message: str


class PaginatedRuns(BaseModel):
    items: list[RunSummary]
    total: int
    page: int
    page_size: int


# ── Helpers ──────────────────────────────────────────────────


def _assessment_to_response(assessment, latest_run=None) -> AssessmentResponse:
    return AssessmentResponse(
        id=assessment.id,
        tenant_id=assessment.tenant_id,
        name=assessment.name,
        description=assessment.description,
        frameworks=assessment.framework_list() if hasattr(assessment, "framework_list") else [],
        collectors=assessment.collector_list() if hasattr(assessment, "collector_list") else [],
        is_active=assessment.is_active,
        created_at=assessment.created_at,
        latest_run=RunSummary.model_validate(latest_run) if latest_run else None,
    )


# ── Endpoints ────────────────────────────────────────────────


@router.get("", response_model=PaginatedAssessments)
async def list_assessments(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
) -> PaginatedAssessments:
    """List assessments, optionally filtered by tenant."""
    from unimonitor.db.repositories.assessment_repo import AssessmentRepository

    repo = AssessmentRepository(db)
    assessments = await repo.list_all(tenant_id=tenant_id, is_active=is_active)
    results = []
    for a in assessments:
        latest = await repo.get_latest_run(a.id)
        results.append(_assessment_to_response(a, latest))

    return PaginatedAssessments(items=results, total=len(results))


@router.post("", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    body: AssessmentCreate,
    current_user: Annotated[Any, Depends(require_role("analyst"))],
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    """Create a new assessment configuration."""
    from unimonitor.db.repositories.assessment_repo import AssessmentRepository

    repo = AssessmentRepository(db)
    tenant_id = body.tenant_id or current_user.tenant_id
    assessment = await repo.create(
        tenant_id=tenant_id,
        name=body.name,
        description=body.description,
        frameworks=",".join(body.frameworks),
        collectors=",".join(body.collectors),
    )

    logger.info("assessment_created", assessment_id=assessment.id, by=current_user.id)
    return _assessment_to_response(assessment)


@router.get("/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    """Get assessment by ID with latest run summary."""
    from unimonitor.db.repositories.assessment_repo import AssessmentRepository

    repo = AssessmentRepository(db)
    assessment = await repo.get_by_id(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    latest = await repo.get_latest_run(assessment_id)

    return _assessment_to_response(assessment, latest)


@router.put("/{assessment_id}", response_model=AssessmentResponse)
async def update_assessment(
    assessment_id: str,
    body: AssessmentUpdate,
    current_user: Annotated[Any, Depends(require_role("analyst"))],
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    """Update assessment configuration."""
    from unimonitor.db.repositories.assessment_repo import AssessmentRepository

    repo = AssessmentRepository(db)
    assessment = await repo.get_by_id(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    updates: dict = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.description is not None:
        updates["description"] = body.description
    if body.frameworks is not None:
        updates["frameworks"] = ",".join(body.frameworks)
    if body.collectors is not None:
        updates["collectors"] = ",".join(body.collectors)
    if body.is_active is not None:
        updates["is_active"] = body.is_active

    assessment = await repo.update(assessment_id, **updates)
    latest = await repo.get_latest_run(assessment_id)

    logger.info("assessment_updated", assessment_id=assessment_id, by=current_user.id)
    return _assessment_to_response(assessment, latest)


@router.delete("/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assessment(
    assessment_id: str,
    current_user: Annotated[Any, Depends(require_role("admin"))],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an assessment and all its runs."""
    from unimonitor.db.repositories.assessment_repo import AssessmentRepository

    repo = AssessmentRepository(db)
    assessment = await repo.get_by_id(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    await repo.delete(assessment_id)

    logger.info("assessment_deleted", assessment_id=assessment_id, by=current_user.id)


@router.post("/{assessment_id}/run", response_model=TriggerRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_run(
    assessment_id: str,
    current_user: Annotated[Any, Depends(require_role("analyst"))],
    db: AsyncSession = Depends(get_db),
) -> TriggerRunResponse:
    """Trigger an assessment run as a Celery background task."""
    from unimonitor.db.repositories.assessment_repo import AssessmentRepository

    repo = AssessmentRepository(db)
    assessment = await repo.get_by_id(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Create the run record
    run = await repo.create_run(
        assessment_id=assessment_id,
        trigger="manual",
        triggered_by=current_user.id,
    )
    await db.flush()

    # Dispatch Celery task
    task_id = f"local-{run.id}"
    try:
        from unimonitor.worker.tasks import run_assessment_task

        task = run_assessment_task.delay(
            assessment_id=assessment_id,
            run_id=run.id,
        )
        await repo.update_run(run.id, task_id=task.id)
        task_id = task.id
    except Exception as exc:
        logger.warning("celery_dispatch_failed", error=str(exc))
        # Store the local task id; the run stays pending for now
        await repo.update_run(run.id, task_id=task_id)

    logger.info("assessment_run_triggered", run_id=run.id, task_id=task_id, by=current_user.id)
    return TriggerRunResponse(
        run_id=run.id,
        task_id=task_id,
        status="pending",
        message=f"Assessment run {run.id} queued successfully",
    )


@router.get("/{assessment_id}/runs", response_model=PaginatedRuns)
async def list_runs(
    assessment_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedRuns:
    """List all runs for an assessment."""
    from unimonitor.db.repositories.assessment_repo import AssessmentRepository

    repo = AssessmentRepository(db)
    runs, total = await repo.list_runs(assessment_id, page=page, page_size=page_size)

    return PaginatedRuns(
        items=[RunSummary.model_validate(r) for r in runs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{assessment_id}/runs/{run_id}", response_model=RunSummary)
async def get_run(
    assessment_id: str,
    run_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> RunSummary:
    """Get a specific assessment run."""
    from unimonitor.db.repositories.assessment_repo import AssessmentRepository

    repo = AssessmentRepository(db)
    run = await repo.get_run_by_id(run_id)
    if not run or run.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="Run not found")

    return RunSummary.model_validate(run)


@router.post("/{assessment_id}/runs/{run_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_run(
    assessment_id: str,
    run_id: str,
    current_user: Annotated[Any, Depends(require_role("analyst"))],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cancel a pending or running assessment run."""
    from unimonitor.db.repositories.assessment_repo import AssessmentRepository

    repo = AssessmentRepository(db)
    run = await repo.get_run_by_id(run_id)
    if not run or run.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status not in ("pending", "running"):
        raise HTTPException(status_code=409, detail=f"Run cannot be cancelled in state '{run.status}'")

    if run.task_id:
        try:
            from unimonitor.worker.celery_app import celery_app

            celery_app.control.revoke(run.task_id, terminate=True)
        except Exception as exc:
            logger.warning("celery_revoke_failed", task_id=run.task_id, error=str(exc))

    await repo.update_run(run_id, status="cancelled")

    logger.info("run_cancelled", run_id=run_id, by=current_user.id)
    return {"run_id": run_id, "status": "cancelled"}
