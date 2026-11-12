"""Dashboard data APIs — all views."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


class ExecutiveSummaryResponse(BaseModel):
    scores: ScoreSummary
    score_trends: list[TrendPoint]
    top_risks: list[TopFinding]
    framework_coverage: list[FrameworkCoverage]
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
            timestamp=a.get("timestamp", datetime.now(timezone.utc)),
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
        generated_at=datetime.now(timezone.utc),
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
        asset_coverage_pct=0.0,
        remediation_progress_pct=0.0,
        generated_at=datetime.now(timezone.utc),
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
        generated_at=datetime.now(timezone.utc),
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
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/risk", response_model=RiskViewResponse)
async def dashboard_risk(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> RiskViewResponse:
    """Risk dashboard — heatmap and critical risks."""
    _, _, risk = await _get_scores_for_tenant(db, tenant_id)
    top_findings = await _get_top_findings_list(db, tenant_id, limit=10)

    from unimonitor.db.repositories.finding_repo import FindingRepository

    repo = FindingRepository(db)
    heatmap_data = await repo.get_risk_heatmap(tenant_id=tenant_id)

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
        critical_risks=[f for f in top_findings if f.severity == "critical"],
        generated_at=datetime.now(timezone.utc),
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
        generated_at=datetime.now(timezone.utc),
    )


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
        generated_at=datetime.now(timezone.utc),
    )
