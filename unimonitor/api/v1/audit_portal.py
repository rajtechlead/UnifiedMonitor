"""Evidence package endpoint and requirement-level framework reporting."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from unimonitor.auth.dependencies import require_compliance

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


@router.get("/frameworks/{framework_id}/requirements")
async def framework_requirements(
    framework_id: str,
    current_user: Annotated[Any, Depends(require_compliance())],
    tenant_id: str | None = Query(default=None),
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
        counts = {"implemented": 0, "partial": 0, "not_implemented": 0, "not_applicable": 0, "not_run": 0}
        for control_id in requirement["controls"]:
            state = states.get(control_id, "not_run")
            if state == "implemented":
                counts["implemented"] += 1
            elif state == "partially_implemented":
                counts["partial"] += 1
            elif state == "not_applicable":
                counts["not_applicable"] += 1
            elif state == "not_run":
                counts["not_run"] += 1
            else:
                counts["not_implemented"] += 1

        applicable = sum(counts[key] for key in ("implemented", "partial", "not_implemented", "not_run"))
        coverage = round(((counts["implemented"] + counts["partial"] * 0.5) / applicable) * 100, 2) if applicable else 0.0
        if counts["implemented"] == applicable and applicable:
            status = "implemented"
        elif counts["implemented"] or counts["partial"]:
            status = "partial"
        elif counts["not_run"] == applicable:
            status = "not_run"
        else:
            status = "gap"

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


@router.get("/frameworks/{framework_id}/evidence-package")
async def evidence_package(
    framework_id: str,
    current_user: Annotated[Any, Depends(require_compliance())],
    tenant_id: str | None = Query(default=None),
    include_evidence: bool = Query(default=True, description="Include captured evidence content"),
) -> dict[str, Any]:
    """A self-contained, hashed evidence package for an auditor.

    Read-only in intent: it exposes control state, the findings behind it and the
    captured evidence, plus a SHA-256 digest of the payload so an auditor can
    confirm the copy they received is the copy the platform produced. Nothing in
    this response is editable, and no credential material is included.
    """
    from sqlalchemy import select

    from unimonitor.api.v1.controls import SUPPORTED_FRAMEWORKS
    from unimonitor.db.base import async_session_factory
    from unimonitor.db.models.finding import Finding, FindingEvidence
    from unimonitor.grc.control_loader import controls_for_framework
    from unimonitor.grc.frameworks import get_framework

    fw_info = next((f for f in SUPPORTED_FRAMEWORKS if f["id"] == framework_id), None)
    if not fw_info:
        raise HTTPException(status_code=404, detail=f"Framework '{framework_id}' not found")

    controls = controls_for_framework(framework_id)
    meta = get_framework(framework_id)

    async with async_session_factory() as session:
        findings: dict[str, Finding] = {}
        if controls:
            stmt = select(Finding).where(Finding.external_control_id.in_([control.id for control in controls]))
            if tenant_id:
                stmt = stmt.where(Finding.tenant_id == tenant_id)
            stmt = stmt.order_by(Finding.last_seen_at.desc())
            for finding in (await session.execute(stmt)).scalars():
                findings.setdefault(finding.external_control_id, finding)

        evidence: dict[str, list[dict[str, Any]]] = {}
        if include_evidence and findings:
            evidence_rows = (
                await session.execute(
                    select(FindingEvidence)
                    .where(FindingEvidence.finding_id.in_([f.id for f in findings.values()]))
                    .order_by(FindingEvidence.collected_at.desc())
                )
            ).scalars()
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

    package_rows: list[dict[str, Any]] = []
    for control in controls:
        control_finding = findings.get(control.id)
        package_rows.append(
            {
                "control_id": control.id,
                "title": control.title,
                "category": control.category,
                "severity": control.severity.lower(),
                "state": _control_state(control_finding),
                "last_seen_at": control_finding.last_seen_at.isoformat() if control_finding and control_finding.last_seen_at else None,
                "finding_id": control_finding.id if control_finding else None,
                "finding_title": control_finding.title if control_finding else None,
                "remediation": "\n".join(control.remediation_steps) or control.remediation_summary,
                "evidence": evidence.get(control_finding.id, []) if control_finding else [],
            }
        )

    generated_at = datetime.now(UTC)
    payload = {
        "framework": {
            "id": framework_id,
            "name": meta.name if meta else fw_info["name"],
            "version": meta.version if meta else "",
            "mapping_note": meta.mapping_note if meta else "",
        },
        "tenant_id": tenant_id,
        "generated_at": generated_at.isoformat(),
        "generated_by": getattr(current_user, "email", None),
        "controls_total": len(package_rows),
        "controls": package_rows,
        "summary": {
            "implemented": sum(1 for row in package_rows if row["state"] == "implemented"),
            "partially_implemented": sum(1 for row in package_rows if row["state"] == "partially_implemented"),
            "not_implemented": sum(1 for row in package_rows if row["state"] == "not_implemented"),
            "not_applicable": sum(1 for row in package_rows if row["state"] == "not_applicable"),
            "not_run": sum(1 for row in package_rows if row["state"] == "not_run"),
        },
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return {**payload, "digest_sha256": digest, "digest_algorithm": "sha256"}
