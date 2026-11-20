"""Dashboard data APIs — all views."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.auth.dependencies import get_current_user
from unimonitor.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── Common schemas ────────────────────────────────────────────


class ScoreSummary(BaseModel):
    security_score: float
    compliance_score: float
    risk_score: float
    score_trend_7d: float


class FindingCounts(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    informational: int = 0
    total: int = 0


class StateCounts(BaseModel):
    implemented: int = 0
    partially_implemented: int = 0
    not_implemented: int = 0
    not_applicable: int = 0


class TopFinding(BaseModel):
    id: str
    title: str
    severity: str
    category: str
    service: str
    first_detected_at: datetime


class ActivityItem(BaseModel):
    timestamp: datetime
    event_type: str
    description: str
    actor: str | None = None


class MonitoringHealth(BaseModel):
    last_collection_at: datetime | None
    collection_status: str
    collectors_online: int
    collectors_total: int
    graph_api_latency_ms: float | None


class OverviewResponse(BaseModel):
    scores: ScoreSummary
    finding_counts: FindingCounts
    state_counts: StateCounts
    top_findings: list[TopFinding]
    recent_activity: list[ActivityItem]
    monitoring_health: MonitoringHealth
    tenant_id: str | None
    generated_at: datetime


class TrendPoint(BaseModel):
    date: str
    security_score: float
    compliance_score: float
    risk_score: float


class FrameworkCoverage(BaseModel):
    framework_id: str
    framework_name: str
    coverage_pct: float
    controls_total: int
    controls_passed: int


class ZeroTrustPlatformScore(BaseModel):
    source: str
    platform: str
    has_run: bool
    score: float
    total: int
    passed: int
    failed: int
    last_run: datetime | None


class ExecutiveSummaryResponse(BaseModel):
    scores: ScoreSummary
    score_trends: list[TrendPoint]
    top_risks: list[TopFinding]
    framework_coverage: list[FrameworkCoverage]
    zero_trust: list[ZeroTrustPlatformScore] = []
    asset_coverage_pct: float
    remediation_progress_pct: float
    generated_at: datetime


class CategoryBreakdown(BaseModel):
    category: str
    critical: int
    high: int
    medium: int
    low: int
    informational: int
    total: int


class SecurityViewResponse(BaseModel):
    finding_counts: FindingCounts
    by_category: list[CategoryBreakdown]
    identity_findings: list[TopFinding]
    device_findings: list[TopFinding]
    threat_findings: list[TopFinding]
    generated_at: datetime


class ComplianceViewResponse(BaseModel):
    overall_compliance_score: float
    frameworks: list[FrameworkCoverage]
    controls_by_category: dict[str, StateCounts]
    generated_at: datetime


class RiskCell(BaseModel):
    likelihood: int
    impact: int
    count: int
    findings: list[str]


class RiskViewResponse(BaseModel):
    overall_risk_score: float
    heatmap: list[RiskCell]
    critical_risks: list[TopFinding]
    risks: list[TopFinding] = []
    generated_at: datetime


class SocViewResponse(BaseModel):
    active_alerts: int
    acknowledged_alerts: int
    resolved_alerts_24h: int
    mean_time_to_acknowledge_hours: float | None
    mean_time_to_resolve_hours: float | None
    alerts_by_severity: FindingCounts
    incident_trend: list[dict]
    generated_at: datetime


class AuditEntry(BaseModel):
    id: str
    action: str
    resource_type: str | None
    resource_id: str | None
    actor: str | None
    entry_hash: str | None = None
    created_at: datetime


class AuditChainResponse(BaseModel):
    valid: bool
    checked: int
    legacy: int
    broken_at: str | None = None
    reason: str | None = None


class CloudAuditEntry(BaseModel):
    id: str
    source: str
    action: str
    actor: str
    target: str = ""
    created_at: datetime


class AuditViewResponse(BaseModel):
    entries: list[AuditEntry]
    total: int
    actions_24h: int
    cloud_events: list[CloudAuditEntry] = []
    generated_at: datetime


class TrendsResponse(BaseModel):
    window_days: int
    score_trends: list[TrendPoint]
    finding_trend: list[dict]
    generated_at: datetime


# ── Shared helpers (accept db session) ───────────────────────


async def _get_scores_for_tenant(db: AsyncSession, tenant_id: str | None) -> tuple[float, float, float]:
    """Return (security, compliance, risk) scores."""
    from unimonitor.db.repositories.assessment_repo import AssessmentRepository

    repo = AssessmentRepository(db)
    latest_run = await repo.get_latest_completed_run(tenant_id=tenant_id)
    if latest_run:
        return (
            latest_run.security_score or 0.0,
            latest_run.compliance_score or 0.0,
            latest_run.risk_score or 0.0,
        )
    return 0.0, 0.0, 0.0


async def _get_finding_counts(db: AsyncSession, tenant_id: str | None) -> FindingCounts:
    from unimonitor.db.repositories.finding_repo import FindingRepository

    repo = FindingRepository(db)
    summary = await repo.get_summary(tenant_id=tenant_id)

    by_sev = summary.get("by_severity", {})
    total = sum(by_sev.values())
    return FindingCounts(
        critical=by_sev.get("critical", 0),
        high=by_sev.get("high", 0),
        medium=by_sev.get("medium", 0),
        low=by_sev.get("low", 0),
        informational=by_sev.get("informational", 0),
        total=total,
    )


async def _get_top_findings_list(db: AsyncSession, tenant_id: str | None, limit: int = 10) -> list[TopFinding]:
    from unimonitor.db.repositories.finding_repo import FindingRepository

    repo = FindingRepository(db)
    raw = await repo.get_top_findings(tenant_id=tenant_id, limit=limit)

    return [
        TopFinding(
            id=f.id,
            title=f.title,
            severity=f.severity,
            category=f.category,
            service=f.service,
            first_detected_at=f.first_detected_at,
        )
        for f in raw
    ]


async def _build_zero_trust_scores(db: AsyncSession, tenant_id: str | None) -> list[ZeroTrustPlatformScore]:
    """Latest Zero Trust Assessment score per platform, for the executive board."""
    from sqlalchemy import select

    from unimonitor.db.models.tenant import Tenant
    from unimonitor.zerotrust import service
    from unimonitor.zerotrust.normalise import PLATFORMS

    if not tenant_id:
        tenant_id = (await db.execute(select(Tenant.id).where(Tenant.is_active.is_(True)).order_by(Tenant.created_at).limit(1))).scalar_one_or_none()
    if not tenant_id:
        return []

    latest = await service.latest_by_source(db, tenant_id)
    rows: list[ZeroTrustPlatformScore] = []
    for source, label in PLATFORMS.items():
        run = latest.get(source)
        rows.append(
            ZeroTrustPlatformScore(
                source=source,
                platform=label,
                has_run=run is not None,
                score=run.score if run else 0.0,
                total=run.total if run else 0,
                passed=run.passed if run else 0,
                failed=run.failed if run else 0,
                last_run=run.created_at if run else None,
            )
        )
    return rows


async def _build_framework_coverage(db: AsyncSession, tenant_id: str | None) -> list[FrameworkCoverage]:
    """Build framework coverage data from findings vs control mappings."""
    try:
        from unimonitor.api.v1.controls import SUPPORTED_FRAMEWORKS
        from unimonitor.grc.scoring import compute_framework_coverage

        coverages = await compute_framework_coverage(db, tenant_id=tenant_id)
    except Exception:
        return []

    result = []
    for fw in SUPPORTED_FRAMEWORKS:
        cov = coverages.get(fw["id"], {})
        result.append(
            FrameworkCoverage(
                framework_id=fw["id"],
                framework_name=fw["name"],
                coverage_pct=cov.get("coverage_pct", 0.0),
                controls_total=cov.get("controls_total", 0),
                controls_passed=cov.get("controls_passed", 0),
            )
        )
    return result


# ── Endpoints ────────────────────────────────────────────────


@router.get("/overview", response_model=OverviewResponse)
async def dashboard_overview(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> OverviewResponse:
    """Overview dashboard: scores, finding counts, monitoring health."""
    sec, comp, risk = await _get_scores_for_tenant(db, tenant_id)
    finding_counts = await _get_finding_counts(db, tenant_id)

    from unimonitor.db.repositories.finding_repo import FindingRepository

    repo = FindingRepository(db)
    summary = await repo.get_summary(tenant_id=tenant_id)
    top_raw = await repo.get_top_findings(tenant_id=tenant_id, limit=5)
    activity_raw = await repo.get_recent_activity(tenant_id=tenant_id, limit=10)

    by_state = summary.get("by_state", {})
    state_counts = StateCounts(
        implemented=by_state.get("implemented", 0),
        partially_implemented=by_state.get("partially_implemented", 0),
        not_implemented=by_state.get("not_implemented", 0),
        not_applicable=by_state.get("not_applicable", 0),
    )

    top_findings = [
        TopFinding(
            id=f.id,
            title=f.title,
            severity=f.severity,
            category=f.category,
            service=f.service,
            first_detected_at=f.first_detected_at,
        )
        for f in top_raw
    ]

    activity = [
        ActivityItem(
            timestamp=a.get("timestamp", datetime.now(UTC)),
            event_type=a.get("event_type", ""),
            description=a.get("description", ""),
            actor=a.get("actor"),
        )
        for a in activity_raw
    ]

    health = MonitoringHealth(
        last_collection_at=None,
        collection_status="unknown",
        collectors_online=0,
        collectors_total=0,
        graph_api_latency_ms=None,
    )

    return OverviewResponse(
        scores=ScoreSummary(
            security_score=sec,
            compliance_score=comp,
            risk_score=risk,
            score_trend_7d=0.0,
        ),
        finding_counts=finding_counts,
        state_counts=state_counts,
        top_findings=top_findings,
        recent_activity=activity,
        monitoring_health=health,
        tenant_id=tenant_id,
        generated_at=datetime.now(UTC),
    )


@router.get("/executive", response_model=ExecutiveSummaryResponse)
async def dashboard_executive(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> ExecutiveSummaryResponse:
    """Executive dashboard view."""
    sec, comp, risk = await _get_scores_for_tenant(db, tenant_id)
    top_findings = await _get_top_findings_list(db, tenant_id, limit=10)

    from unimonitor.db.repositories.assessment_repo import AssessmentRepository

    repo = AssessmentRepository(db)
    trend_points = await repo.get_score_trends(tenant_id=tenant_id, days=30)
    framework_coverage = await _build_framework_coverage(db, tenant_id)
    zero_trust = await _build_zero_trust_scores(db, tenant_id)

    return ExecutiveSummaryResponse(
        scores=ScoreSummary(
            security_score=sec,
            compliance_score=comp,
            risk_score=risk,
            score_trend_7d=0.0,
        ),
        score_trends=[
            TrendPoint(
                date=p.get("date", ""),
                security_score=p.get("security_score", 0.0),
                compliance_score=p.get("compliance_score", 0.0),
                risk_score=p.get("risk_score", 0.0),
            )
            for p in trend_points
        ],
        top_risks=top_findings[:5],
        framework_coverage=framework_coverage,
        zero_trust=zero_trust,
        asset_coverage_pct=0.0,
        remediation_progress_pct=0.0,
        generated_at=datetime.now(UTC),
    )


@router.get("/security", response_model=SecurityViewResponse)
async def dashboard_security(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> SecurityViewResponse:
    """Security operations dashboard view."""
    finding_counts = await _get_finding_counts(db, tenant_id)
    top_findings = await _get_top_findings_list(db, tenant_id, limit=20)

    identity_findings = [f for f in top_findings if f.category.lower() in ("identity", "entra_id")][:5]
    device_findings = [f for f in top_findings if f.category.lower() in ("devices", "intune", "endpoint")][:5]
    threat_findings = [f for f in top_findings if f.category.lower() in ("defender", "threats", "soc")][:5]

    from unimonitor.db.repositories.finding_repo import FindingRepository

    repo = FindingRepository(db)
    summary = await repo.get_summary(tenant_id=tenant_id)

    by_cat = summary.get("by_category", {})
    category_breakdowns = [
        CategoryBreakdown(
            category=cat,
            critical=counts.get("critical", 0) if isinstance(counts, dict) else 0,
            high=counts.get("high", 0) if isinstance(counts, dict) else 0,
            medium=counts.get("medium", 0) if isinstance(counts, dict) else 0,
            low=counts.get("low", 0) if isinstance(counts, dict) else 0,
            informational=counts.get("informational", 0) if isinstance(counts, dict) else 0,
            total=counts.get("total", 0) if isinstance(counts, dict) else counts,
        )
        for cat, counts in by_cat.items()
    ]

    return SecurityViewResponse(
        finding_counts=finding_counts,
        by_category=category_breakdowns,
        identity_findings=identity_findings,
        device_findings=device_findings,
        threat_findings=threat_findings,
        generated_at=datetime.now(UTC),
    )


@router.get("/compliance", response_model=ComplianceViewResponse)
async def dashboard_compliance(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> ComplianceViewResponse:
    """Compliance dashboard view — framework coverage percentages."""
    _, comp, _ = await _get_scores_for_tenant(db, tenant_id)
    framework_coverage = await _build_framework_coverage(db, tenant_id)

    return ComplianceViewResponse(
        overall_compliance_score=comp,
        frameworks=framework_coverage,
        controls_by_category={},
        generated_at=datetime.now(UTC),
    )


@router.get("/risk", response_model=RiskViewResponse)
async def dashboard_risk(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> RiskViewResponse:
    """Risk dashboard — heatmap and every open risk, so nothing is hidden behind "critical"."""
    from sqlalchemy import select

    from unimonitor.db.models.finding import Finding
    from unimonitor.db.repositories.finding_repo import FindingRepository

    _, _, risk = await _get_scores_for_tenant(db, tenant_id)
    repo = FindingRepository(db)
    heatmap_data = await repo.get_risk_heatmap(tenant_id=tenant_id)

    stmt = select(Finding).where(
        Finding.state.in_(["not_implemented", "partially_implemented"]),
        Finding.is_suppressed.is_(False),
    )
    if tenant_id:
        stmt = stmt.where(Finding.tenant_id == tenant_id)
    stmt = stmt.order_by(Finding.risk_score.desc()).limit(200)
    open_rows = (await db.execute(stmt)).scalars().all()
    open_risks = [
        TopFinding(
            id=f.id,
            title=f.title,
            severity=f.severity,
            category=f.category,
            service=f.service,
            first_detected_at=f.first_detected_at,
        )
        for f in open_rows
    ]

    return RiskViewResponse(
        overall_risk_score=risk,
        heatmap=[
            RiskCell(
                likelihood=cell.get("likelihood", 1),
                impact=cell.get("impact", 1),
                count=cell.get("count", 0),
                findings=cell.get("finding_ids", []),
            )
            for cell in heatmap_data
        ],
        critical_risks=[f for f in open_risks if f.severity == "critical"],
        risks=open_risks,
        generated_at=datetime.now(UTC),
    )


@router.get("/soc", response_model=SocViewResponse)
async def dashboard_soc(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> SocViewResponse:
    """SOC operations dashboard view."""
    finding_counts = await _get_finding_counts(db, tenant_id)

    return SocViewResponse(
        active_alerts=finding_counts.total,
        acknowledged_alerts=0,
        resolved_alerts_24h=0,
        mean_time_to_acknowledge_hours=None,
        mean_time_to_resolve_hours=None,
        alerts_by_severity=finding_counts,
        incident_trend=[],
        generated_at=datetime.now(UTC),
    )


@router.get("/audit", response_model=AuditViewResponse)
async def dashboard_audit(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
) -> AuditViewResponse:
    """Audit view — recent audit trail entries and 24h activity."""
    from sqlalchemy import func, select

    from unimonitor.db.models.audit_log import AuditLog

    rows = (await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))).scalars().all()
    total = await db.scalar(select(func.count()).select_from(AuditLog)) or 0
    since = datetime.now(UTC) - timedelta(hours=24)
    actions_24h = await db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.created_at >= since)) or 0

    # Platform activity (M365 / AWS / GCP / Workspace), not just this app's own log.
    from unimonitor.core.cloud_audit import cloud_events as read_cloud_events

    try:
        cloud_rows = await read_cloud_events(db, limit=limit)
    except Exception as exc:  # noqa: BLE001 - the app audit trail must still render
        logger.warning("cloud_audit_unavailable", error=str(exc)[:200])
        cloud_rows = []

    return AuditViewResponse(
        entries=[
            AuditEntry(
                id=r.id,
                action=r.action,
                resource_type=r.resource_type,
                resource_id=r.resource_id,
                actor=r.user_id,
                entry_hash=r.entry_hash,
                created_at=r.created_at,
            )
            for r in rows
        ],
        total=total,
        actions_24h=actions_24h,
        cloud_events=[
            CloudAuditEntry(
                id=row["id"],
                source=row["source"],
                action=row["action"],
                actor=row["actor"],
                target=row["target"],
                created_at=row["created_at"],
            )
            for row in cloud_rows
        ],
        generated_at=datetime.now(UTC),
    )


@router.get("/audit/verify", response_model=AuditChainResponse)
async def verify_audit_chain(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=5000, ge=1, le=50000),
) -> AuditChainResponse:
    """Recompute the audit hash chain and report the first break."""
    from unimonitor.core.audit import verify_chain

    result = await verify_chain(db, limit=limit)
    return AuditChainResponse(**result)


@router.get("/trends", response_model=TrendsResponse)
async def dashboard_trends(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
    window_days: int = Query(default=30, ge=7, le=365),
) -> TrendsResponse:
    """Historical score and finding trends."""
    from unimonitor.db.repositories.assessment_repo import AssessmentRepository

    repo = AssessmentRepository(db)
    trend_points = await repo.get_score_trends(tenant_id=tenant_id, days=window_days)
    finding_trend = await repo.get_finding_trends(tenant_id=tenant_id, days=window_days)

    return TrendsResponse(
        window_days=window_days,
        score_trends=[
            TrendPoint(
                date=p.get("date", ""),
                security_score=p.get("security_score", 0.0),
                compliance_score=p.get("compliance_score", 0.0),
                risk_score=p.get("risk_score", 0.0),
            )
            for p in trend_points
        ],
        finding_trend=finding_trend,
        generated_at=datetime.now(UTC),
    )


# ── Multi-cloud dashboards ───────────────────────────────────
#
# The platform monitors several clouds; these views roll the existing control
# library and findings up per provider, plus an aggregate across all of them.
# Provider membership is defined in unimonitor/grc/providers.py.


class ProviderServiceBreakdown(BaseModel):
    service: str
    controls_total: int
    controls_passed: int
    findings: int


class ProviderControlCategory(BaseModel):
    category: str
    controls_total: int
    controls_passed: int
    coverage_pct: float


class CloudProviderSummary(BaseModel):
    provider_id: str
    name: str
    short_name: str
    description: str
    connected: bool
    controls_total: int
    controls_passed: int
    coverage_pct: float
    scores: ScoreSummary
    finding_counts: FindingCounts
    state_counts: StateCounts
    services: list[str]
    collectors: list[str]
    credential_settings: list[str]


class CloudTotals(BaseModel):
    providers_total: int
    providers_connected: int
    controls_total: int
    controls_passed: int
    coverage_pct: float
    findings_total: int
    critical: int
    high: int


class CloudAggregateResponse(BaseModel):
    providers: list[CloudProviderSummary]
    totals: CloudTotals
    overall_scores: ScoreSummary
    generated_at: datetime


class CloudProviderDetailResponse(BaseModel):
    provider: CloudProviderSummary
    services: list[ProviderServiceBreakdown]
    categories: list[ProviderControlCategory]
    frameworks: list[FrameworkCoverage]
    top_findings: list[TopFinding]
    generated_at: datetime


@cache
def _provider_controls_cached(provider_id: str) -> tuple:
    """Control definitions owned by one provider (loaded once per process).

    The control YAML is static at runtime and every dashboard request asks for
    all providers, so re-reading the library per provider was pure overhead.
    """
    from unimonitor.grc.control_loader import ControlLoader
    from unimonitor.grc.providers import provider_for_service

    return tuple(c for c in ControlLoader().load_all() if (p := provider_for_service(c.service)) and p.id == provider_id)


def _provider_controls(provider_id: str) -> list:
    """Control definitions owned by one provider (a copy callers may sort)."""
    return list(_provider_controls_cached(provider_id))


def _count_states(findings: list) -> tuple[FindingCounts, StateCounts, float, float, float]:
    """Return (severity counts, state counts, security, compliance, risk)."""
    from unimonitor.grc.scoring import calculate_scores

    sev = {"critical": 0, "high": 0, "medium": 0, "low": 0, "informational": 0}
    states = {"implemented": 0, "partially_implemented": 0, "not_implemented": 0, "not_applicable": 0}
    for f in findings:
        if f.severity in sev:
            sev[f.severity] += 1
        if f.state in states:
            states[f.state] += 1

    finding_counts = FindingCounts(total=len(findings), **sev)
    state_counts = StateCounts(**states)
    if not findings:
        return finding_counts, state_counts, 0.0, 0.0, 0.0

    scores = calculate_scores(findings)
    return (
        finding_counts,
        state_counts,
        scores["security_score"],
        scores["compliance_score"],
        scores["risk_score"],
    )


def _summarise_provider(provider, findings: list, controls: list, connected: bool | None = None) -> CloudProviderSummary:
    """One provider row. An unconnected cloud reports no data, not false findings."""
    is_connected = bool(findings) if connected is None else connected
    if not is_connected:
        findings = []
    finding_counts, state_counts, sec, comp, risk = _count_states(findings)
    states = {f.external_control_id: f.state for f in findings}
    applicable = [c for c in controls if states.get(c.id) != "not_applicable"]
    passed = sum(1 for c in applicable if states.get(c.id) == "implemented")
    coverage = round((passed / len(applicable)) * 100, 2) if applicable else 0.0

    return CloudProviderSummary(
        provider_id=provider.id,
        name=provider.name,
        short_name=provider.short_name,
        description=provider.description,
        connected=is_connected,
        controls_total=len(controls),
        controls_passed=passed,
        coverage_pct=coverage,
        scores=ScoreSummary(
            security_score=sec,
            compliance_score=comp,
            risk_score=risk,
            score_trend_7d=0.0,
        ),
        finding_counts=finding_counts,
        state_counts=state_counts,
        services=list(provider.services),
        collectors=list(provider.collectors),
        credential_settings=list(provider.credential_settings),
    )


def _provider_frameworks(controls: list, findings: list) -> list[FrameworkCoverage]:
    from unimonitor.api.v1.controls import SUPPORTED_FRAMEWORKS

    states = {f.external_control_id: f.state for f in findings}
    out: list[FrameworkCoverage] = []
    for fw in SUPPORTED_FRAMEWORKS:
        keys = {fw["id"], fw["id"].replace("-", "_")}
        mapped = [c for c in controls if keys & set(c.compliance_mapping)]
        if not mapped:
            continue
        applicable = [c for c in mapped if states.get(c.id) != "not_applicable"]
        credit = sum(1.0 if states.get(c.id) == "implemented" else 0.5 if states.get(c.id) == "partially_implemented" else 0.0 for c in applicable)
        out.append(
            FrameworkCoverage(
                framework_id=fw["id"],
                framework_name=fw["name"],
                coverage_pct=round((credit / len(applicable)) * 100, 2) if applicable else 0.0,
                controls_total=len(mapped),
                controls_passed=sum(1 for c in applicable if states.get(c.id) == "implemented"),
            )
        )
    return out


async def _load_findings(db: AsyncSession, tenant_id: str | None) -> list:
    from unimonitor.db.repositories.finding_repo import FindingRepository

    rows, _ = await FindingRepository(db).list_paginated(tenant_id=tenant_id, page_size=1000)
    return list(rows)


def _group_by_provider(findings: list) -> dict[str, list]:
    from unimonitor.grc.providers import provider_for_service, provider_ids

    groups: dict[str, list] = {pid: [] for pid in provider_ids()}
    for f in findings:
        provider = provider_for_service(f.service)
        if provider:
            groups[provider.id].append(f)
    return groups


class PillarScore(BaseModel):
    id: str
    name: str
    description: str
    controls_total: int
    implemented: int
    partial: int
    not_implemented: int
    not_applicable: int
    coverage_pct: float
    status: str  # "covered" | "gap" | "uncovered"


class ZeroTrustResponse(BaseModel):
    pillars: list[PillarScore]
    overall_coverage_pct: float
    generated_at: datetime


def _pillar_buckets(states: dict[str, str]) -> dict[str, dict[str, int]]:
    """Count control states per Zero Trust pillar from each control's mapping."""
    from unimonitor.db.models.finding import FindingState
    from unimonitor.grc.control_loader import ControlLoader
    from unimonitor.grc.pillars import PILLARS, pillar_for

    # Control state → the bucket it increments; anything unrecognised is unimplemented.
    buckets_for = {
        FindingState.IMPLEMENTED.value: "implemented",
        FindingState.PARTIALLY_IMPLEMENTED.value: "partial",
        FindingState.NOT_APPLICABLE.value: "not_applicable",
    }
    buckets: dict[str, dict[str, int]] = {
        pillar.id: {"implemented": 0, "partial": 0, "not_implemented": 0, "not_applicable": 0} for pillar in PILLARS
    }
    for control in ControlLoader().load_all():
        state = states.get(control.id, FindingState.NOT_IMPLEMENTED.value)
        bucket_name = buckets_for.get(state, "not_implemented")
        for mapping in control.compliance_mapping.get("zero_trust", []) or []:
            pillar_id = pillar_for(str(mapping))
            if pillar_id is not None and pillar_id in buckets:
                buckets[pillar_id][bucket_name] += 1
    return buckets


