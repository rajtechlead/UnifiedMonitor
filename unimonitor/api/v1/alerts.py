"""Alert Center API — policies, alerts and their workflow."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.auth.dependencies import get_current_user, require_role
from unimonitor.core.audit import write_audit
from unimonitor.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter()

AlertStatusLiteral = Literal["open", "acknowledged", "snoozed", "resolved"]


class AlertResponse(BaseModel):
    id: str
    tenant_id: str
    policy_id: str | None
    title: str
    detail: str | None
    severity: str
    status: str
    metric: str | None
    metric_value: float | None
    threshold: float | None
    assigned_to: str | None
    notes: str | None
    snoozed_until: datetime | None
    triggered_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class AlertPage(BaseModel):
    items: list[AlertResponse]
    total: int
    page: int
    page_size: int
    pages: int


class AlertSummary(BaseModel):
    open: int
    acknowledged: int
    snoozed: int
    resolved: int
    by_severity: dict[str, int]
    total: int


class PolicyResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str | None
    kind: str
    metric: str
    comparator: str
    threshold: float
    window_hours: int
    severity: str
    enabled: bool
    notify: bool
    template_key: str | None

    model_config = {"from_attributes": True}


class PolicyRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    kind: Literal["metric", "activity", "anomaly"] = "metric"
    metric: str = "critical_findings"
    comparator: Literal[">=", ">", "<=", "<"] = ">="
    threshold: float = 1
    window_hours: int = 24
    severity: str = "HIGH"
    enabled: bool = True
    notify: bool = True


class TemplateRequest(BaseModel):
    template_key: str
    tenant_id: str | None = None
    enabled: bool = True


class AlertUpdateRequest(BaseModel):
    status: AlertStatusLiteral
    assigned_to: str | None = None
    snooze_hours: int | None = None
    note: str | None = None


@router.get("/templates")
async def list_templates(current_user: Annotated[Any, Depends(get_current_user)]) -> list[dict]:
    """Predefined policies the UI can create in one click."""
    from unimonitor.db.models.alert import ALERT_TEMPLATES, METRICS

    return [{**template, "metric_label": METRICS.get(template["metric"], template["metric"])} for template in ALERT_TEMPLATES]


@router.get("/summary")
async def alert_summary(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> AlertSummary:
    from unimonitor.db.models.alert import Alert

    conditions = [Alert.tenant_id == tenant_id] if tenant_id else []
    status_rows = (await db.execute(select(Alert.status, func.count(Alert.id)).where(*conditions).group_by(Alert.status))).all()
    severity_rows = (
        await db.execute(select(Alert.severity, func.count(Alert.id)).where(*conditions, Alert.status != "resolved").group_by(Alert.severity))
    ).all()
    by_status = {row[0]: row[1] for row in status_rows}
    return AlertSummary(
        open=by_status.get("open", 0),
        acknowledged=by_status.get("acknowledged", 0),
        snoozed=by_status.get("snoozed", 0),
        resolved=by_status.get("resolved", 0),
        by_severity={row[0]: row[1] for row in severity_rows},
        total=sum(by_status.values()),
    )


@router.get("/policies")
async def list_policies(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> list[PolicyResponse]:
    from unimonitor.db.models.alert import AlertPolicy

    stmt = select(AlertPolicy).order_by(AlertPolicy.name)
    if tenant_id:
        stmt = stmt.where(AlertPolicy.tenant_id == tenant_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [PolicyResponse.model_validate(row) for row in rows]


async def _tenant_for(db: AsyncSession, tenant_id: str | None) -> str:
    from unimonitor.db.models.tenant import Tenant

    if tenant_id:
        return tenant_id
    first = (await db.execute(select(Tenant.id).where(Tenant.is_active).order_by(Tenant.created_at))).scalars().first()
    if not first:
        raise HTTPException(status_code=409, detail="No tenant is configured yet")
    return first


@router.post("/policies", status_code=status.HTTP_201_CREATED)
async def create_policy(
    body: PolicyRequest,
    current_user: Annotated[Any, Depends(require_role("analyst"))],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> PolicyResponse:
    from unimonitor.db.models.alert import METRICS, AlertPolicy

    if body.metric not in METRICS:
        raise HTTPException(status_code=422, detail=f"Unknown metric '{body.metric}'. Valid: {sorted(METRICS)}")
    policy = AlertPolicy(
        tenant_id=await _tenant_for(db, tenant_id),
        name=body.name or METRICS[body.metric],
        description=body.description,
        kind=body.kind,
        metric=body.metric,
        comparator=body.comparator,
        threshold=body.threshold,
        window_hours=max(1, min(24 * 30, body.window_hours)),
        severity=body.severity,
        enabled=body.enabled,
        notify=body.notify,
    )
    db.add(policy)
    await db.flush()
    await write_audit(
        db,
        action="alert.policy_created",
        tenant_id=policy.tenant_id,
        user_id=current_user.id,
        resource_type="alert_policy",
        resource_id=policy.id,
        payload={"name": policy.name, "metric": policy.metric},
    )
    await db.flush()
    return PolicyResponse.model_validate(policy)


@router.post("/policies/from-template", status_code=status.HTTP_201_CREATED)
async def create_policy_from_template(
    body: TemplateRequest,
    current_user: Annotated[Any, Depends(require_role("analyst"))],
    db: AsyncSession = Depends(get_db),
) -> PolicyResponse:
    from unimonitor.db.models.alert import ALERT_TEMPLATES, AlertPolicy

    template = next((t for t in ALERT_TEMPLATES if t["key"] == body.template_key), None)
    if template is None:
        raise HTTPException(status_code=404, detail=f"Unknown template '{body.template_key}'")
    policy = AlertPolicy(
        tenant_id=await _tenant_for(db, body.tenant_id),
        name=template["name"],
        description=template["description"],
        kind=template["kind"],
        metric=template["metric"],
        comparator=template["comparator"],
        threshold=float(template["threshold"]),
        window_hours=int(template["window_hours"]),
        severity=template["severity"],
        enabled=body.enabled,
        template_key=template["key"],
    )
    db.add(policy)
    await db.flush()
    await write_audit(
        db,
        action="alert.policy_created",
        tenant_id=policy.tenant_id,
        user_id=current_user.id,
        resource_type="alert_policy",
        resource_id=policy.id,
        payload={"template": template["key"]},
    )
    await db.flush()
    return PolicyResponse.model_validate(policy)


@router.put("/policies/{policy_id}")
async def update_policy(
    policy_id: str,
    body: PolicyRequest,
    current_user: Annotated[Any, Depends(require_role("analyst"))],
    db: AsyncSession = Depends(get_db),
) -> PolicyResponse:
    from unimonitor.db.models.alert import AlertPolicy

    policy = (await db.execute(select(AlertPolicy).where(AlertPolicy.id == policy_id))).scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if body.name is not None:
        policy.name = body.name
    policy.description = body.description
    policy.kind = body.kind
    policy.metric = body.metric
    policy.comparator = body.comparator
    policy.threshold = body.threshold
    policy.window_hours = max(1, min(24 * 30, body.window_hours))
    policy.severity = body.severity
    policy.enabled = body.enabled
    policy.notify = body.notify
    await db.flush()
    return PolicyResponse.model_validate(policy)


@router.delete("/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: str,
    current_user: Annotated[Any, Depends(require_role("analyst"))],
    db: AsyncSession = Depends(get_db),
) -> None:
    from sqlalchemy import delete

    from unimonitor.db.models.alert import AlertPolicy

    await db.execute(delete(AlertPolicy).where(AlertPolicy.id == policy_id))
    await db.flush()


@router.post("/evaluate")
async def evaluate_now(
    current_user: Annotated[Any, Depends(require_role("analyst"))],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> dict:
    """Evaluate policies immediately instead of waiting for the schedule."""
    from unimonitor.alerts.engine import evaluate_tenant

    target = await _tenant_for(db, tenant_id)
    raised = await evaluate_tenant(db, target)
    return {"tenant_id": target, "raised": len(raised), "alert_ids": [alert.id for alert in raised]}


@router.get("")
async def list_alerts(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> AlertPage:
    from unimonitor.db.models.alert import Alert

    conditions = []
    if tenant_id:
        conditions.append(Alert.tenant_id == tenant_id)
    if status_filter:
        conditions.append(Alert.status == status_filter)
    if severity:
        conditions.append(Alert.severity == severity)

    total = await db.scalar(select(func.count(Alert.id)).where(*conditions)) or 0
    rows = (
        (await db.execute(select(Alert).where(*conditions).order_by(desc(Alert.triggered_at)).offset((page - 1) * page_size).limit(page_size)))
        .scalars()
        .all()
    )
    return AlertPage(
        items=[AlertResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, (total + page_size - 1) // page_size),
    )


@router.post("/{alert_id}/status")
async def update_alert(
    alert_id: str,
    body: AlertUpdateRequest,
    current_user: Annotated[Any, Depends(require_role("analyst"))],
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    from unimonitor.db.models.alert import Alert

    alert = (await db.execute(select(Alert).where(Alert.id == alert_id))).scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    now = datetime.now(UTC)
    previous = alert.status
    alert.status = body.status
    if body.assigned_to is not None:
        alert.assigned_to = body.assigned_to
    if body.note:
        alert.notes = f"{alert.notes}\n{body.note}".strip() if alert.notes else body.note
    if body.status == "acknowledged":
        alert.acknowledged_at = now
        alert.snoozed_until = None
    elif body.status == "snoozed":
        alert.snoozed_until = now + timedelta(hours=body.snooze_hours or 24)
    elif body.status == "resolved":
        alert.resolved_at = now
        alert.snoozed_until = None

    await write_audit(
        db,
        action="alert.status_changed",
        tenant_id=alert.tenant_id,
        user_id=current_user.id,
        resource_type="alert",
        resource_id=alert.id,
        payload={"from": previous, "to": body.status, "note": body.note},
    )
    await db.flush()
    return AlertResponse.model_validate(alert)
