"""Evaluate alert policies against findings and assessment history.

Every policy is a metric, a comparator and a threshold over a window. Evaluation
is idempotent within the window: a policy that already has an unresolved alert
does not raise a second one.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.core.audit import write_audit
from unimonitor.core.logging import get_logger
from unimonitor.db.models.alert import Alert, AlertPolicy, AlertStatus
from unimonitor.db.models.assessment import AssessmentRun
from unimonitor.db.models.finding import Finding, FindingState

logger = get_logger(__name__)

_UNRESOLVED = (Finding.state != FindingState.IMPLEMENTED.value, Finding.state != FindingState.NOT_APPLICABLE.value)


def _compares(value: float, comparator: str, threshold: float) -> bool:
    return {
        ">=": value >= threshold,
        ">": value > threshold,
        "<=": value <= threshold,
        "<": value < threshold,
    }.get(comparator, value >= threshold)


async def metric_value(db: AsyncSession, tenant_id: str, metric: str, window_hours: int) -> float:
    """Current value of a policy metric (0 when there is no data)."""
    cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
    base = [Finding.tenant_id == tenant_id, Finding.is_suppressed.is_(False), *_UNRESOLVED]

    if metric in {"critical_findings", "high_findings", "open_findings"}:
        stmt = select(func.count(Finding.id)).where(*base)
        if metric == "critical_findings":
            stmt = stmt.where(Finding.severity == "critical")
        elif metric == "high_findings":
            stmt = stmt.where(Finding.severity == "high")
        return float(await db.scalar(stmt) or 0)

    if metric == "risk_score":
        avg_stmt = select(func.avg(Finding.risk_score)).where(*base)
        return float(await db.scalar(avg_stmt) or 0)

    if metric == "new_findings":
        return float(await db.scalar(select(func.count(Finding.id)).where(*base, Finding.first_detected_at >= cutoff)) or 0)

    if metric == "security_score_drop":
        score_stmt = (
            select(AssessmentRun.security_score)
            .join(AssessmentRun.assessment)
            .where(
                AssessmentRun.assessment.has(tenant_id=tenant_id),
                AssessmentRun.security_score.is_not(None),
                AssessmentRun.started_at >= cutoff,
            )
            .order_by(AssessmentRun.started_at.asc())
        )
        scores = [row for row in (await db.execute(score_stmt)).scalars().all() if row is not None]
        return round(scores[0] - scores[-1], 2) if len(scores) > 1 else 0.0

    logger.warning("Unknown alert metric", metric=metric)
    return 0.0


async def evaluate_tenant(db: AsyncSession, tenant_id: str) -> list[Alert]:
    """Evaluate every enabled policy for one tenant and raise alerts."""
    from unimonitor.db.models.notification_setting import NotificationSetting
    from unimonitor.notifications.dispatcher import NotificationDispatcher

    policies = (await db.execute(select(AlertPolicy).where(AlertPolicy.tenant_id == tenant_id, AlertPolicy.enabled))).scalars().all()
    settings_obj = (await db.execute(select(NotificationSetting).where(NotificationSetting.tenant_id == tenant_id))).scalar_one_or_none()

    raised: list[Alert] = []
    for policy in policies:
        value = await metric_value(db, tenant_id, policy.metric, policy.window_hours)
        if not _compares(value, policy.comparator, policy.threshold):
            continue

        # One unresolved alert per policy per window.
        window_start = datetime.now(UTC) - timedelta(hours=max(1, policy.window_hours))
        existing = (
            await db.execute(
                select(Alert).where(
                    Alert.policy_id == policy.id,
                    Alert.status != AlertStatus.RESOLVED.value,
                    Alert.triggered_at >= window_start,
                )
            )
        ).scalar_one_or_none()
        if existing:
            continue

        alert = Alert(
            tenant_id=tenant_id,
            policy_id=policy.id,
            title=f"{policy.name} ({value:g} {policy.comparator} {policy.threshold:g})",
            detail=policy.description,
            severity=policy.severity,
            status=AlertStatus.OPEN.value,
            metric=policy.metric,
            metric_value=value,
            threshold=policy.threshold,
        )
        db.add(alert)
        await db.flush()
        raised.append(alert)

        await write_audit(
            db,
            action="alert.triggered",
            tenant_id=tenant_id,
            resource_type="alert",
            resource_id=alert.id,
            payload={"policy": policy.name, "metric": policy.metric, "value": value, "threshold": policy.threshold},
        )

        if policy.notify and settings_obj is not None and settings_obj.immediate_alerts:
            try:
                await NotificationDispatcher(db=db, tenant_id=tenant_id).send_alert(alert, settings_obj)
            except Exception as exc:  # noqa: BLE001 - notification failure must not lose the alert
                logger.warning("alert_notification_failed", alert_id=alert.id, error=str(exc))

    # Caller commits: a task commits once per tenant, an API request at the end.
    return raised


async def evaluate_all_tenants() -> dict[str, int]:
    """Evaluate policies for every active tenant (used by the beat task)."""
    from unimonitor.db.base import async_session_factory
    from unimonitor.db.models.tenant import Tenant

    total = 0
    tenants = 0
    async with async_session_factory() as db:
        tenant_ids = (await db.execute(select(Tenant.id).where(Tenant.is_active))).scalars().all()
        for tenant_id in tenant_ids:
            raised = await evaluate_tenant(db, tenant_id)
            await db.commit()
            tenants += 1
            total += len(raised)
    return {"tenants": tenants, "alerts": total}


def serialize_policy(policy: AlertPolicy) -> dict[str, Any]:
    return {
        "id": policy.id,
        "tenant_id": policy.tenant_id,
        "name": policy.name,
        "description": policy.description,
        "kind": policy.kind,
        "metric": policy.metric,
        "comparator": policy.comparator,
        "threshold": policy.threshold,
        "window_hours": policy.window_hours,
        "severity": policy.severity,
        "enabled": policy.enabled,
        "notify": policy.notify,
        "template_key": policy.template_key,
    }
