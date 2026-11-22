"""Evidence package endpoint and requirement-level framework reporting."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from unimonitor.api.v1.lookups import latest_findings_by_control
from unimonitor.auth.dependencies import require_compliance
from unimonitor.auth.tenant_scope import tenant_scope

router = APIRouter()

MAX_EVIDENCE_CHARS = 2000


class RequirementRow(BaseModel):
    id: str
    title: str
    family: str
    family_code: str
    level: int
    controls_total: int
    implemented: int
    partial: int
    not_implemented: int
    not_applicable: int
    coverage_pct: float
    status: str  # implemented | partial | gap | not_run


class RequirementCatalogue(BaseModel):
    framework_id: str
    framework_name: str
    requirement_count: int
    level1_count: int
    rows: list[RequirementRow]
    generated_at: datetime


def _control_state(finding: Any) -> str:
    if finding is None:
        return "not_run"
    return finding.state


@router.get("/frameworks/{framework_id}/requirements", responses={404: {"description": "Not found"}})
async def framework_requirements(
    framework_id: str,
    current_user: Annotated[Any, Depends(require_compliance())],
    tenant_id: Annotated[str | None, Depends(tenant_scope)] = None,
) -> RequirementCatalogue:
    """Per-requirement status for a framework with a requirement catalogue.

    Today that is CPCSC (98 ITSP.10.171 requirements). Other frameworks have
    control-level mappings only, and say so rather than inventing requirement ids.
    """
    from datetime import UTC, datetime

    from sqlalchemy import select

    from unimonitor.api.v1.controls import SUPPORTED_FRAMEWORKS
    from unimonitor.db.base import async_session_factory
    from unimonitor.db.models.finding import Finding
    from unimonitor.grc.framework_mappings import cpcsc_requirements
    from unimonitor.grc.frameworks import get_framework

    fw_info = next((f for f in SUPPORTED_FRAMEWORKS if f["id"] == framework_id), None)
    if not fw_info:
        raise HTTPException(status_code=404, detail=f"Framework '{framework_id}' not found")
    if framework_id != "cpcsc":
        raise HTTPException(
            status_code=404,
            detail=f"Framework '{framework_id}' has no requirement catalogue; use /frameworks/{framework_id}/controls",
        )

    async with async_session_factory() as session:
        stmt = select(Finding.external_control_id, Finding.state)
        if tenant_id:
            stmt = stmt.where(Finding.tenant_id == tenant_id)
        states = {row[0]: row[1] for row in (await session.execute(stmt)).all()}

    rows: list[RequirementRow] = []
    for requirement in cpcsc_requirements():
        counts = _requirement_counts(requirement, states)
        applicable = sum(counts[key] for key in ("implemented", "partial", "not_implemented", "not_run"))
        coverage = round(((counts["implemented"] + counts["partial"] * 0.5) / applicable) * 100, 2) if applicable else 0.0
        status = _requirement_status(counts, applicable)

        rows.append(
            RequirementRow(
                id=requirement["id"],
                title=requirement["title"],
                family=requirement["family"],
                family_code=requirement["family_code"],
                level=requirement["level"],
                controls_total=len(requirement["controls"]),
                implemented=counts["implemented"],
                partial=counts["partial"],
                not_implemented=counts["not_implemented"],
                not_applicable=counts["not_applicable"],
                coverage_pct=coverage,
                status=status,
            )
        )

    meta = get_framework(framework_id)
    return RequirementCatalogue(
        framework_id=framework_id,
        framework_name=meta.name if meta else fw_info["name"],
        requirement_count=len(rows),
        level1_count=sum(1 for row in rows if row.level == 1),
        rows=rows,
        generated_at=datetime.now(UTC),
    )


@router.get("/frameworks/{framework_id}/evidence-package", responses={404: {"description": "Not found"}})
async def evidence_package(
    framework_id: str,
    current_user: Annotated[Any, Depends(require_compliance())],
    tenant_id: Annotated[str | None, Depends(tenant_scope)] = None,
    include_evidence: Annotated[bool, Query(description="Include captured evidence content")] = True,
) -> dict[str, Any]:
    """A self-contained, hashed evidence package for an auditor.

    Read-only in intent: it exposes control state, the findings behind it and the
    captured evidence, plus a SHA-256 digest of the payload so an auditor can
    confirm the copy they received is the copy the platform produced. Nothing in
    this response is editable, and no credential material is included.
    """
    from unimonitor.api.v1.controls import SUPPORTED_FRAMEWORKS
    from unimonitor.db.base import async_session_factory
    from unimonitor.grc.control_loader import controls_for_framework
    from unimonitor.grc.frameworks import get_framework

    fw_info = next((f for f in SUPPORTED_FRAMEWORKS if f["id"] == framework_id), None)
    if not fw_info:
        raise HTTPException(status_code=404, detail=f"Framework '{framework_id}' not found")

    controls = controls_for_framework(framework_id)
    meta = get_framework(framework_id)

    async with async_session_factory() as session:
        findings = await latest_findings_by_control(session, [control.id for control in controls], tenant_id)
        evidence = await _load_evidence(session, findings, include_evidence)

    package_rows = [_package_row(control, findings.get(control.id), evidence) for control in controls]
    payload = _package_payload(framework_id, fw_info, meta, tenant_id, current_user, package_rows)
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return {**payload, "digest_sha256": digest, "digest_algorithm": "sha256"}


async def _load_evidence(session: Any, findings: dict[str, Any], include_evidence: bool) -> dict[str, list[dict[str, Any]]]:
    """Up to three captured evidence entries per finding, newest first."""
    if not include_evidence or not findings:
        return {}

    from sqlalchemy import select

    from unimonitor.db.models.finding import FindingEvidence

    evidence_rows = (
        await session.execute(
            select(FindingEvidence)
            .where(FindingEvidence.finding_id.in_([f.id for f in findings.values()]))
            .order_by(FindingEvidence.collected_at.desc())
        )
    ).scalars()

    evidence: dict[str, list[dict[str, Any]]] = {}
    for evidence_row in evidence_rows:
        bucket = evidence.setdefault(evidence_row.finding_id, [])
        if len(bucket) >= 3:
            continue
        bucket.append(
            {
                "type": evidence_row.evidence_type,
                "source": evidence_row.source,
                "content": (evidence_row.content or "")[:MAX_EVIDENCE_CHARS],
                "collected_at": evidence_row.collected_at.isoformat(),
            }
        )
    return evidence


def _package_row(control: Any, finding: Any, evidence: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """One control row: its state, the finding behind it and its evidence."""
    return {
        "control_id": control.id,
        "title": control.title,
        "category": control.category,
        "severity": control.severity.lower(),
        "state": _control_state(finding),
        "last_seen_at": finding.last_seen_at.isoformat() if finding and finding.last_seen_at else None,
        "finding_id": finding.id if finding else None,
        "finding_title": finding.title if finding else None,
        "remediation": "\n".join(control.remediation_steps) or control.remediation_summary,
        "evidence": evidence.get(finding.id, []) if finding else [],
    }


def _package_payload(
    framework_id: str,
    fw_info: dict[str, Any],
    meta: Any,
    tenant_id: str | None,
    current_user: Any,
    package_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """The hashed package body: framework, tenant, control rows and state counts."""
    states = [row["state"] for row in package_rows]
    return {
        "framework": {
            "id": framework_id,
            "name": meta.name if meta else fw_info["name"],
            "version": meta.version if meta else "",
            "mapping_note": meta.mapping_note if meta else "",
        },
        "tenant_id": tenant_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "generated_by": getattr(current_user, "email", None),
        "controls_total": len(package_rows),
        "controls": package_rows,
        "summary": {state: states.count(state) for state in ("implemented", "partially_implemented", "not_implemented", "not_applicable", "not_run")},
    }


def _requirement_counts(requirement: dict[str, Any], states: dict[str, str]) -> dict[str, int]:
    """How many of a requirement's controls sit in each state."""
    counts = {"implemented": 0, "partial": 0, "not_implemented": 0, "not_applicable": 0, "not_run": 0}
    bucket_for = {"implemented": "implemented", "partially_implemented": "partial", "not_applicable": "not_applicable", "not_run": "not_run"}
    for control_id in requirement["controls"]:
        counts[bucket_for.get(states.get(control_id, "not_run"), "not_implemented")] += 1
    return counts


def _requirement_status(counts: dict[str, int], applicable: int) -> str:
    """Implemented, partial, not run, or a gap — in that order of precedence."""
    if applicable and counts["implemented"] == applicable:
        return "implemented"
    if counts["implemented"] or counts["partial"]:
        return "partial"
    if counts["not_run"] == applicable:
        return "not_run"
    return "gap"
