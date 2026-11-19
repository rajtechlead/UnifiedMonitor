"""Zero Trust assessment API — imported PowerShell results and cloud checks."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.auth.dependencies import get_current_user, require_role
from unimonitor.core.audit import write_audit
from unimonitor.db.session import get_db
from unimonitor.zerotrust import service
from unimonitor.zerotrust.normalise import PLATFORMS

logger = structlog.get_logger(__name__)
router = APIRouter()

SourceLiteral = Literal["microsoft", "aws", "gcp", "google_workspace"]
SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "zerotrust" / "Invoke-UniMonitorZeroTrust.ps1"


class CheckResponse(BaseModel):
    check_id: str
    title: str
    pillar: str
    severity: str
    status: str
    category: str | None
    remediation: list[str] = []
    reference: str | None

    model_config = {"from_attributes": True}


class RunResponse(BaseModel):
    id: str
    source: str
    platform: str
    score: float
    total: int
    passed: int
    failed: int
    warned: int
    not_run: int
    origin: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PlatformSummary(BaseModel):
    source: str
    platform: str
    has_run: bool
    score: float
    total: int
    passed: int
    failed: int
    warned: int
    not_run: int
    last_run: datetime | None
    pillars: list[dict[str, Any]] = []


class SummaryResponse(BaseModel):
    platforms: list[PlatformSummary]
    overall_score: float
    generated_at: datetime


class ImportRequest(BaseModel):
    source: SourceLiteral = "microsoft"
    tenant_id: str | None = None
    # Either raw export (any shape Microsoft writes) or already-normalised checks.
    payload: Any | None = None
    checks: list[dict[str, Any]] | None = None


class ImportResponse(BaseModel):
    run: RunResponse
    checks: list[CheckResponse]


class RunRequest(BaseModel):
    # The Python engine is the default path for every platform, Microsoft included.
    platform: SourceLiteral
    tenant_id: str | None = None


class RunAllResponse(BaseModel):
    runs: list[RunResponse]
    skipped: list[str] = []


async def _resolve_tenant(db: AsyncSession, tenant_id: str | None) -> str:
    """Use the requested tenant, or the only active one for single-tenant installs."""
    if tenant_id:
        return tenant_id
    from sqlalchemy import select

    from unimonitor.db.models.tenant import Tenant

    row = (await db.execute(select(Tenant.id).where(Tenant.is_active.is_(True)).order_by(Tenant.created_at).limit(1))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=400, detail="No active tenant. Complete setup or pass tenant_id.")
    return row


def _run_response(run: Any) -> RunResponse:
    return RunResponse(
        id=run.id,
        source=run.source,
        platform=PLATFORMS.get(run.source, run.source),
        score=run.score,
        total=run.total,
        passed=run.passed,
        failed=run.failed,
        warned=run.warned,
        not_run=run.not_run,
        origin=run.origin,
        created_at=run.created_at,
    )


def _check_response(check: Any) -> CheckResponse:
    steps: list[str] = []
    if getattr(check, "remediation", None):
        try:
            parsed = json.loads(check.remediation)
            steps = [str(step) for step in parsed] if isinstance(parsed, list) else [str(parsed)]
        except (TypeError, ValueError):
            steps = [str(check.remediation)]
    return CheckResponse(
        check_id=check.check_id,
        title=check.title,
        pillar=check.pillar,
        severity=check.severity,
        status=check.status,
        category=check.category,
        remediation=steps,
        reference=check.reference,
    )


@router.get("/summary", response_model=SummaryResponse)
async def zerotrust_summary(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> SummaryResponse:
    """Latest score for every platform, so the page can compare them side by side."""
    tenant = await _resolve_tenant(db, tenant_id)
    latest = await service.latest_by_source(db, tenant)
    platforms: list[PlatformSummary] = []
    for source, label in PLATFORMS.items():
        run = latest.get(source)
        if run is None:
            platforms.append(
                PlatformSummary(
                    source=source,
                    platform=label,
                    has_run=False,
                    score=0.0,
                    total=0,
                    passed=0,
                    failed=0,
                    warned=0,
                    not_run=0,
                    last_run=None,
                )
            )
            continue
        try:
            pillars = json.loads(run.pillars) if run.pillars else []
        except ValueError:
            pillars = []
        platforms.append(
            PlatformSummary(
                source=source,
                platform=label,
                has_run=True,
                score=run.score,
                total=run.total,
                passed=run.passed,
                failed=run.failed,
                warned=run.warned,
                not_run=run.not_run,
                last_run=run.created_at,
                pillars=pillars,
            )
        )

    scored = [p.score for p in platforms if p.has_run]
    return SummaryResponse(
        platforms=platforms,
        overall_score=round(sum(scored) / len(scored), 2) if scored else 0.0,
        generated_at=datetime.now().astimezone(),
    )


@router.get("/checks", response_model=list[CheckResponse])
async def zerotrust_checks(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
    source: SourceLiteral = Query(default="microsoft"),
    pillar: str | None = Query(default=None),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    q: str | None = Query(default=None),
) -> list[CheckResponse]:
    """Checks from the latest run of a platform, filtered for the page's table."""
    tenant = await _resolve_tenant(db, tenant_id)
    latest = await service.latest_by_source(db, tenant)
    run = latest.get(source)
    if run is None:
        return []

    checks = await service.run_checks(db, run.id)
    rows = [_check_response(check) for check in checks]
    if pillar:
        rows = [row for row in rows if row.pillar == pillar]
    if status:
        rows = [row for row in rows if row.status == status]
    if severity:
        rows = [row for row in rows if row.severity == severity]
    if q:
        needle = q.lower()
        rows = [row for row in rows if needle in row.title.lower() or needle in row.check_id.lower()]
    return rows


