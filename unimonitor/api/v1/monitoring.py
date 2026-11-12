"""Monitoring health and collector management API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.auth.dependencies import get_current_user, require_role
from unimonitor.core.logging import get_logger
from unimonitor.db.base import get_session
from unimonitor.db.models.assessment import AssessmentRun, AssessmentStatus
from unimonitor.db.models.tenant import Tenant
from unimonitor.db.models.user import User

logger = get_logger(__name__)
router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────

class PlatformHealthResponse(BaseModel):
    status: str
    timestamp: datetime
    database: dict[str, Any]
    redis: dict[str, Any]
    celery: dict[str, Any]
    graph_connectivity: dict[str, Any]
    version: str = "1.0.0"


class CollectorStatus(BaseModel):
    name: str
    display_name: str
    description: str
    last_run: datetime | None
    last_status: str | None  # "success" | "partial" | "failed" | "never"
    last_duration_seconds: float | None
    next_scheduled: datetime | None
    enabled: bool


class CollectorRunResponse(BaseModel):
    task_id: str
    collector: str
    tenant_id: str
    message: str


class CollectionHistoryEntry(BaseModel):
    id: str
    assessment_id: str
    assessment_name: str
    trigger: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: float | None
    total_controls_checked: int
    controls_passed: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    informational_count: int
    security_score: float | None
    compliance_score: float | None
    error_message: str | None


# ── Known collector definitions ────────────────────────────────────────────

COLLECTOR_DEFINITIONS = [
    {
        "name": "entra_id",
        "display_name": "Microsoft Entra ID",
        "description": "Conditional Access, MFA, Identity Protection, PIM, Risky Users/Sign-ins, Auth Methods",
    },
    {
        "name": "intune",
        "display_name": "Microsoft Intune",
        "description": "Device compliance, endpoint security, security baselines, app protection, app inventory",
    },
    {
        "name": "defender",
        "display_name": "Microsoft Defender",
        "description": "Defender for Endpoint, Office 365, Identity, Cloud Apps, XDR incidents and alerts",
    },
    {
        "name": "purview",
        "display_name": "Microsoft Purview",
        "description": "Information protection, DLP policies, insider risk, eDiscovery, data governance",
    },
    {
        "name": "exchange",
        "display_name": "Exchange Online",
        "description": "Mail flow rules, anti-spam/phish policies, connectors, audit log settings",
    },
    {
        "name": "sharepoint",
        "display_name": "SharePoint Online",
        "description": "Sharing policies, external access, site permissions, information barriers",
    },
    {
        "name": "teams",
        "display_name": "Microsoft Teams",
        "description": "Teams policies, external access, guest settings, meeting policies",
    },
    {
        "name": "copilot",
        "display_name": "Microsoft Copilot",
        "description": "Copilot for M365 configuration, data access controls, usage policies",
    },
    {
        "name": "azure_security",
        "display_name": "Azure Security",
        "description": "Azure Security Center, Defender for Cloud, subscription security posture",
    },
    {
        "name": "secure_score",
        "display_name": "Secure Score",
        "description": "Microsoft Secure Score trends, improvement actions, comparison data",
    },
]


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=PlatformHealthResponse,
    summary="Platform health check",
)
async def get_platform_health(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_session),
) -> PlatformHealthResponse:
    """Return health status of all platform components."""
    import time

    from unimonitor.core.cache import get_redis

    now = datetime.now(UTC)

    # Database check
    db_status: dict[str, Any] = {"status": "unknown", "latency_ms": None}
    try:
        t0 = time.monotonic()
        await db.execute(select(1))
        db_status = {"status": "healthy", "latency_ms": round((time.monotonic() - t0) * 1000, 2)}
    except Exception as exc:
        db_status = {"status": "unhealthy", "error": str(exc)}

    # Redis check
    redis_status: dict[str, Any] = {"status": "unknown", "latency_ms": None}
    try:
        t0 = time.monotonic()
        redis_client = await get_redis()
        await redis_client.ping()
        redis_status = {"status": "healthy", "latency_ms": round((time.monotonic() - t0) * 1000, 2)}
    except Exception as exc:
        redis_status = {"status": "unhealthy", "error": str(exc)}

    # Celery check
    celery_status: dict[str, Any] = {"status": "unknown"}
    try:
        from unimonitor.worker.celery_app import celery_app
        inspect = celery_app.control.inspect(timeout=2.0)
        ping_result = inspect.ping()
        if ping_result:
            worker_count = len(ping_result)
            celery_status = {"status": "healthy", "workers": worker_count}
        else:
            celery_status = {"status": "degraded", "workers": 0, "note": "No workers responding"}
    except Exception as exc:
        celery_status = {"status": "unhealthy", "error": str(exc)[:200]}

    # Graph connectivity check (using default tenant if any)
    graph_status: dict[str, Any] = {"status": "not_configured"}
    try:
        result = await db.execute(select(Tenant).where(Tenant.is_active).limit(1))
        tenant = result.scalar_one_or_none()
        if tenant:
            from unimonitor.graph.client import GraphClient
            async with GraphClient(
                tenant_id=tenant.entra_tenant_id,
                client_id=tenant.client_id,
                client_secret=tenant.client_secret,
                cache_ttl=60,
            ) as gc:
                t0 = time.monotonic()
                resp = await gc.get("/organization", use_cache=False)
                latency = round((time.monotonic() - t0) * 1000, 2)
                if resp.success:
                    graph_status = {"status": "healthy", "latency_ms": latency}
                else:
                    graph_status = {"status": "degraded", "error": resp.error_message}
        else:
            graph_status = {"status": "not_configured", "note": "No active tenants"}
    except Exception as exc:
        graph_status = {"status": "unhealthy", "error": str(exc)[:200]}

    overall = "healthy"
    if db_status["status"] != "healthy":
        overall = "unhealthy"
    elif redis_status["status"] != "healthy" or celery_status.get("status") not in ("healthy", "not_configured"):
        overall = "degraded"

    return PlatformHealthResponse(
        status=overall,
        timestamp=now,
        database=db_status,
        redis=redis_status,
        celery=celery_status,
        graph_connectivity=graph_status,
    )


@router.get(
    "/collectors",
    summary="Get collector status for a tenant",
)
async def get_collectors(
    tenant_id: Annotated[str, Query(description="Tenant ID")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_session),
) -> list[CollectorStatus]:
    """Return the status of all data collectors for a given tenant."""
    # Verify tenant exists
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Get the last collection run per assessment
    result = await db.execute(
        select(AssessmentRun)
        .join(AssessmentRun.assessment)
        .where(AssessmentRun.assessment.has(tenant_id=tenant_id))
        .order_by(desc(AssessmentRun.started_at))
        .limit(1)
    )
    last_run = result.scalar_one_or_none()

    statuses: list[CollectorStatus] = []
    for defn in COLLECTOR_DEFINITIONS:
        if last_run:
            last_status = "success" if last_run.status == AssessmentStatus.COMPLETED.value else last_run.status
            last_run_time = last_run.started_at
            duration = last_run.duration_seconds
        else:
            last_status = "never"
            last_run_time = None
            duration = None

        statuses.append(
            CollectorStatus(
                name=defn["name"],
                display_name=defn["display_name"],
                description=defn["description"],
                last_run=last_run_time,
                last_status=last_status,
                last_duration_seconds=duration,
                next_scheduled=None,
                enabled=True,
            )
        )
    return statuses


@router.post(
    "/collectors/{collector_name}/run",
    response_model=CollectorRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a specific collector",
)
async def run_collector(
    collector_name: str,
    tenant_id: Annotated[str, Query(description="Tenant ID")],
    current_user: Annotated[User, Depends(require_role("analyst"))],
    db: AsyncSession = Depends(get_session),
) -> CollectorRunResponse:
    """Trigger a named collector to run immediately for a tenant."""
    valid_names = {d["name"] for d in COLLECTOR_DEFINITIONS}
    if collector_name not in valid_names:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown collector '{collector_name}'. Valid: {sorted(valid_names)}",
        )

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    try:
        from unimonitor.worker.tasks.assessment import run_single_collector_task
        task = run_single_collector_task.delay(
            tenant_id=tenant_id,
            collector_name=collector_name,
            triggered_by=str(current_user.id),
        )
        logger.info(
            "Collector triggered",
            collector=collector_name,
            tenant_id=tenant_id,
            task_id=task.id,
        )
        return CollectorRunResponse(
            task_id=task.id,
            collector=collector_name,
            tenant_id=tenant_id,
            message=f"Collector '{collector_name}' queued successfully",
        )
    except Exception as exc:
        logger.error("Failed to queue collector", collector=collector_name, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to queue collector task")


@router.get(
    "/collection-history",
    response_model=list[CollectionHistoryEntry],
    summary="Recent collection run history",
)
async def get_collection_history(
    tenant_id: Annotated[str, Query(description="Tenant ID")],
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CollectionHistoryEntry]:
    """Return the last N assessment runs for a tenant."""
    from unimonitor.db.models.assessment import Assessment

    result = await db.execute(
        select(AssessmentRun, Assessment)
        .join(Assessment, AssessmentRun.assessment_id == Assessment.id)
        .where(Assessment.tenant_id == tenant_id)
        .order_by(desc(AssessmentRun.started_at))
        .limit(limit)
    )
    rows = result.all()

    history: list[CollectionHistoryEntry] = []
    for run, assessment in rows:
        history.append(
            CollectionHistoryEntry(
                id=run.id,
                assessment_id=assessment.id,
                assessment_name=assessment.name,
                trigger=run.trigger,
                status=run.status,
                started_at=run.started_at,
                completed_at=run.completed_at,
                duration_seconds=run.duration_seconds,
                total_controls_checked=run.total_controls_checked,
                controls_passed=run.controls_passed,
                critical_count=run.critical_count,
                high_count=run.high_count,
                medium_count=run.medium_count,
                low_count=run.low_count,
                informational_count=run.informational_count,
                security_score=run.security_score,
                compliance_score=run.compliance_score,
                error_message=run.error_message,
            )
        )
    return history
