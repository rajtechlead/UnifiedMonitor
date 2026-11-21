"""Finding management endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.auth.dependencies import get_current_user, require_role
from unimonitor.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter()

NOT_FOUND_DETAIL = "Finding not found"


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
    triage_status: str = "open"
    assignee_id: str | None = None
    snoozed_until: datetime | None = None
    is_suppressed: bool
    suppression_reason: str | None
    suppression_expires_at: datetime | None = None
    first_detected_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None
    ai_remediation: dict | None = None
    # Remediation carried by the control definition — always available, unlike the
    # AI guidance which only exists once it has been generated.
    remediation: str | None = None

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
    # An exception without an end date is a permanent blind spot; allow both, but
    # make the time-boxed form the easy one.
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


class TriageRequest(BaseModel):
    """Handler workflow change; the control's implementation state is separate."""

    status: Literal["open", "acknowledged", "snoozed", "resolved"]
    assignee_id: str | None = None
    snooze_hours: int | None = None
    note: str | None = None


class PriorityItem(BaseModel):
    id: str
    external_control_id: str
    title: str
    severity: str
    category: str
    service: str
    risk_score: int
    triage_status: str
    effort: int
    impact: int
    roi: float


class PriorityQueueResponse(BaseModel):
    items: list[PriorityItem]
    total: int
    tenant_id: str | None


class TimelineItem(BaseModel):
    kind: str
    at: datetime
    state: str | None = None
    source: str | None = None
    detail: str | None = None


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


def _control_remediation() -> dict[str, str]:
    """Remediation guidance per control id, from the control library."""
    from unimonitor.grc.control_loader import ControlLoader

    guidance: dict[str, str] = {}
    for control in ControlLoader().load_all():
        text = "\n".join(control.remediation_steps) or control.remediation_summary
        if text:
            guidance[control.id] = text
    return guidance


def _with_remediation(finding, guidance: dict[str, str]) -> FindingResponse:
    item = FindingResponse.model_validate(finding)
    if not item.remediation:
        item.remediation = guidance.get(finding.external_control_id)
    return item


VALID_SEVERITIES = {"informational", "low", "medium", "high", "critical"}


async def _release_expired_suppressions(db: AsyncSession) -> int:
    """Clear time-boxed exceptions whose end date has passed."""
    from sqlalchemy import update

    from unimonitor.db.models.finding import Finding

    now = datetime.now(UTC)
    result = await db.execute(
        update(Finding)
        .where(
            Finding.is_suppressed.is_(True),
            Finding.suppression_expires_at.is_not(None),
            Finding.suppression_expires_at <= now,
        )
        .values(is_suppressed=False, suppression_reason=None, suppression_expires_at=None)
    )
    if result.rowcount:
        # The request-scoped session commits at the end of the request; flushing
        # keeps this usable inside callers that manage their own transaction.
        await db.flush()
        logger.info("suppressions_expired", count=result.rowcount)
    return int(result.rowcount or 0)


