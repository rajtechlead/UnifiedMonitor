"""Monitoring health and collector management API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.auth.dependencies import get_current_user, require_role
from unimonitor.config import get_settings
from unimonitor.core.logging import get_logger
from unimonitor.core.tenants import resolve_tenant as _resolve_tenant
from unimonitor.db.base import get_session
from unimonitor.db.models.assessment import Assessment, AssessmentRun, AssessmentStatus
from unimonitor.db.models.tenant import Tenant
from unimonitor.db.models.user import User

logger = get_logger(__name__)
router = APIRouter()

TENANT_QUERY_DESCRIPTION = "Tenant ID (default: first active tenant)"


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
    provider: str = "microsoft"
    connected: bool = True
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
    {
        "name": "aws",
        "display_name": "Amazon Web Services",
        "description": "IAM, S3 public access and encryption, CloudTrail, GuardDuty, AWS Config, Security Hub",
        "provider": "aws",
    },
    {
        "name": "gcp",
        "display_name": "Google Cloud Platform",
        "description": "Cloud IAM, service-account keys, firewall rules, audit sinks, buckets, KMS, org policy",
        "provider": "gcp",
    },
    {
        "name": "google_workspace",
        "display_name": "Google Workspace",
        "description": "2-step verification, super admins, admin roles, OAuth grants, Drive sharing, mobile devices",
        "provider": "google_workspace",
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
    db: Annotated[AsyncSession, Depends(get_session)],
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
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    tenant_id: Annotated[str | None, Query(description=TENANT_QUERY_DESCRIPTION)] = None,
) -> list[CollectorStatus]:
    """Return the status of all data collectors for a given tenant.

    A cloud that was never connected has no collection to report: its collectors
    say ``not_connected`` instead of borrowing the last Microsoft run's success.
    """
    from unimonitor.onboarding.service import connected_providers

    tenant = await _resolve_tenant(db, tenant_id)
    connected = await connected_providers(db, tenant.id)

    # Get the last collection run per assessment
    result = await db.execute(
        select(AssessmentRun)
        .join(AssessmentRun.assessment)
        .where(AssessmentRun.assessment.has(tenant_id=tenant.id))
        .order_by(desc(AssessmentRun.started_at))
        .limit(1)
    )
    last_run = result.scalar_one_or_none()

    statuses: list[CollectorStatus] = []
    for defn in COLLECTOR_DEFINITIONS:
        provider = defn.get("provider", "microsoft")
        is_connected = provider in connected
        if not is_connected:
            last_status = "not_connected"
            last_run_time = None
            duration = None
        elif last_run:
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
                provider=provider,
                connected=is_connected,
                last_run=last_run_time,
                last_status=last_status,
                last_duration_seconds=duration,
                next_scheduled=(last_run_time + timedelta(minutes=max(1, get_settings().COLLECTION_INTERVAL_MINUTES)) if last_run_time else None),
                enabled=is_connected,
            )
        )
    return statuses


@router.post(
    "/collectors/{collector_name}/run",
    response_model=CollectorRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a specific collector",
    responses={400: {"description": "Bad request"}, 500: {"description": "Internal error"}},
)
async def run_collector(
    collector_name: str,
    current_user: Annotated[User, Depends(require_role("analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
    tenant_id: Annotated[str | None, Query(description=TENANT_QUERY_DESCRIPTION)] = None,
) -> CollectorRunResponse:
    """Trigger a named collector to run immediately for a tenant."""
    valid_names = {d["name"] for d in COLLECTOR_DEFINITIONS}
    if collector_name not in valid_names:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown collector '{collector_name}'. Valid: {sorted(valid_names)}",
        )

    tenant = await _resolve_tenant(db, tenant_id)

    try:
        from unimonitor.worker.inline import dispatch
        from unimonitor.worker.tasks.assessment import run_collector_now, run_single_collector_task

        task_id = dispatch(
            run_single_collector_task,
            run_collector_now,
            tenant_id=tenant.id,
            collector_name=collector_name,
            triggered_by=str(current_user.id),
        )
        logger.info(
            "Collector triggered",
            collector=collector_name,
            tenant_id=tenant_id,
            task_id=task_id,
        )
        return CollectorRunResponse(
            task_id=task_id,
            collector=collector_name,
            tenant_id=tenant_id,
            message=f"Collector '{collector_name}' queued successfully",
        )
    except Exception as exc:
        logger.error("Failed to queue collector", collector=collector_name, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to queue collector task") from exc


@router.get(
    "/collection-history",
    response_model=list[CollectionHistoryEntry],
    summary="Recent collection run history",
)
async def get_collection_history(
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    tenant_id: Annotated[str | None, Query(description=TENANT_QUERY_DESCRIPTION)] = None,
) -> list[CollectionHistoryEntry]:
    """Return the last N assessment runs for a tenant."""
    from unimonitor.db.models.assessment import Assessment

    tenant = await _resolve_tenant(db, tenant_id)
    result = await db.execute(
        select(AssessmentRun, Assessment)
        .join(Assessment, AssessmentRun.assessment_id == Assessment.id)
        .where(Assessment.tenant_id == tenant.id)
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


# ── Collection schedule, licensing and service health ──────────────────────


class CollectionScheduleResponse(BaseModel):
    enabled: bool
    interval_minutes: int
    next_run: datetime
    last_run: datetime | None
    collectors: int


class CollectNowResponse(BaseModel):
    task_id: str | None
    tenant_id: str
    assessment_id: str
    message: str


class LicenceSku(BaseModel):
    sku_id: str
    sku_part_number: str
    capability_status: str
    consumed: int
    prepaid: int
    available: int
    utilisation_pct: float
    status: str  # "healthy" | "unused" | "over" | "suspended"


class LicensingResponse(BaseModel):
    skus: list[LicenceSku]
    total_seats: int
    consumed_seats: int
    available_seats: int
    utilisation_pct: float
    unused_skus: int
    source: str
    generated_at: datetime


class ServiceHealthItem(BaseModel):
    service: str
    status: str
    classification: str | None = None


class ServiceIssue(BaseModel):
    id: str
    title: str
    severity: str
    status: str
    classification: str | None = None
    service: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    is_resolved: bool
    details: str | None = None


class ServiceHealthResponse(BaseModel):
    services: list[ServiceHealthItem]
    active_issues: list[ServiceIssue]
    degraded_services: int
    generated_at: datetime


async def _graph_json(tenant: Tenant, endpoint: str) -> dict[str, Any]:
    """GET one Graph collection for a tenant, raising an actionable error."""
    from unimonitor.graph.client import GraphClient

    try:
        async with GraphClient(
            tenant_id=tenant.entra_tenant_id,
            client_id=tenant.client_id,
            client_secret=tenant.client_secret,
            cache_ttl=300,
        ) as gc:
            response = await gc.get(endpoint)
    except Exception as exc:  # noqa: BLE001 - surface configuration errors to the page
        raise HTTPException(status_code=502, detail=f"Graph request failed: {exc}") from exc
    if not response.success:
        raise HTTPException(status_code=502, detail=response.error_message or "Graph request failed")
    return response.data if isinstance(response.data, dict) else {"value": response.data}


@router.get("/schedule")
async def get_collection_schedule(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    tenant_id: Annotated[str | None, Query()] = None,
) -> CollectionScheduleResponse:
    """Automatic collection interval and the next expected run."""
    from unimonitor.config import get_settings

    settings = get_settings()
    tenant = await _resolve_tenant(db, tenant_id)
    interval = max(1, settings.COLLECTION_INTERVAL_MINUTES)
    last_run = await db.scalar(
        select(AssessmentRun.started_at)
        .join(AssessmentRun.assessment)
        .where(AssessmentRun.assessment.has(tenant_id=tenant.id))
        .order_by(desc(AssessmentRun.started_at))
        .limit(1)
    )
    base = last_run or datetime.now(UTC)
    return CollectionScheduleResponse(
        enabled=settings.AUTO_COLLECTION_ENABLED,
        interval_minutes=interval,
        next_run=base + timedelta(minutes=interval),
        last_run=last_run,
        collectors=len(COLLECTOR_DEFINITIONS),
    )


@router.post("/collect", status_code=status.HTTP_202_ACCEPTED, responses={503: {"description": "Service unavailable"}})
async def collect_now(
    current_user: Annotated[User, Depends(require_role("analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
    tenant_id: Annotated[str | None, Query()] = None,
) -> CollectNowResponse:
    """Run a full collection immediately, creating a default assessment if needed."""
    import uuid

    from unimonitor.core.audit import write_audit

    tenant = await _resolve_tenant(db, tenant_id)
    assessment = (await db.execute(select(Assessment).where(Assessment.tenant_id == tenant.id, Assessment.is_active))).scalars().first()
    if assessment is None:
        assessment = Assessment(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            name="Continuous monitoring",
            description="Created automatically for manual collection",
            frameworks="",
            collectors="",
        )
        db.add(assessment)
        await db.flush()

    run = AssessmentRun(
        id=str(uuid.uuid4()),
        assessment_id=assessment.id,
        trigger="manual",
        triggered_by=current_user.id,
        status=AssessmentStatus.PENDING.value,
    )
    db.add(run)
    tenant.last_collection_at = datetime.now(UTC)
    tenant.last_collection_status = "queued"
    await write_audit(
        db,
        action="collection.started",
        tenant_id=tenant.id,
        user_id=current_user.id,
        resource_type="assessment_run",
        resource_id=run.id,
        payload={"trigger": "manual"},
    )
    # The job runs in its own session; commit so it can see the run row.
    await db.commit()

    task_id: str | None = None
    try:
        from unimonitor.worker.inline import dispatch
        from unimonitor.worker.tasks.assessment import run_assessment_now, run_assessment_task

        task_id = dispatch(
            run_assessment_task,
            run_assessment_now,
            run_id=run.id,
            tenant_id=tenant.id,
            assessment_id=assessment.id,
            frameworks=assessment.framework_list(),
            collectors=assessment.collector_list() or None,
            triggered_by=current_user.id,
        )
    except Exception as exc:  # noqa: BLE001 - the run row records the failure
        run.status = AssessmentStatus.FAILED.value
        run.error_message = f"Could not queue collection: {exc}"
        tenant.last_collection_status = "failed"
        tenant.last_collection_error = str(exc)[:500]
        await db.commit()
        raise HTTPException(status_code=503, detail="Could not queue collection; is a worker running?") from exc
    await db.commit()

    return CollectNowResponse(
        task_id=task_id,
        tenant_id=tenant.id,
        assessment_id=assessment.id,
        message="Full collection queued",
    )


@router.get("/licensing")
async def get_licensing(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    tenant_id: Annotated[str | None, Query()] = None,
) -> LicensingResponse:
    """Licence posture: seats bought, assigned, idle and suspended per SKU."""
    tenant = await _resolve_tenant(db, tenant_id)
    payload = await _graph_json(
        tenant,
        "/subscribedSkus?$select=skuId,skuPartNumber,capabilityStatus,consumedUnits,prepaidUnits",
    )
    skus: list[LicenceSku] = []
    for row in payload.get("value", []) or []:
        prepaid = int((row.get("prepaidUnits") or {}).get("enabled", 0) or 0)
        consumed = int(row.get("consumedUnits", 0) or 0)
        available = max(0, prepaid - consumed)
        utilisation = round(consumed / prepaid * 100, 1) if prepaid else 0.0
        capability = row.get("capabilityStatus", "Enabled")
        if capability != "Enabled":
            sku_status = "suspended"
        elif prepaid and available == prepaid:
            sku_status = "unused"
        elif prepaid and consumed > prepaid:
            sku_status = "over"
        else:
            sku_status = "healthy"
        skus.append(
            LicenceSku(
                sku_id=row.get("skuId", ""),
                sku_part_number=row.get("skuPartNumber", ""),
                capability_status=capability,
                consumed=consumed,
                prepaid=prepaid,
                available=available,
                utilisation_pct=utilisation,
                status=sku_status,
            )
        )
    skus.sort(key=lambda s: s.sku_part_number)
    total = sum(s.prepaid for s in skus)
    used = sum(s.consumed for s in skus)
    return LicensingResponse(
        skus=skus,
        total_seats=total,
        consumed_seats=used,
        available_seats=max(0, total - used),
        utilisation_pct=round(used / total * 100, 1) if total else 0.0,
        unused_skus=sum(1 for s in skus if s.status == "unused"),
        source="Microsoft Graph /subscribedSkus",
        generated_at=datetime.now(UTC),
    )


@router.get("/service-health")
async def get_service_health(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    tenant_id: Annotated[str | None, Query()] = None,
) -> ServiceHealthResponse:
    """Microsoft 365 service health and unresolved advisories."""
    tenant = await _resolve_tenant(db, tenant_id)
    health = await _graph_json(tenant, "/admin/serviceAnnouncement/healthOverviews")
    issues_payload = await _graph_json(
        tenant,
        "/admin/serviceAnnouncement/issues?$filter=isResolved eq false&$top=50",
    )

    services = [
        ServiceHealthItem(
            service=row.get("service", "Unknown"),
            status=row.get("status", "unknown"),
        )
        for row in health.get("value", []) or []
    ]
    issues = [
        ServiceIssue(
            id=row.get("id", ""),
            title=row.get("title", ""),
            severity=row.get("severity", ""),
            status=row.get("status", ""),
            classification=row.get("classification"),
            service=row.get("service"),
            start_time=row.get("startDateTime"),
            end_time=row.get("endDateTime"),
            is_resolved=bool(row.get("isResolved", False)),
            details=row.get("impactDescription") or row.get("body", {}).get("content") if isinstance(row.get("body"), dict) else None,
        )
        for row in issues_payload.get("value", []) or []
    ]
    return ServiceHealthResponse(
        services=services,
        active_issues=issues,
        degraded_services=sum(1 for s in services if s.status.lower() not in {"serviceoperational", "operational"}),
        generated_at=datetime.now(UTC),
    )