@router.get("/runs", response_model=list[RunResponse])
async def zerotrust_runs(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> list[RunResponse]:
    tenant = await _resolve_tenant(db, tenant_id)
    return [_run_response(run) for run in await service.list_runs(db, tenant)]


@router.post("/import", response_model=ImportResponse)
async def zerotrust_import(
    body: ImportRequest,
    current_user: Annotated[Any, Depends(require_role("admin", "analyst"))],
    db: AsyncSession = Depends(get_db),
) -> ImportResponse:
    """Import the JSON a Zero Trust Assessment run produced.

    The payload may be the export file's parsed JSON or an already-normalised
    ``checks`` list; both are accepted because the export shape varies by release.
    """
    payload = body.checks if body.checks is not None else body.payload
    if payload is None:
        raise HTTPException(status_code=400, detail="Send either 'payload' (the exported JSON) or 'checks'.")

    checks = service.import_export(payload)
    if not checks:
        raise HTTPException(
            status_code=422,
            detail="No checks found in that payload. Expected a list, or an object with a tests/results/checks array.",
        )

    tenant = await _resolve_tenant(db, body.tenant_id)
    run, summary = await service.store_run(
        db,
        tenant_id=tenant,
        source=body.source,
        checks=checks,
        origin="import",
        user_id=getattr(current_user, "id", None),
    )
    await write_audit(
        db,
        action="zerotrust.import",
        tenant_id=tenant,
        user_id=getattr(current_user, "id", None),
        resource_type="zerotrust_run",
        resource_id=run.id,
        payload={"source": body.source, "checks": summary["total"], "score": summary["score"]},
    )
    stored = await service.run_checks(db, run.id)
    response = ImportResponse(run=_run_response(run), checks=[_check_response(check) for check in stored])
    return response


@router.post("/run", response_model=ImportResponse)
async def zerotrust_run_platform(
    body: RunRequest,
    current_user: Annotated[Any, Depends(require_role("admin", "analyst"))],
    db: AsyncSession = Depends(get_db),
) -> ImportResponse:
    """Evaluate a platform's checks from the latest collected evidence."""
    tenant = await _resolve_tenant(db, body.tenant_id)
    checks = await service.cloud_checks(db, tenant, body.platform)
    if not checks:
        raise HTTPException(
            status_code=404,
            detail=f"No {PLATFORMS[body.platform]} controls are defined, so there is nothing to evaluate.",
        )

    run, summary = await service.store_run(
        db,
        tenant_id=tenant,
        source=body.platform,
        checks=checks,
        origin="collector",
        user_id=getattr(current_user, "id", None),
    )
    await write_audit(
        db,
        action="zerotrust.evaluate",
        tenant_id=tenant,
        user_id=getattr(current_user, "id", None),
        resource_type="zerotrust_run",
        resource_id=run.id,
        payload={"source": body.platform, "checks": summary["total"], "score": summary["score"]},
    )
    stored = await service.run_checks(db, run.id)
    response = ImportResponse(run=_run_response(run), checks=[_check_response(check) for check in stored])
    return response


@router.post("/run-all", response_model=RunAllResponse)
async def zerotrust_run_all(
    current_user: Annotated[Any, Depends(require_role("admin", "analyst"))],
    db: AsyncSession = Depends(get_db),
    tenant_id: str | None = Query(default=None),
) -> RunAllResponse:
    """Evaluate every platform with the Python engine in one pass.

    A platform with no defined controls (or no connection) is skipped rather than
    failing the whole run.
    """
    tenant = await _resolve_tenant(db, tenant_id)
    runs: list[RunResponse] = []
    skipped: list[str] = []
    for source in PLATFORMS:
        checks = await service.cloud_checks(db, tenant, source)
        if not checks:
            skipped.append(source)
            continue
        run, summary = await service.store_run(
            db,
            tenant_id=tenant,
            source=source,
            checks=checks,
            origin="collector",
            user_id=getattr(current_user, "id", None),
        )
        await write_audit(
            db,
            action="zerotrust.evaluate",
            tenant_id=tenant,
            user_id=getattr(current_user, "id", None),
            resource_type="zerotrust_run",
            resource_id=run.id,
            payload={"source": source, "checks": summary["total"], "score": summary["score"]},
        )
        runs.append(_run_response(run))
    return RunAllResponse(runs=runs, skipped=skipped)


@router.get("/script", response_class=PlainTextResponse)
async def zerotrust_script(current_user: Annotated[Any, Depends(get_current_user)]) -> PlainTextResponse:
    """The PowerShell runner, so the page can offer it for download."""
    if not SCRIPT_PATH.exists():
        raise HTTPException(status_code=404, detail="The PowerShell runner is not bundled with this build.")
    return PlainTextResponse(SCRIPT_PATH.read_text(encoding="utf-8"), media_type="text/plain")
