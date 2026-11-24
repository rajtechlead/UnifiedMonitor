"""Zero Trust assessment storage and cloud check evaluation."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.db.models.finding import Finding, FindingState
from unimonitor.db.models.zerotrust import ZeroTrustCheck, ZeroTrustRun
from unimonitor.grc.control_loader import ControlLoader
from unimonitor.grc.pillars import pillar_for
from unimonitor.zerotrust.microsoft import TEST_IDS
from unimonitor.zerotrust.microsoft import TESTS as MICROSOFT_TESTS
from unimonitor.zerotrust.normalise import normalise_checks, summarise
from unimonitor.zerotrust.platform_tests import PlatformTest, tests_for

# Imports arrive on a schedule; keep only the newest snapshots so the table and
# the executive score do not accumulate every historical export.
RETAIN_RUNS_PER_PLATFORM = 5

_STATUS_TO_RESULT = {
    FindingState.IMPLEMENTED.value: "pass",
    FindingState.PARTIALLY_IMPLEMENTED.value: "warn",
    FindingState.NOT_IMPLEMENTED.value: "fail",
    FindingState.NOT_APPLICABLE.value: "not_applicable",
}


# A platform is several control services for Microsoft, one for each cloud.
PLATFORM_SERVICES: dict[str, tuple[str, ...]] = {
    "microsoft": (
        "entra_id",
        "azure_security",
        "intune",
        "defender",
        "defender_office",
        "defender_cloud_apps",
        "defender_identity",
        "purview",
        "purview_insider_risk",
        "purview_ediscovery",
        "exchange",
        "sharepoint",
        "teams",
        "copilot_m365",
        "copilot_studio",
    ),
    "aws": ("aws",),
    "gcp": ("gcp",),
    "google_workspace": ("google_workspace",),
}


# Worst-case ordering used when several controls back one upstream test.
_STATUS_PRIORITY = ("fail", "warn", "pass", "not_run", "not_applicable")


def _worst_status(statuses: list[str]) -> str:
    """The weakest result in a group; a single failure fails the test."""
    if not statuses:
        return "not_run"
    return min(statuses, key=lambda status: _STATUS_PRIORITY.index(status) if status in _STATUS_PRIORITY else len(_STATUS_PRIORITY))


def _remediation_steps(control: Any) -> list[str]:
    return list(control.remediation_steps or ([control.remediation_summary] if control.remediation_summary else []))


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
    retain: int = RETAIN_RUNS_PER_PLATFORM,
) -> tuple[ZeroTrustRun, dict[str, Any]]:
    """Persist one run and its checks, pruning the platform's older runs.

    The caller commits.
    """
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
    await prune_runs(db, tenant_id=tenant_id, source=source, keep=retain)
    return run, summary


async def prune_runs(db: AsyncSession, *, tenant_id: str, source: str, keep: int = RETAIN_RUNS_PER_PLATFORM) -> int:
    """Delete all but the newest ``keep`` runs for one tenant and platform.

    Returns how many runs were removed. Ordering is by creation time with the id
    as a tie-breaker, because imports within the same second share a timestamp.
    """
    if keep < 1:
        return 0
    stale = list(
        (
            await db.execute(
                select(ZeroTrustRun.id)
                .where(ZeroTrustRun.tenant_id == tenant_id, ZeroTrustRun.source == source)
                .order_by(desc(ZeroTrustRun.created_at), desc(ZeroTrustRun.id))
                .offset(keep)
            )
        )
        .scalars()
        .all()
    )
    if not stale:
        return 0
    await db.execute(delete(ZeroTrustCheck).where(ZeroTrustCheck.run_id.in_(stale)))
    await db.execute(delete(ZeroTrustRun).where(ZeroTrustRun.id.in_(stale)))
    await db.flush()
    return len(stale)


async def _finding_states(db: AsyncSession, tenant_id: str) -> dict[str, str]:
    rows = (await db.execute(select(Finding.external_control_id, Finding.state).where(Finding.tenant_id == tenant_id))).all()
    states: dict[str, str] = {}
    for control_id, state in rows:
        # Later rows overwrite; findings are one row per control, so this is the current state.
        states[control_id] = state
    return states


async def _microsoft_checks(db: AsyncSession, tenant_id: str) -> list[dict[str, Any]]:
    """Every upstream Microsoft Zero Trust test, scored from local evidence.

    Microsoft's assessment is 364 PowerShell tests; this reports all of them in
    their own ids so an export from the PowerShell runner and a Python run can be
    compared row for row. A test whose evidence a control collects takes that
    control's finding; the rest stay ``not_run`` instead of being assumed to pass.
    Controls that the catalogue does not cover are appended under their own ids so
    their findings are still visible.
    """
    states = await _finding_states(db, tenant_id)
    services = set(PLATFORM_SERVICES["microsoft"])
    controls = [control for control in ControlLoader().load_all() if control.service in services]

    by_test: dict[str, list[Any]] = {}
    for control in controls:
        for test_id in control.ms_zt_tests:
            by_test.setdefault(test_id, []).append(control)

    checks: list[dict[str, Any]] = []
    for test in MICROSOFT_TESTS:
        backing = by_test.get(test.id, [])
        checks.append(_catalogue_check(test.id, test.title, test.pillar, test.severity, test.category, backing, states))

    mapped_controls = {control.id for test_id in TEST_IDS for control in by_test.get(test_id, [])}
    for control in controls:
        if control.id not in mapped_controls:
            checks.append(_control_check(control, states.get(control.id)))
    return checks


def _catalogue_check(
    check_id: str,
    title: str,
    pillar: str,
    severity: str,
    category: str,
    backing: list[Any],
    states: dict[str, str],
    fallback_remediation: list[str] | None = None,
) -> dict[str, Any]:
    """Score one catalogue row from the findings of the controls behind it.

    Only controls that actually reported a result are aggregated: a sibling with
    no evidence must not hide the one control that did.
    """
    statuses = [_STATUS_TO_RESULT.get(states.get(control.id, ""), "not_run") for control in backing]
    evidence = [status for status in statuses if status != "not_run"]
    return {
        "check_id": check_id,
        "title": title,
        "pillar": pillar,
        "severity": severity,
        "status": _worst_status(evidence),
        "category": category,
        "remediation": next(
            (steps for control in backing if (steps := _remediation_steps(control))),
            fallback_remediation or [],
        ),
        "reference": "",
    }


# What Microsoft's module writes in TestStatus.
MODULE_STATUS_TO_RESULT = {
    "passed": "pass",
    "failed": "fail",
    "investigate": "warn",
    "error": "fail",
    "skipped": "not_applicable",
    "planned": "not_run",
    "notrun": "not_run",
    "not run": "not_run",
}


def checks_from_module_export(payload: Any) -> list[dict[str, Any]]:
    """The checks Microsoft's own assessment produced, in our row shape.

    ``Invoke-ZtAssessment`` writes ``ZeroTrustAssessmentReport.json`` next to its
    HTML report with one ``Tests`` row per executed test (``TestId``, ``TestTitle``,
    ``TestStatus``, ``TestPillar``, ``TestRisk``, ``TestCategory``). Reading it is
    what makes the run show real statuses: the Python catalogue can only score the
    tests whose evidence UniMonitor also collects.
    """
    if not isinstance(payload, dict):
        return []
    rows = payload.get("Tests") or payload.get("tests") or []
    if not isinstance(rows, list):
        return []
    checks: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        test_id = str(row.get("TestId") or row.get("testId") or "").strip()
        title = str(row.get("TestTitle") or row.get("title") or "").strip()
        if not test_id or not title:
            continue
        status = str(row.get("TestStatus") or row.get("status") or "").strip()
        pillar = str(row.get("TestPillar") or "identity").strip().lower() or "identity"
        severity = str(row.get("TestRisk") or "medium").strip().lower() or "medium"
        checks.append(
            {
                "check_id": test_id,
                "title": title,
                "pillar": pillar,
                "severity": severity,
                "status": MODULE_STATUS_TO_RESULT.get(status.lower(), "not_run"),
                "category": str(row.get("TestCategory") or "") or None,
                "remediation": [],
                "reference": "",
            }
        )
    return checks


def _control_check(control: Any, current_state: str | None) -> dict[str, Any]:
    return {
        "check_id": control.id,
        "title": control.title,
        "pillar": _control_pillar(control.compliance_mapping) or "infrastructure",
        "severity": control.severity.lower(),
        "status": _STATUS_TO_RESULT.get(current_state or "", "not_run"),
        "category": control.service,
        "remediation": _remediation_steps(control),
        "reference": "",
    }


async def cloud_checks(db: AsyncSession, tenant_id: str, platform: str) -> list[dict[str, Any]]:
    """Evaluate the platform's checks against the tenant's latest findings.

    Microsoft is served from the ported PowerShell catalogue; AWS, Google Cloud
    and Google Workspace from their native Python catalogues. Either way the
    remediation text comes from the control YAML where one backs the test, so
    every check carries a "what to do next". A control the catalogue does not map
    is appended under its own id so its finding is still visible.
    """
    if platform == "microsoft":
        return await _microsoft_checks(db, tenant_id)

    states = await _finding_states(db, tenant_id)
    services = PLATFORM_SERVICES.get(platform, (platform,))
    controls = [control for control in ControlLoader().load_all() if control.service in services]
    tests = tests_for(platform)

    if not tests:
        return [_control_check(control, states.get(control.id)) for control in controls]

    by_id = {control.id: control for control in controls}
    checks = [
        _catalogue_check(
            test.id,
            test.title,
            test.pillar,
            test.severity,
            test.category,
            [by_id[cid] for cid in test.control_ids if cid in by_id],
            states,
            list(test.remediation),
        )
        for test in tests
    ]
    mapped = {control_id for test in tests for control_id in test.control_ids}
    checks.extend(_control_check(control, states.get(control.id)) for control in controls if control.id not in mapped)
    return checks


def catalogue_for(platform: str) -> tuple[str, list[PlatformTest]]:
    """Catalogue name and rows for a platform (Microsoft included)."""
    if platform == "microsoft":
        return "Microsoft Zero Trust Assessment", [
            PlatformTest(test.id, test.title, test.pillar, test.category, test.severity, (), (), "") for test in MICROSOFT_TESTS
        ]
    from unimonitor.zerotrust.platform_tests import PLATFORM_CATALOGUE_NAMES

    return PLATFORM_CATALOGUE_NAMES.get(platform, platform), list(tests_for(platform))


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