@router.get("/summary", response_model=FindingSummaryResponse)
async def findings_summary(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> FindingSummaryResponse:
    """Return aggregated finding counts by severity, state, and category."""
    from unimonitor.db.repositories.finding_repo import FindingRepository

    await _release_expired_suppressions(db)
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


@router.get("/export/siem")
async def export_siem(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    fmt: Literal["cef", "json"] = Query(default="cef", alias="format"),
    limit: int = Query(default=1000, ge=1, le=5000),
) -> Response:
    """Export open findings for a SIEM (CEF or JSON lines).

    Only unsuppressed, unresolved findings are exported: implemented and
    not-applicable controls are posture, not events. The export is intentionally
    stateless so a collector can poll it on its own schedule.
    """
    import json as _json

    from sqlalchemy import select

    from unimonitor.db.models.finding import Finding

    await _release_expired_suppressions(db)
    stmt = select(Finding).where(
        Finding.is_suppressed.is_(False),
        Finding.state.in_(["not_implemented", "partially_implemented"]),
    )
    if tenant_id:
        stmt = stmt.where(Finding.tenant_id == tenant_id)
    if severity:
        if severity.lower() not in VALID_SEVERITIES:
            raise HTTPException(status_code=400, detail=f"Invalid severity '{severity}'")
        stmt = stmt.where(Finding.severity == severity.upper())
    stmt = stmt.order_by(Finding.risk_score.desc(), Finding.last_seen_at.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    from unimonitor.integrations.events import finding_cef, finding_event

    if fmt == "json":
        body = "\n".join(_json.dumps(finding_event(row), separators=(",", ":")) for row in rows)
        return Response(content=body, media_type="application/x-ndjson")

    return Response(content="\n".join(finding_cef(row) for row in rows), media_type="text/plain")


@router.get("", response_model=PaginatedFindings)
async def list_findings(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    state: str | None = Query(default=None),
    triage_status: str | None = Query(default=None),
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

    await _release_expired_suppressions(db)

    if severity and severity.lower() not in VALID_SEVERITIES:
        raise HTTPException(status_code=422, detail=f"Invalid severity: {severity}")
    # State filter: accept known states and pass-through unknown values (returns empty results)

    repo = FindingRepository(db)
    findings, total = await repo.list_paginated(
        tenant_id=tenant_id,
        severity=severity,
        state=state,
        triage_status=triage_status,
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
    guidance = _control_remediation()
    return PaginatedFindings(
        items=[_with_remediation(f, guidance) for f in findings],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/priority", response_model=PriorityQueueResponse)
async def priority_queue(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> PriorityQueueResponse:
    """Open findings ranked by return on remediation effort (ROI).

    ``impact`` is the control's security impact (severity weight when the control
    does not declare one) and ``effort`` its 1–5 remediation complexity. A control
    can set either in YAML; the defaults keep the queue useful out of the box.
    """
    from unimonitor.db.models.finding import SEVERITY_WEIGHTS, FindingSeverity, FindingState
    from unimonitor.db.repositories.finding_repo import FindingRepository
    from unimonitor.grc.control_loader import ControlLoader

    repo = FindingRepository(db)
    findings, total = await repo.list_paginated(
        tenant_id=tenant_id,
        is_suppressed=False,
        page=1,
        page_size=500,
        sort_by="risk_score",
        sort_desc=True,
    )
    controls = {c.id: c for c in ControlLoader().load_all()}
    done = {FindingState.IMPLEMENTED.value, FindingState.NOT_APPLICABLE.value}

    items: list[PriorityItem] = []
    for finding in findings:
        if finding.state in done or finding.triage_status == "resolved":
            continue
        control = controls.get(finding.external_control_id)
        effort = max(1, min(5, int(getattr(control, "effort", 3) or 3)))
        impact = int(getattr(control, "impact", 0) or 0) or SEVERITY_WEIGHTS.get(finding.severity.upper(), SEVERITY_WEIGHTS[FindingSeverity.MEDIUM])
        roi = round((impact * 10 + (finding.risk_score or 0)) / effort, 2)
        items.append(
            PriorityItem(
                id=finding.id,
                external_control_id=finding.external_control_id,
                title=finding.title,
                severity=finding.severity,
                category=finding.category,
                service=finding.service,
                risk_score=finding.risk_score,
                triage_status=finding.triage_status,
                effort=effort,
                impact=impact,
                roi=roi,
            )
        )

    items.sort(key=lambda item: item.roi, reverse=True)
    return PriorityQueueResponse(items=items[:limit], total=total, tenant_id=tenant_id)


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
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)

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

    from unimonitor.db.repositories.finding_repo import FindingRepository

    repo = FindingRepository(db)
    finding = await repo.get_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)

    old_state = finding.state
    updates: dict = {"state": body.state}
    if body.state == "implemented":
        updates["resolved_at"] = datetime.now(UTC)
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


@router.post("/{finding_id}/triage", response_model=FindingResponse)
async def triage_finding(
    finding_id: str,
    body: TriageRequest,
    current_user: Annotated[Any, Depends(require_role("analyst"))],
    db: AsyncSession = Depends(get_db),
) -> FindingResponse:
    """Acknowledge, snooze, assign or resolve a finding.

    Separate from ``state`` (whether the control is implemented): this is the
    handler's queue status, and every change is written to the audit log.
    """
    from unimonitor.core.audit import write_audit
    from unimonitor.db.repositories.finding_repo import FindingRepository

    repo = FindingRepository(db)
    finding = await repo.get_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)

    previous = finding.triage_status
    snoozed_until = None
    if body.status == "snoozed":
        hours = body.snooze_hours if body.snooze_hours and body.snooze_hours > 0 else 24
        snoozed_until = datetime.now(UTC) + timedelta(hours=hours)

    finding = await repo.update(
        finding_id,
        triage_status=body.status,
        assignee_id=body.assignee_id if body.assignee_id is not None else finding.assignee_id,
        snoozed_until=snoozed_until,
    )
    await repo.add_history(
        finding_id=finding_id,
        previous_state=previous,
        new_state=body.status,
        changed_by=current_user.id,
        comment=body.note or f"Triage: {previous} → {body.status}",
    )
    await write_audit(
        db,
        action="finding.triaged",
        tenant_id=finding.tenant_id,
        user_id=current_user.id,
        resource_type="finding",
        resource_id=finding_id,
        payload={"from": previous, "to": body.status, "assignee_id": body.assignee_id, "note": body.note},
    )

    logger.info("finding_triaged", finding_id=finding_id, old=previous, new=body.status, by=current_user.id)
    return FindingResponse.model_validate(finding)


@router.get("/{finding_id}/timeline", response_model=list[TimelineItem])
async def finding_timeline(
    finding_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[TimelineItem]:
    """Merged investigation timeline: state changes and collected evidence."""
    from unimonitor.db.repositories.finding_repo import FindingRepository

    repo = FindingRepository(db)
    finding = await repo.get_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)

    timeline = [
        TimelineItem(
            kind="history",
            at=item.changed_at,
            state=item.new_state,
            detail=item.comment or f"{item.previous_state} → {item.new_state}",
        )
        for item in await repo.get_history(finding_id)
    ]
    from sqlalchemy import select

    from unimonitor.db.models.finding import FindingEvidence

    evidence = (await db.execute(select(FindingEvidence).where(FindingEvidence.finding_id == finding_id))).scalars().all()
    timeline += [TimelineItem(kind="evidence", at=item.collected_at, source=item.source, detail=item.evidence_type) for item in evidence]
    timeline.sort(key=lambda item: item.at)
    return timeline


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
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)

    expires_at = datetime.now(UTC) + timedelta(days=body.expires_in_days) if body.expires_in_days else None
    finding = await repo.update(
        finding_id,
        is_suppressed=True,
        suppression_reason=body.reason,
        suppression_expires_at=expires_at,
    )
    await repo.add_history(
        finding_id=finding_id,
        previous_state=finding.state,
        new_state="suppressed",
        changed_by=current_user.id,
        comment=f"Suppressed: {body.reason}" + (f" (expires {expires_at.date().isoformat()})" if expires_at else ""),
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
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)

    finding = await repo.update(
        finding_id,
        is_suppressed=False,
        suppression_reason=None,
        suppression_expires_at=None,
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
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)

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
        raise HTTPException(status_code=503, detail="Failed to dispatch AI remediation task") from exc


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
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)
    history = await repo.get_history(finding_id)

    return [FindingHistoryItem.model_validate(h) for h in history]
