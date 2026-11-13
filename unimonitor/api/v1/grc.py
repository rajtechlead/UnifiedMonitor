"""GRC framework endpoints — crosswalk, gap analysis, evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from unimonitor.api.v1.controls import SUPPORTED_FRAMEWORKS
from unimonitor.auth.dependencies import get_current_user, require_role

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────


class FrameworkCoverage(BaseModel):
    framework_id: str
    framework_name: str
    coverage_pct: float
    controls_total: int
    controls_implemented: int
    controls_partial: int
    controls_not_implemented: int
    controls_not_applicable: int


class CrosswalkEntry(BaseModel):
    control_id: str
    control_name: str
    framework_id: str
    framework_name: str
    framework_control_id: str
    framework_control_name: str


class GapItem(BaseModel):
    finding_id: str
    external_control_id: str
    title: str
    severity: str
    category: str
    state: str
    frameworks_affected: list[str]


class GapAnalysisResponse(BaseModel):
    tenant_id: str | None
    total_gaps: int
    critical_gaps: int
    high_gaps: int
    gaps_by_category: dict[str, list[GapItem]]
    generated_at: datetime


class RiskBreakdown(BaseModel):
    category: str
    risk_score: float
    finding_count: int
    critical_count: int
    high_count: int


class RiskScoringResponse(BaseModel):
    overall_risk_score: float
    tenant_id: str | None
    breakdown: list[RiskBreakdown]
    methodology: str
    generated_at: datetime


class EvidenceResponse(BaseModel):
    id: str
    finding_id: str
    evidence_type: str
    source: str
    content: str
    collected_at: datetime

    model_config = {"from_attributes": True}


class EvidenceUploadResponse(BaseModel):
    id: str
    finding_id: str
    evidence_type: str
    filename: str
    size_bytes: int
    collected_at: datetime


# ── Endpoints ────────────────────────────────────────────────


@router.get("/frameworks", response_model=list[FrameworkCoverage])
async def list_frameworks_with_coverage(
    current_user: Annotated[Any, Depends(get_current_user)],
    tenant_id: str | None = Query(default=None),
) -> list[FrameworkCoverage]:
    """List all supported frameworks with current compliance coverage."""
    from unimonitor.db.base import async_session_factory
    from unimonitor.grc.scoring import compute_framework_coverage

    async with async_session_factory() as session:
        coverages = await compute_framework_coverage(session, tenant_id=tenant_id)

    result = []
    for fw in SUPPORTED_FRAMEWORKS:
        cov = coverages.get(fw["id"], {})
        result.append(
            FrameworkCoverage(
                framework_id=fw["id"],
                framework_name=fw["name"],
                coverage_pct=cov.get("coverage_pct", 0.0),
                controls_total=cov.get("controls_total", 0),
                controls_implemented=cov.get("controls_implemented", 0),
                controls_partial=cov.get("controls_partial", 0),
                controls_not_implemented=cov.get("controls_not_implemented", 0),
                controls_not_applicable=cov.get("controls_not_applicable", 0),
            )
        )
    return result


@router.get("/frameworks/{framework_id}/coverage", response_model=FrameworkCoverage)
async def framework_coverage(
    framework_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
    tenant_id: str | None = Query(default=None),
) -> FrameworkCoverage:
    """Get detailed compliance coverage for a specific framework."""
    fw_info = next((f for f in SUPPORTED_FRAMEWORKS if f["id"] == framework_id), None)
    if not fw_info:
        raise HTTPException(status_code=404, detail=f"Framework '{framework_id}' not found")

    from unimonitor.db.base import async_session_factory
    from unimonitor.grc.scoring import compute_framework_coverage

    async with async_session_factory() as session:
        coverages = await compute_framework_coverage(session, tenant_id=tenant_id, framework_id=framework_id)

    cov = coverages.get(framework_id, {})
    return FrameworkCoverage(
        framework_id=fw_info["id"],
        framework_name=fw_info["name"],
        coverage_pct=cov.get("coverage_pct", 0.0),
        controls_total=cov.get("controls_total", 0),
        controls_implemented=cov.get("controls_implemented", 0),
        controls_partial=cov.get("controls_partial", 0),
        controls_not_implemented=cov.get("controls_not_implemented", 0),
        controls_not_applicable=cov.get("controls_not_applicable", 0),
    )


@router.get("/frameworks/{framework_id}/controls")
async def framework_controls(
    framework_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
    tenant_id: str | None = Query(default=None),
) -> list[dict]:
    """Get all controls for a framework with current finding state."""
    fw_info = next((f for f in SUPPORTED_FRAMEWORKS if f["id"] == framework_id), None)
    if not fw_info:
        raise HTTPException(status_code=404, detail=f"Framework '{framework_id}' not found")

    from unimonitor.db.base import async_session_factory
    from unimonitor.db.repositories.finding_repo import FindingRepository
    from unimonitor.grc.control_loader import ControlLibrary

    async with async_session_factory() as session:
        library = ControlLibrary(session)
        repo = FindingRepository(session)
        controls = await library.get_controls_for_framework(framework_id)

        result = []
        for control in controls:
            # Get latest finding state for this control
            finding = await repo.get_latest_by_control(
                external_control_id=control.external_id,
                tenant_id=tenant_id,
            )
            result.append(
                {
                    "control_id": control.id,
                    "external_id": control.external_id,
                    "name": control.name,
                    "category": control.category,
                    "severity": control.severity,
                    "state": finding.state if finding else "not_implemented",
                    "last_seen": finding.last_seen_at.isoformat() if finding else None,
                }
            )

    return result


@router.get("/crosswalk")
async def control_crosswalk(
    current_user: Annotated[Any, Depends(get_current_user)],
    control_id: str = Query(..., description="External control ID to crosswalk"),
) -> list[CrosswalkEntry]:
    """Show how a control maps across all supported frameworks."""
    from unimonitor.db.base import async_session_factory
    from unimonitor.grc.control_loader import ControlLibrary

    async with async_session_factory() as session:
        library = ControlLibrary(session)
        control = await library.get_by_external_id(control_id)
        if not control:
            raise HTTPException(status_code=404, detail=f"Control '{control_id}' not found")

        mappings = await library.get_crosswalk_mappings(control.id)

    return [
        CrosswalkEntry(
            control_id=control.id,
            control_name=control.name,
            framework_id=m.get("framework_id", ""),
            framework_name=m.get("framework_name", ""),
            framework_control_id=m.get("framework_control_id", ""),
            framework_control_name=m.get("framework_control_name", ""),
        )
        for m in mappings
    ]


@router.get("/gap-analysis", response_model=GapAnalysisResponse)
async def gap_analysis(
    current_user: Annotated[Any, Depends(get_current_user)],
    tenant_id: str | None = Query(default=None),
    framework_id: str | None = Query(default=None),
    min_severity: str = Query(default="medium"),
) -> GapAnalysisResponse:
    """Gap analysis: controls not yet implemented, grouped by category."""
    from unimonitor.db.base import async_session_factory
    from unimonitor.db.repositories.finding_repo import FindingRepository

    sev_order = {"informational": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    min_sev_level = sev_order.get(min_severity, 2)

    async with async_session_factory() as session:
        repo = FindingRepository(session)
        findings, _ = await repo.list_paginated(
            tenant_id=tenant_id,
            state="not_implemented",
            page=1,
            page_size=1000,
            is_suppressed=False,
        )

    gaps_by_category: dict[str, list[GapItem]] = {}
    critical_gaps = 0
    high_gaps = 0

    for f in findings:
        if sev_order.get(f.severity, 0) < min_sev_level:
            continue

        item = GapItem(
            finding_id=f.id,
            external_control_id=f.external_control_id,
            title=f.title,
            severity=f.severity,
            category=f.category,
            state=f.state,
            frameworks_affected=[],
        )

        cat = f.category or "Uncategorised"
        if cat not in gaps_by_category:
            gaps_by_category[cat] = []
        gaps_by_category[cat].append(item)

        if f.severity == "critical":
            critical_gaps += 1
        elif f.severity == "high":
            high_gaps += 1

    total_gaps = sum(len(v) for v in gaps_by_category.values())

    return GapAnalysisResponse(
        tenant_id=tenant_id,
        total_gaps=total_gaps,
        critical_gaps=critical_gaps,
        high_gaps=high_gaps,
        gaps_by_category=gaps_by_category,
        generated_at=datetime.now(UTC),
    )


@router.get("/risk-scoring", response_model=RiskScoringResponse)
async def risk_scoring(
    current_user: Annotated[Any, Depends(get_current_user)],
    tenant_id: str | None = Query(default=None),
) -> RiskScoringResponse:
    """Overall risk scoring with breakdown by category."""
    from unimonitor.db.base import async_session_factory
    from unimonitor.grc.scoring import compute_risk_score

    async with async_session_factory() as session:
        result = await compute_risk_score(session, tenant_id=tenant_id)

    return RiskScoringResponse(
        overall_risk_score=result.get("overall_score", 0.0),
        tenant_id=tenant_id,
        breakdown=[
            RiskBreakdown(
                category=item.get("category", ""),
                risk_score=item.get("risk_score", 0.0),
                finding_count=item.get("finding_count", 0),
                critical_count=item.get("critical_count", 0),
                high_count=item.get("high_count", 0),
            )
            for item in result.get("breakdown", [])
        ],
        methodology=("Risk score = (Critical×10 + High×8 + Medium×5 + Low×3 + Informational×1) normalised to 0–100. Lower is better."),
        generated_at=datetime.now(UTC),
    )


@router.post("/evidence/{finding_id}", response_model=EvidenceUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    finding_id: str,
    file: UploadFile = File(...),
    current_user: Annotated[Any, Depends(require_role("analyst"))] = None,
) -> EvidenceUploadResponse:
    """Upload evidence file for a finding."""
    import uuid
    from pathlib import Path

    from unimonitor.config import get_settings
    from unimonitor.db.base import async_session_factory
    from unimonitor.db.repositories.finding_repo import FindingRepository

    settings = get_settings()

    async with async_session_factory() as session:
        repo = FindingRepository(session)
        finding = await repo.get_by_id(finding_id)
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")

    # Save file to evidence storage
    evidence_id = str(uuid.uuid4())
    evidence_dir = Path(settings.REPORT_STORAGE_PATH) / "evidence" / finding_id
    evidence_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "evidence.bin").suffix
    dest = evidence_dir / f"{evidence_id}{suffix}"
    content = await file.read()
    dest.write_bytes(content)

    # Save record
    async with async_session_factory() as session:
        repo = FindingRepository(session)
        evidence = await repo.add_evidence(
            finding_id=finding_id,
            evidence_type="file_upload",
            source=file.filename or "upload",
            content=str(dest),
        )

    logger.info("evidence_uploaded", finding_id=finding_id, file=file.filename, by=current_user.id if current_user else None)
    return EvidenceUploadResponse(
        id=evidence.id,
        finding_id=finding_id,
        evidence_type="file_upload",
        filename=file.filename or "evidence",
        size_bytes=len(content),
        collected_at=evidence.collected_at,
    )


@router.get("/evidence/{finding_id}", response_model=list[EvidenceResponse])
async def list_evidence(
    finding_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
) -> list[EvidenceResponse]:
    """List all evidence for a finding."""
    from unimonitor.db.base import async_session_factory
    from unimonitor.db.repositories.finding_repo import FindingRepository

    async with async_session_factory() as session:
        repo = FindingRepository(session)
        finding = await repo.get_by_id(finding_id)
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")
        evidence_list = await repo.list_evidence(finding_id)

    return [EvidenceResponse.model_validate(e) for e in evidence_list]
