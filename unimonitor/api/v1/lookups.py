"""Read-only finding queries shared by more than one endpoint module.

Both the framework views and the auditor portal need "the newest finding per
control" and "evidence grouped by finding", so they live here once.
"""

from __future__ import annotations

from typing import Any


async def latest_findings_by_control(session: Any, control_ids: list[str], tenant_id: str | None = None) -> dict[str, Any]:
    """Newest finding per external control id, optionally scoped to one tenant."""
    from sqlalchemy import select

    from unimonitor.db.models.finding import Finding

    if not control_ids:
        return {}
    stmt = select(Finding).where(Finding.external_control_id.in_(control_ids))
    if tenant_id:
        stmt = stmt.where(Finding.tenant_id == tenant_id)
    stmt = stmt.order_by(Finding.last_seen_at.desc())
    findings: dict[str, Any] = {}
    for finding in (await session.execute(stmt)).scalars():
        findings.setdefault(finding.external_control_id, finding)
    return findings


async def evidence_by_finding(session: Any, finding_ids: list[str]) -> dict[str, list[Any]]:
    """Evidence rows grouped by finding id, newest first."""
    from sqlalchemy import select

    from unimonitor.db.models.finding import FindingEvidence

    grouped: dict[str, list[Any]] = {}
    if not finding_ids:
        return grouped
    stmt = select(FindingEvidence).where(FindingEvidence.finding_id.in_(finding_ids)).order_by(FindingEvidence.collected_at.desc())
    for row in (await session.execute(stmt)).scalars():
        grouped.setdefault(row.finding_id, []).append(row)
    return grouped
