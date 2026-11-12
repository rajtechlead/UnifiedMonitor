"""Finding repository with domain-specific queries."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import and_, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.db.models.finding import Finding, FindingEvidence, FindingHistory, FindingState
from unimonitor.db.repositories.base import BaseRepository


class FindingRepository(BaseRepository[Finding]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Finding, session)

    # ── Convenience wrappers ──────────────────────────────────────

    async def get_by_id(self, finding_id: str) -> Finding | None:
        return await self.get(finding_id)

    async def update(self, finding_id: str, **kwargs: Any) -> Finding:  # type: ignore[override]
        obj = await self.get_or_raise(finding_id)
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    # ── Summary / counts ──────────────────────────────────────────

    async def get_summary(self, tenant_id: str | None = None) -> dict:
        """Return aggregated counts by severity, state, category, plus suppressed."""
        base_cond = []
        if tenant_id:
            base_cond.append(Finding.tenant_id == tenant_id)

        # Total
        total_q = select(func.count(Finding.id))
        if base_cond:
            total_q = total_q.where(and_(*base_cond))
        total_result = await self.session.execute(total_q)
        total = total_result.scalar_one()

        # Suppressed count
        supp_cond = base_cond + [Finding.is_suppressed.is_(True)]
        supp_q = select(func.count(Finding.id)).where(and_(*supp_cond))
        supp_result = await self.session.execute(supp_q)
        suppressed_count = supp_result.scalar_one()

        # By severity
        sev_q = (
            select(Finding.severity, func.count(Finding.id))
            .where(and_(*base_cond) if base_cond else True)
            .group_by(Finding.severity)
        )
        sev_result = await self.session.execute(sev_q)
        by_severity = {row[0]: row[1] for row in sev_result.all()}

        # By state
        state_q = (
            select(Finding.state, func.count(Finding.id))
            .where(and_(*base_cond) if base_cond else True)
            .group_by(Finding.state)
        )
        state_result = await self.session.execute(state_q)
        by_state = {row[0]: row[1] for row in state_result.all()}

        # By category
        cat_q = (
            select(Finding.category, func.count(Finding.id))
            .where(and_(*base_cond) if base_cond else True)
            .group_by(Finding.category)
        )
        cat_result = await self.session.execute(cat_q)
        by_category = {row[0]: row[1] for row in cat_result.all()}

        return {
            "total": total,
            "suppressed_count": suppressed_count,
            "by_severity": by_severity,
            "by_state": by_state,
            "by_category": by_category,
        }

    # ── Paginated list ────────────────────────────────────────────

    async def list_paginated(
        self,
        tenant_id: str | None = None,
        severity: str | None = None,
        state: str | None = None,
        category: str | None = None,
        service: str | None = None,
        is_suppressed: bool | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "last_seen_at",
        sort_desc: bool = True,
    ) -> tuple[Sequence[Finding], int]:
        """Return (findings, total) with filtering and pagination."""
        conditions = []
        if tenant_id:
            conditions.append(Finding.tenant_id == tenant_id)
        if severity:
            conditions.append(Finding.severity == severity)
        if state:
            conditions.append(Finding.state == state)
        if category:
            conditions.append(Finding.category == category)
        if service:
            conditions.append(Finding.service == service)
        if is_suppressed is not None:
            conditions.append(Finding.is_suppressed.is_(is_suppressed))
        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(
                    Finding.title.ilike(pattern),
                    Finding.description.ilike(pattern),
                    Finding.external_control_id.ilike(pattern),
                )
            )

        where_clause = and_(*conditions) if conditions else True

        # Count
        count_q = select(func.count(Finding.id)).where(where_clause)
        total_result = await self.session.execute(count_q)
        total = total_result.scalar_one()

        # Sort
        sort_col = getattr(Finding, sort_by, Finding.last_seen_at)
        order = desc(sort_col) if sort_desc else asc(sort_col)

        offset = (page - 1) * page_size
        rows_q = (
            select(Finding)
            .where(where_clause)
            .order_by(order)
            .offset(offset)
            .limit(page_size)
        )
        rows_result = await self.session.execute(rows_q)
        return rows_result.scalars().all(), total

    # ── History ───────────────────────────────────────────────────

    async def add_history(
        self,
        finding_id: str,
        previous_state: str,
        new_state: str,
        changed_by: str | None = None,
        comment: str | None = None,
    ) -> FindingHistory:
        history = FindingHistory(
            finding_id=finding_id,
            previous_state=previous_state,
            new_state=new_state,
            changed_by=changed_by,
            comment=comment,
        )
        self.session.add(history)
        await self.session.flush()
        return history

    async def get_history(self, finding_id: str) -> Sequence[FindingHistory]:
        result = await self.session.execute(
            select(FindingHistory)
            .where(FindingHistory.finding_id == finding_id)
            .order_by(desc(FindingHistory.changed_at))
        )
        return result.scalars().all()

    # ── Legacy helpers (kept for backward compat) ─────────────────

    async def get_by_tenant(
        self,
        tenant_id: str,
        *,
        severity: str | None = None,
        state: str | None = None,
        service: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[Finding]:
        stmt = (
            select(Finding)
            .where(
                and_(
                    Finding.tenant_id == tenant_id,
                    Finding.is_suppressed.is_(False),
                )
            )
            .order_by(Finding.first_detected_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if severity:
            stmt = stmt.where(Finding.severity == severity)
        if state:
            stmt = stmt.where(Finding.state == state)
        if service:
            stmt = stmt.where(Finding.service == service)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_severity_summary(self, tenant_id: str) -> dict[str, int]:
        stmt = (
            select(Finding.severity, func.count(Finding.id))
            .where(
                and_(
                    Finding.tenant_id == tenant_id,
                    Finding.is_suppressed.is_(False),
                )
            )
            .group_by(Finding.severity)
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def get_state_summary(self, tenant_id: str) -> dict[str, int]:
        stmt = (
            select(Finding.state, func.count(Finding.id))
            .where(Finding.tenant_id == tenant_id)
            .group_by(Finding.state)
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def upsert_finding(
        self,
        tenant_id: str,
        external_control_id: str,
        assessment_run_id: str,
        **data,
    ) -> tuple[Finding, bool]:
        """Create or update a finding; returns (finding, created)."""
        stmt = select(Finding).where(
            and_(
                Finding.tenant_id == tenant_id,
                Finding.external_control_id == external_control_id,
            )
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            old_state = existing.state
            for k, v in data.items():
                setattr(existing, k, v)
            existing.assessment_run_id = assessment_run_id
            if existing.state != old_state:
                history = FindingHistory(
                    finding_id=existing.id,
                    previous_state=old_state,
                    new_state=existing.state,
                )
                self.session.add(history)
            await self.session.flush()
            return existing, False
        else:
            finding = Finding(
                tenant_id=tenant_id,
                external_control_id=external_control_id,
                assessment_run_id=assessment_run_id,
                **data,
            )
            self.session.add(finding)
            await self.session.flush()
            return finding, True

    async def change_state(
        self, finding_id: str, new_state: str, changed_by: str | None = None, comment: str | None = None
    ) -> Finding:
        finding = await self.get_or_raise(finding_id)
        old_state = finding.state
        finding.state = new_state
        history = FindingHistory(
            finding_id=finding_id,
            previous_state=old_state,
            new_state=new_state,
            changed_by=changed_by,
            comment=comment,
        )
        self.session.add(history)
        await self.session.flush()
        return finding

    async def add_evidence(
        self,
        finding_id: str,
        evidence_type: str,
        source: str,
        content: str,
    ) -> FindingEvidence:
        evidence = FindingEvidence(
            finding_id=finding_id,
            evidence_type=evidence_type,
            source=source,
            content=content,
        )
        self.session.add(evidence)
        await self.session.flush()
        return evidence

    async def get_top_findings(
        self,
        tenant_id: str | None = None,
        limit: int = 10,
    ) -> Sequence[Finding]:
        """Return top-priority non-suppressed, non-implemented findings."""

        stmt = (
            select(Finding)
            .where(
                and_(
                    Finding.state != FindingState.NOT_APPLICABLE.value,
                    Finding.state != FindingState.IMPLEMENTED.value,
                    Finding.is_suppressed.is_(False),
                )
            )
            .order_by(Finding.risk_score.desc(), Finding.first_detected_at.asc())
            .limit(limit)
        )
        if tenant_id:
            stmt = stmt.where(Finding.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_risk_heatmap(
        self,
        tenant_id: str | None = None,
    ) -> list[dict]:
        """Return risk heatmap cells (likelihood x impact)."""
        # Basic implementation: group by severity as proxy for likelihood/impact
        stmt = (
            select(Finding.severity, func.count(Finding.id).label("cnt"))
            .where(Finding.is_suppressed.is_(False))
            .group_by(Finding.severity)
        )
        if tenant_id:
            stmt = stmt.where(Finding.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        rows = result.all()

        # Map severity → likelihood/impact grid
        sev_to_coords = {
            "critical": (5, 5),
            "high": (4, 4),
            "medium": (3, 3),
            "low": (2, 2),
            "informational": (1, 1),
        }
        cells = []
        for sev, count in rows:
            coords = sev_to_coords.get(sev, (3, 3))
            cells.append({
                "likelihood": coords[0],
                "impact": coords[1],
                "count": count,
                "finding_ids": [],
            })
        return cells

    async def get_recent_activity(
        self,
        tenant_id: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Return recent finding state changes as activity items."""
        stmt = (
            select(FindingHistory)
            .join(Finding, FindingHistory.finding_id == Finding.id)
            .order_by(desc(FindingHistory.changed_at))
            .limit(limit)
        )
        if tenant_id:
            stmt = stmt.where(Finding.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "timestamp": r.changed_at,
                "event_type": "state_change",
                "description": f"Finding state changed: {r.previous_state} → {r.new_state}",
                "actor": r.changed_by,
            }
            for r in rows
        ]

    async def add_history(
        self,
        finding_id: str,
        previous_state: str,
        new_state: str,
        changed_by: str | None = None,
        comment: str | None = None,
    ) -> FindingHistory:
        """Add a state-change history entry for a finding."""
        history = FindingHistory(
            finding_id=finding_id,
            previous_state=previous_state,
            new_state=new_state,
            changed_by=changed_by,
            comment=comment,
        )
        self.session.add(history)
        await self.session.flush()
        await self.session.refresh(history)
        return history

    async def get_history(
        self,
        finding_id: str,
    ) -> Sequence[FindingHistory]:
        """Return all state-change history for a finding."""
        stmt = (
            select(FindingHistory)
            .where(FindingHistory.finding_id == finding_id)
            .order_by(desc(FindingHistory.changed_at))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