@router.get("/zero-trust", response_model=ZeroTrustResponse)
async def dashboard_zero_trust(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> ZeroTrustResponse:
    """Coverage per Zero Trust pillar, grouped from each control's ``zero_trust`` mapping."""
    from sqlalchemy import select

    from unimonitor.db.models.finding import Finding
    from unimonitor.grc.pillars import PILLARS

    stmt = select(Finding.external_control_id, Finding.state)
    if tenant_id:
        stmt = stmt.where(Finding.tenant_id == tenant_id)
    states = {row[0]: row[1] for row in (await db.execute(stmt)).all()}
    buckets = _pillar_buckets(states)

    pillars: list[PillarScore] = []
    for pillar in PILLARS:
        b = buckets[pillar.id]
        applicable = b["implemented"] + b["partial"] + b["not_implemented"]
        total = applicable + b["not_applicable"]
        coverage = round((b["implemented"] + b["partial"] * 0.5) / applicable * 100, 2) if applicable else 0.0
        status = "uncovered" if applicable == 0 else ("gap" if coverage < 60 else "covered")
        pillars.append(
            PillarScore(
                id=pillar.id,
                name=pillar.name,
                description=pillar.description,
                controls_total=total,
                implemented=b["implemented"],
                partial=b["partial"],
                not_implemented=b["not_implemented"],
                not_applicable=b["not_applicable"],
                coverage_pct=coverage,
                status=status,
            )
        )

    covered = [p for p in pillars if p.status != "uncovered"]
    overall = round(sum(p.coverage_pct for p in covered) / len(covered), 2) if covered else 0.0
    return ZeroTrustResponse(pillars=pillars, overall_coverage_pct=overall, generated_at=datetime.now(UTC))


@router.get("/clouds", response_model=CloudAggregateResponse)
async def dashboard_clouds(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> CloudAggregateResponse:
    """Aggregate multi-cloud dashboard: one row per provider plus totals."""
    from unimonitor.grc.providers import PROVIDERS
    from unimonitor.onboarding.service import connected_providers

    findings = await _load_findings(db, tenant_id)
    groups = _group_by_provider(findings)
    connected = await connected_providers(db, tenant_id)

    providers = [_summarise_provider(p, groups.get(pid, []), _provider_controls(pid), connected=pid in connected) for pid, p in PROVIDERS.items()]

    controls_total = sum(p.controls_total for p in providers)
    controls_passed = sum(p.controls_passed for p in providers)
    applicable = sum(p.controls_total - p.state_counts.not_applicable for p in providers)
    _, _, sec, comp, risk = _count_states(findings)

    return CloudAggregateResponse(
        providers=providers,
        totals=CloudTotals(
            providers_total=len(providers),
            providers_connected=sum(1 for p in providers if p.connected),
            controls_total=controls_total,
            controls_passed=controls_passed,
            coverage_pct=round((controls_passed / applicable) * 100, 2) if applicable else 0.0,
            findings_total=len(findings),
            critical=sum(p.finding_counts.critical for p in providers),
            high=sum(p.finding_counts.high for p in providers),
        ),
        overall_scores=ScoreSummary(
            security_score=sec,
            compliance_score=comp,
            risk_score=risk,
            score_trend_7d=0.0,
        ),
        generated_at=datetime.now(UTC),
    )


@router.get("/clouds/{provider_id}", response_model=CloudProviderDetailResponse)
async def dashboard_cloud_provider(
    provider_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> CloudProviderDetailResponse:
    """Single-cloud dashboard: scores, control coverage and findings for one provider."""
    from fastapi import HTTPException

    from unimonitor.grc.providers import get_provider, provider_for_service

    provider = get_provider(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Unknown cloud provider '{provider_id}'")

    from unimonitor.onboarding.service import connected_providers

    connected = provider.id in await connected_providers(db, tenant_id)
    findings = []
    if connected:
        for finding in await _load_findings(db, tenant_id):
            owner = provider_for_service(finding.service)
            if owner is not None and owner.id == provider.id:
                findings.append(finding)
    controls = _provider_controls(provider.id)
    summary = _summarise_provider(provider, findings, controls, connected=connected)

    states = {f.external_control_id: f.state for f in findings}
    services = [
        ProviderServiceBreakdown(
            service=service,
            controls_total=sum(1 for c in controls if c.service == service),
            controls_passed=sum(1 for c in controls if c.service == service and states.get(c.id) == "implemented"),
            findings=sum(1 for f in findings if f.service == service),
        )
        for service in provider.services
    ]

    categories: dict[str, list] = {}
    for ctrl in controls:
        categories.setdefault(ctrl.category or "general", []).append(ctrl)
    category_rows = []
    for name, group in sorted(categories.items()):
        applicable = [c for c in group if states.get(c.id) != "not_applicable"]
        passed = sum(1 for c in applicable if states.get(c.id) == "implemented")
        category_rows.append(
            ProviderControlCategory(
                category=name,
                controls_total=len(group),
                controls_passed=passed,
                coverage_pct=round((passed / len(applicable)) * 100, 2) if applicable else 0.0,
            )
        )

    top = sorted(
        (f for f in findings if f.state not in ("implemented", "not_applicable") and not f.is_suppressed),
        key=lambda f: f.risk_score,
        reverse=True,
    )[:10]

    return CloudProviderDetailResponse(
        provider=summary,
        services=services,
        categories=category_rows,
        frameworks=_provider_frameworks(controls, findings),
        top_findings=[
            TopFinding(
                id=f.id,
                title=f.title,
                severity=f.severity,
                category=f.category,
                service=f.service,
                first_detected_at=f.first_detected_at,
            )
            for f in top
        ],
        generated_at=datetime.now(UTC),
    )


# ── CISO dashboard ───────────────────────────────────────────
#
# One board for the security leader: residual risk, cloud-by-cloud exposure,
# the risks worth acting on this week, and the frameworks drifting furthest
# from target. Aggregates every provider rather than a single cloud.


class CloudRiskRow(BaseModel):
    provider_id: str
    name: str
    short_name: str
    colour: str
    connected: bool
    security_score: float
    coverage_pct: float
    critical: int
    high: int
    findings_total: int


class CisoRiskItem(BaseModel):
    id: str
    title: str
    severity: str
    state: str
    provider_id: str
    provider_name: str
    colour: str
    service: str
    risk_score: int
    first_detected_at: datetime


class CisoDashboardResponse(BaseModel):
    scores: ScoreSummary
    severity_totals: FindingCounts
    state_totals: StateCounts
    open_findings: int
    suppressed_findings: int
    clouds: list[CloudRiskRow]
    top_risks: list[CisoRiskItem]
    weakest_frameworks: list[FrameworkCoverage]
    coverage_trend: list[TrendPoint]
    generated_at: datetime


@router.get("/ciso", response_model=CisoDashboardResponse)
async def dashboard_ciso(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
    risk_limit: int = Query(default=10, ge=1, le=50),
) -> CisoDashboardResponse:
    """CISO view: residual risk across every monitored cloud."""
    from unimonitor.grc.providers import PROVIDERS, provider_for_service
    from unimonitor.grc.scoring import compute_framework_coverage
    from unimonitor.onboarding.service import connected_providers

    findings = await _load_findings(db, tenant_id)
    groups = _group_by_provider(findings)
    connected = await connected_providers(db, tenant_id)
    # Findings from a cloud that is not connected are noise from an earlier install.
    findings = [f for f in findings if getattr(provider_for_service(f.service), "id", None) in connected]

    clouds = []
    for pid, provider in PROVIDERS.items():
        summary = _summarise_provider(provider, groups.get(pid, []), _provider_controls(pid), connected=pid in connected)
        clouds.append(
            CloudRiskRow(
                provider_id=pid,
                name=provider.name,
                short_name=provider.short_name,
                colour=provider.colour,
                connected=summary.connected,
                security_score=summary.scores.security_score,
                coverage_pct=summary.coverage_pct,
                critical=summary.finding_counts.critical,
                high=summary.finding_counts.high,
                findings_total=summary.finding_counts.total,
            )
        )

    risks = []
    for finding in findings:
        if finding.state in ("implemented", "not_applicable") or finding.is_suppressed:
            continue
        provider = provider_for_service(finding.service)
        risks.append(
            CisoRiskItem(
                id=finding.id,
                title=finding.title,
                severity=finding.severity,
                state=finding.state,
                provider_id=provider.id if provider else "other",
                provider_name=provider.name if provider else "Unassigned",
                colour=provider.colour if provider else "#94A3B8",
                service=finding.service,
                risk_score=finding.risk_score,
                first_detected_at=finding.first_detected_at,
            )
        )
    risks.sort(key=lambda r: r.risk_score, reverse=True)

    _, state_totals, sec, comp, risk = _count_states(findings)
    # Board-level severity must count *open* risk only; implemented controls and
    # not-applicable findings are not exposure.
    severity_totals = FindingCounts(
        critical=sum(1 for r in risks if r.severity == "critical"),
        high=sum(1 for r in risks if r.severity == "high"),
        medium=sum(1 for r in risks if r.severity == "medium"),
        low=sum(1 for r in risks if r.severity == "low"),
        informational=sum(1 for r in risks if r.severity == "informational"),
        total=len(risks),
    )

    try:
        coverages = await compute_framework_coverage(db, tenant_id=tenant_id)
    except Exception:  # noqa: BLE001 - coverage must never break the CISO board
        coverages = {}

    # Framework ids are slugged (iso27001-2022); show the display name instead.
    from unimonitor.api.v1.controls import SUPPORTED_FRAMEWORKS

    framework_names = {fw["id"]: fw["name"] for fw in SUPPORTED_FRAMEWORKS}
    framework_gaps = [
        FrameworkCoverage(
            framework_id=fw_id,
            framework_name=framework_names.get(fw_id, fw_id.replace("-", " ").title()),
            coverage_pct=cov.get("coverage_pct", 0.0),
            controls_total=cov.get("controls_total", 0),
            controls_passed=cov.get("controls_passed", 0),
        )
        for fw_id, cov in coverages.items()
        if cov.get("controls_total")
    ]
    framework_gaps.sort(key=lambda fw: fw.coverage_pct)

    from unimonitor.db.repositories.assessment_repo import AssessmentRepository

    trend_points = await AssessmentRepository(db).get_score_trends(tenant_id=tenant_id, days=30)

    return CisoDashboardResponse(
        scores=ScoreSummary(
            security_score=sec,
            compliance_score=comp,
            risk_score=risk,
            score_trend_7d=0.0,
        ),
        severity_totals=severity_totals,
        state_totals=state_totals,
        open_findings=len(risks),
        suppressed_findings=sum(1 for f in findings if f.is_suppressed),
        clouds=clouds,
        top_risks=risks[:risk_limit],
        weakest_frameworks=framework_gaps[:5],
        coverage_trend=[
            TrendPoint(
                date=p.get("date", ""),
                security_score=p.get("security_score", 0.0),
                compliance_score=p.get("compliance_score", 0.0),
                risk_score=p.get("risk_score", 0.0),
            )
            for p in trend_points
        ],
        generated_at=datetime.now(UTC),
    )
