"""Finding management endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.auth.dependencies import get_current_user, require_role
from unimonitor.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────

class FindingResponse(BaseModel):
    id: str
    tenant_id: str
    external_control_id: str
    title: str
    description: str
    severity: str
    state: str
    category: str
    service: str
    risk_score: int
    is_suppressed: bool
    suppression_reason: str | None
    first_detected_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None
    ai_remediation: dict | None = None

    model_config = {"from_attributes": True}

    def model_post_init(self, _context) -> None:
        import json
        if isinstance(self.ai_remediation, str):
            try:
                self.ai_remediation = json.loads(self.ai_remediation)
            except (ValueError, TypeError):
                self.ai_remediation = None


class FindingHistoryItem(BaseModel):
    id: str
    previous_state: str
    new_state: str
    changed_by: str | None
    comment: str | None
    changed_at: datetime

    model_config = {"from_attributes": True}


class StateUpdateRequest(BaseModel):
    state: str
    comment: str | None = None


class SuppressRequest(BaseModel):
    reason: str


class AiRemediationRequest(BaseModel):
    force_refresh: bool = False


class FindingSummaryResponse(BaseModel):
    total: int
    by_severity: dict[str, int]
    by_state: dict[str, int]
    by_category: dict[str, int]
    suppressed_count: int
    tenant_id: str | None


class PaginatedFindings(BaseModel):
    items: list[FindingResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ── Endpoints ────────────────────────────────────────────────

VALID_STATES = {"implemented", "partially_implemented", "not_implemented", "not_applicable"}
VALID_SEVERITIES = {"informational", "low", "medium", "high", "critical"}


@router.get("/summary", response_model=FindingSummaryResponse)
async def findings_summary(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> FindingSummaryResponse:
    """Return aggregated finding counts by severity, state, and category."""
    from unimonitor.db.repositories.finding_repo import FindingRepository

    repo = FindingRepository(db)
    summary = await repo.get_summary(tenant_id=tenant_id)

    return FindingSummaryResponse(
        total=summary.get("total", 0),
        by_severity=summary.get("by_severity", {}),
        by_state=summary.get("by_state", {}),
        by_category=summary.get("by_category", {}),
        suppressed_count=summary.get("suppressed_count", 0),
        tenant_id=tenant_id,
    )


@router.get("", response_model=PaginatedFindings)
async def list_findings(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    state: str | None = Query(default=None),
    category: str | None = Query(default=None),
    service: str | None = Query(default=None),
    is_suppressed: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    sort_by: str = Query(default="last_seen_at"),
    sort_desc: bool = Query(default=True),
) -> PaginatedFindings:
    """List findings with filtering and pagination."""
    from unimonitor.db.repositories.finding_repo import FindingRepository

    if severity and severity.lower() not in VALID_SEVERITIES:
        raise HTTPException(status_code=422, detail=f"Invalid severity: {severity}")
    # State filter: accept known states and pass-through unknown values (returns empty results)

    repo = FindingRepository(db)
    findings, total = await repo.list_paginated(
        tenant_id=tenant_id,
        severity=severity,
        state=state,
        category=category,
        service=service,
        is_suppressed=is_suppressed,
        search=search,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )

    pages = max(1, (total + page_size - 1) // page_size)
    return PaginatedFindings(
        items=[FindingResponse.model_validate(f) for f in findings],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{finding_id}", response_model=FindingResponse)
async def get_finding(
    finding_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> FindingResponse:
    """Get a specific finding by ID."""
    from unimonitor.db.repositories.finding_repo import FindingRepository

    repo = FindingRepository(db)
    finding = await repo.get_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    return FindingResponse.model_validate(finding)


@router.patch("/{finding_id}/state", response_model=FindingResponse)
async def update_finding_state(
    finding_id: str,
    body: StateUpdateRequest,
    current_user: Annotated[Any, Depends(require_role("analyst"))],
    db: AsyncSession = Depends(get_db),
) -> FindingResponse:
    """Update the implementation state of a finding."""
    if body.state not in VALID_STATES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid state '{body.state}'. Valid states: {', '.join(VALID_STATES)}",
        )

    from datetime import timezone
    from unimonitor.db.repositories.finding_repo import FindingRepository

    repo = FindingRepository(db)
    finding = await repo.get_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    old_state = finding.state
    updates: dict = {"state": body.state}
    if body.state == "implemented":
        updates["resolved_at"] = datetime.now(timezone.utc)
    elif old_state == "implemented":
        updates["resolved_at"] = None

    finding = await repo.update(finding_id, **updates)

    await repo.add_history(
        finding_id=finding_id,
        previous_state=old_state,
        new_state=body.state,
        changed_by=current_user.id,
        comment=body.comment,
    )

    logger.info("finding_state_updated", finding_id=finding_id, old=old_state, new=body.state)
    return FindingResponse.model_validate(finding)


@router.post("/{finding_id}/suppress", response_model=FindingResponse)
async def suppress_finding(
    finding_id: str,
    body: SuppressRequest,
    current_user: Annotated[Any, Depends(require_role("analyst"))],
    db: AsyncSession = Depends(get_db),
) -> FindingResponse:
    """Suppress a finding with a justification reason."""
    from unimonitor.db.repositories.finding_repo import FindingRepository

    repo = FindingRepository(db)
    finding = await repo.get_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    finding = await repo.update(
        finding_id,
        is_suppressed=True,
        suppression_reason=body.reason,
    )
    await repo.add_history(
        finding_id=finding_id,
        previous_state=finding.state,
        new_state="suppressed",
        changed_by=current_user.id,
        comment=f"Suppressed: {body.reason}",
    )

    logger.info("finding_suppressed", finding_id=finding_id, by=current_user.id)
    return FindingResponse.model_validate(finding)


@router.post("/{finding_id}/unsuppress", response_model=FindingResponse)
async def unsuppress_finding(
    finding_id: str,
    current_user: Annotated[Any, Depends(require_role("analyst"))],
    db: AsyncSession = Depends(get_db),
) -> FindingResponse:
    """Remove suppression from a finding."""
    from unimonitor.db.repositories.finding_repo import FindingRepository

    repo = FindingRepository(db)
    finding = await repo.get_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    finding = await repo.update(
        finding_id,
        is_suppressed=False,
        suppression_reason=None,
    )
    await repo.add_history(
        finding_id=finding_id,
        previous_state="suppressed",
        new_state=finding.state,
        changed_by=current_user.id,
        comment="Suppression removed",
    )

    logger.info("finding_unsuppressed", finding_id=finding_id, by=current_user.id)
    return FindingResponse.model_validate(finding)


@router.post("/{finding_id}/remediate", status_code=status.HTTP_202_ACCEPTED)
async def trigger_ai_remediation(
    finding_id: str,
    body: AiRemediationRequest,
    current_user: Annotated[Any, Depends(require_role("analyst"))],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger AI-powered remediation generation for a finding."""
    from unimonitor.db.repositories.finding_repo import FindingRepository

    repo = FindingRepository(db)
    finding = await repo.get_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    if finding.ai_remediation and not body.force_refresh:
        import json
        try:
            return {"finding_id": finding_id, "status": "cached", "remediation": json.loads(finding.ai_remediation)}
        except (ValueError, TypeError):
            pass

    try:
        from unimonitor.worker.tasks import generate_ai_remediation_task
        task = generate_ai_remediation_task.delay(finding_id=finding_id)
        return {
            "finding_id": finding_id,
            "task_id": task.id,
            "status": "queued",
            "message": "AI remediation generation started",
        }
    except Exception as exc:
        logger.error("ai_remediation_dispatch_failed", finding_id=finding_id, error=str(exc))
        raise HTTPException(status_code=503, detail="Failed to dispatch AI remediation task")


@router.get("/{finding_id}/history", response_model=list[FindingHistoryItem])
async def get_finding_history(
    finding_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[FindingHistoryItem]:
    """Return state change history for a finding."""
    from unimonitor.db.repositories.finding_repo import FindingRepository

    repo = FindingRepository(db)
    finding = await repo.get_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    history = await repo.get_history(finding_id)

    return [FindingHistoryItem.model_validate(h) for h in history]
