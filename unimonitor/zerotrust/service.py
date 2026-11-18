"""Zero Trust assessment storage and cloud check evaluation."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.db.models.finding import Finding, FindingState
from unimonitor.db.models.zerotrust import ZeroTrustCheck, ZeroTrustRun
from unimonitor.grc.control_loader import ControlLoader
from unimonitor.grc.pillars import pillar_for
from unimonitor.zerotrust.normalise import PLATFORMS, normalise_checks, summarise

_STATUS_TO_RESULT = {
    FindingState.IMPLEMENTED.value: "pass",
    FindingState.PARTIALLY_IMPLEMENTED.value: "warn",
    FindingState.NOT_IMPLEMENTED.value: "fail",
    FindingState.NOT_APPLICABLE.value: "not_applicable",
}


def _platform_name(source: str) -> str:
    return PLATFORMS.get(source, source)


def _control_pillar(compliance_mapping: dict[str, Any]) -> str | None:
    for mapping in compliance_mapping.get("zero_trust", []) or []:
        pillar = pillar_for(str(mapping))
        if pillar:
            return pillar
    return None


async def store_run(
    db: AsyncSession,
    *,
    tenant_id: str,
    source: str,
    checks: list[dict[str, Any]],
    origin: str = "import",
    user_id: str | None = None,
) -> tuple[ZeroTrustRun, dict[str, Any]]:
    """Persist one run and its checks. The caller commits."""
    summary = summarise(checks)
    run = ZeroTrustRun(
        tenant_id=tenant_id,
        source=source,
        status="completed",
        score=summary["score"],
        total=summary["total"],
        passed=summary["passed"],
        failed=summary["failed"],
        warned=summary["warned"],
        not_run=summary["not_run"],
        pillars=json.dumps(summary["pillars"]),
        origin=origin,
        imported_by=user_id,
    )
    db.add(run)
    await db.flush()

    for check in checks:
        db.add(
            ZeroTrustCheck(
                run_id=run.id,
                check_id=str(check["check_id"])[:64],
                title=str(check["title"])[:512],
                pillar=str(check.get("pillar") or "identity"),
                severity=str(check.get("severity") or "medium"),
                status=str(check.get("status") or "not_run"),
                category=(check.get("category") or None),
                remediation=json.dumps(check.get("remediation") or []),
                reference=(check.get("reference") or None),
            )
        )
    await db.flush()
    return run, summary


async def cloud_checks(db: AsyncSession, tenant_id: str, platform: str) -> list[dict[str, Any]]:
    """Evaluate the platform's controls against the tenant's latest findings.

    The remediation text comes from the control YAML, so these checks carry the
    same "what to do next" as the Microsoft assessment.
    """
    rows = (await db.execute(select(Finding.external_control_id, Finding.state).where(Finding.tenant_id == tenant_id))).all()
    states: dict[str, str] = {}
    for control_id, state in rows:
        # Later rows overwrite; findings are one row per control, so this is the current state.
        states[control_id] = state

    checks: list[dict[str, Any]] = []
    for control in ControlLoader().load_all():
        if control.service != platform:
            continue
        current_state: str | None = states.get(control.id)
        status = _STATUS_TO_RESULT.get(current_state or "", "not_run")
        pillar = _control_pillar(control.compliance_mapping) or "infrastructure"
        checks.append(
            {
                "check_id": control.id,
                "title": control.title,
                "pillar": pillar,
                "severity": control.severity.lower(),
                "status": status,
                "category": control.service,
                "remediation": control.remediation_steps or ([control.remediation_summary] if control.remediation_summary else []),
                "reference": "",
            }
        )
    return checks


async def list_runs(db: AsyncSession, tenant_id: str, limit: int = 50) -> list[ZeroTrustRun]:
    return list(
        (await db.execute(select(ZeroTrustRun).where(ZeroTrustRun.tenant_id == tenant_id).order_by(desc(ZeroTrustRun.created_at)).limit(limit)))
        .scalars()
        .all()
    )


async def latest_by_source(db: AsyncSession, tenant_id: str) -> dict[str, ZeroTrustRun]:
    latest: dict[str, ZeroTrustRun] = {}
    for run in await list_runs(db, tenant_id):
        latest.setdefault(run.source, run)
    return latest


async def run_checks(db: AsyncSession, run_id: str) -> list[ZeroTrustCheck]:
    return list((await db.execute(select(ZeroTrustCheck).where(ZeroTrustCheck.run_id == run_id).order_by(ZeroTrustCheck.check_id))).scalars().all())


def import_export(payload: Any) -> list[dict[str, Any]]:
    """Normalise an uploaded export; kept here so the API stays thin."""
    return normalise_checks(payload)


def platform_label(source: str) -> str:
    return _platform_name(source)
