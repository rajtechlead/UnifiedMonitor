"""GRC framework endpoints — crosswalk, gap analysis, evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.api.v1.controls import SUPPORTED_FRAMEWORKS
from unimonitor.api.v1.lookups import evidence_by_finding, latest_findings_by_control
from unimonitor.auth.dependencies import get_current_user, require_role
from unimonitor.auth.tenant_scope import tenant_scope
from unimonitor.db.session import get_db

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


@router.get("/frameworks")
async def list_frameworks_with_coverage(
    current_user: Annotated[Any, Depends(get_current_user)],
    tenant_id: Annotated[str | None, Depends(tenant_scope)] = None,
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


@router.get("/frameworks/{framework_id}/coverage", responses={404: {"description": "Not found"}})
async def framework_coverage(
    framework_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
    tenant_id: Annotated[str | None, Depends(tenant_scope)] = None,
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


@router.get("/frameworks/{framework_id}/controls", responses={404: {"description": "Not found"}})
async def framework_controls(
    framework_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
    tenant_id: Annotated[str | None, Depends(tenant_scope)] = None,
) -> list[dict]:
    """Get all controls for a framework with current finding state."""
    fw_info = next((f for f in SUPPORTED_FRAMEWORKS if f["id"] == framework_id), None)
    if not fw_info:
        raise HTTPException(status_code=404, detail=f"Framework '{framework_id}' not found")

    from unimonitor.db.base import async_session_factory
    from unimonitor.grc.control_loader import controls_for_framework

    # Canonical aliases: every control mapped to the framework, none dropped by a
    # dash/underscore or legacy-key mismatch.
    controls = controls_for_framework(framework_id)

    result = []
    async with async_session_factory() as session:
        findings = await latest_findings_by_control(session, [c.id for c in controls], tenant_id)
        evidence = await evidence_by_finding(session, [f.id for f in findings.values()])

        for control in controls:
            finding = findings.get(control.id)
            result.append(
                {
                    "control_id": control.id,
                    "external_id": control.id,
                    "name": control.title,
                    "category": control.category,
                    "severity": control.severity.lower(),
                    "state": finding.state if finding else "not_run",
                    "last_seen": finding.last_seen_at.isoformat() if finding else None,
                    "finding_id": finding.id if finding else None,
                    "remediation": "\n".join(control.remediation_steps) or control.remediation_summary,
                    "evidence": [
                        {
                            "type": item.evidence_type,
                            "source": item.source,
                            "content": (item.content or "")[:800],
                            "collected_at": item.collected_at.isoformat(),
                        }
                        for item in evidence.get(finding.id, [])[:3]
                    ]
                    if finding
                    else [],
                }
            )

    return result


@router.get(
    "/controls/trend",
    responses={401: {"description": "Not authenticated"}},
)
async def controls_trend(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[str | None, Depends(tenant_scope)] = None,
    days: Annotated[int, Query(ge=1, le=365, description="Window in days")] = 30,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    only_changed: Annotated[bool, Query(description="Only controls whose state changed")] = False,
) -> dict[str, Any]:
    """Control-level state series from the snapshots written by each run."""
    from unimonitor.grc.control_trends import control_trends

    return await control_trends(db, tenant_id, days=days, limit=limit, only_changed=only_changed)


@router.get(
    "/controls/{control_id}/trend",
    responses={401: {"description": "Not authenticated"}, 404: {"description": "No snapshots exist for this control in the window"}},
)
async def single_control_trend(
    control_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[str | None, Depends(tenant_scope)] = None,
    days: Annotated[int, Query(ge=1, le=365)] = 90,
) -> dict[str, Any]:
    """State series for one control."""
    from unimonitor.grc.control_trends import control_trend

    result = await control_trend(db, tenant_id, control_id, days=days)
    if not result["points"]:
        raise HTTPException(status_code=404, detail=f"No snapshots for control '{control_id}' in the last {days} days")
    return result


@router.get("/crosswalk", responses={404: {"description": "Not found"}})
async def control_crosswalk(
    current_user: Annotated[Any, Depends(get_current_user)],
    control_id: Annotated[str, Query(..., description="External control ID to crosswalk")],
) -> list[CrosswalkEntry]:
    """Show how a control maps across all supported frameworks."""
    from unimonitor.api.v1.controls import SUPPORTED_FRAMEWORKS
    from unimonitor.grc.control_loader import ControlLoader
    from unimonitor.grc.frameworks import framework_id_for_key

    control = next((item for item in ControlLoader().load_all() if item.id == control_id), None)
    if control is None:
        raise HTTPException(status_code=404, detail=f"Control '{control_id}' not found")

    names = {fw["id"]: fw["name"] for fw in SUPPORTED_FRAMEWORKS}
    entries: list[CrosswalkEntry] = []
    for framework_key, references in control.compliance_mapping.items():
        if framework_key == "zero_trust":
            continue
        framework_id = framework_id_for_key(framework_key) or framework_key.replace("_", "-")
        refs = references if isinstance(references, (list, tuple)) else [references]
        for reference in refs:
            entries.append(
                CrosswalkEntry(
                    control_id=control.id,
                    control_name=control.title,
                    framework_id=framework_id,
                    framework_name=names.get(framework_id, framework_id.replace("-", " ").title()),
                    framework_control_id=str(reference),
                    framework_control_name=control.title,
                )
            )
    return entries


@router.get("/gap-analysis")
async def gap_analysis(
    current_user: Annotated[Any, Depends(get_current_user)],
    tenant_id: Annotated[str | None, Depends(tenant_scope)] = None,
    framework_id: Annotated[str | None, Query()] = None,
    min_severity: Annotated[str, Query()] = "medium",
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


@router.get("/risk-scoring")
async def risk_scoring(
    current_user: Annotated[Any, Depends(get_current_user)],
    tenant_id: Annotated[str | None, Depends(tenant_scope)] = None,
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


@router.post("/evidence/{finding_id}", status_code=status.HTTP_201_CREATED, responses={404: {"description": "Not found"}})
async def upload_evidence(
    finding_id: str,
    file: Annotated[UploadFile, File(...)],
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


@router.get("/evidence/{finding_id}", responses={404: {"description": "Not found"}})
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
