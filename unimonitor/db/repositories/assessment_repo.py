"""Assessment and run repository."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.db.models.assessment import Assessment, AssessmentRun, AssessmentStatus
from unimonitor.db.repositories.base import BaseRepository


class AssessmentRepository(BaseRepository[Assessment]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Assessment, session)

    # ── Convenience wrappers ──────────────────────────────────────

    async def get_by_id(self, assessment_id: str) -> Assessment | None:
        return await self.get(assessment_id)

    async def list_all(
        self,
        tenant_id: str | None = None,
        is_active: bool | None = None,
    ) -> Sequence[Assessment]:
        stmt = select(Assessment)
        if tenant_id is not None:
            stmt = stmt.where(Assessment.tenant_id == tenant_id)
        if is_active is not None:
            stmt = stmt.where(Assessment.is_active == is_active)
        stmt = stmt.order_by(desc(Assessment.created_at))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, assessment_id: str, **kwargs: Any) -> Assessment:  # type: ignore[override]
        obj = await self.get_or_raise(assessment_id)
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, assessment_id: str) -> None:  # type: ignore[override]
        obj = await self.get_or_raise(assessment_id)
        await self.session.delete(obj)
        await self.session.flush()

    # ── Active tenants ────────────────────────────────────────────

    async def get_active_for_tenant(self, tenant_id: str) -> Sequence[Assessment]:
        result = await self.session.execute(
            select(Assessment).where(
                and_(Assessment.tenant_id == tenant_id, Assessment.is_active.is_(True))
            )
        )
        return result.scalars().all()

    # ── Run helpers ───────────────────────────────────────────────

    async def get_latest_run(self, assessment_id: str) -> AssessmentRun | None:
        result = await self.session.execute(
            select(AssessmentRun)
            .where(AssessmentRun.assessment_id == assessment_id)
            .order_by(desc(AssessmentRun.started_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_run(
        self,
        assessment_id: str,
        trigger: str = "manual",
        triggered_by: str | None = None,
    ) -> AssessmentRun:
        run = AssessmentRun(
            assessment_id=assessment_id,
            trigger=trigger,
            triggered_by=triggered_by,
            status=AssessmentStatus.PENDING.value,
        )
        self.session.add(run)
        await self.session.flush()
        await self.session.refresh(run)
        return run

    async def get_run_by_id(self, run_id: str) -> AssessmentRun | None:
        return await self.session.get(AssessmentRun, run_id)

    async def update_run(self, run_id: str, **kwargs: Any) -> AssessmentRun:
        run = await self.session.get(AssessmentRun, run_id)
        if run is None:
            from unimonitor.exceptions import NotFoundError
            raise NotFoundError(f"AssessmentRun '{run_id}' not found")
        for key, value in kwargs.items():
            setattr(run, key, value)
        await self.session.flush()
        await self.session.refresh(run)
        return run

    async def list_runs(
        self,
        assessment_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[AssessmentRun], int]:
        total_result = await self.session.execute(
            select(func.count()).select_from(AssessmentRun).where(
                AssessmentRun.assessment_id == assessment_id
            )
        )
        total = total_result.scalar_one()
        offset = (page - 1) * page_size
        runs_result = await self.session.execute(
            select(AssessmentRun)
            .where(AssessmentRun.assessment_id == assessment_id)
            .order_by(desc(AssessmentRun.started_at))
            .offset(offset)
            .limit(page_size)
        )
        return runs_result.scalars().all(), total


    async def get_latest_completed_run(self, tenant_id: str | None = None) -> AssessmentRun | None:
        """Return the most recent completed run, optionally filtered by tenant."""
        stmt = (
            select(AssessmentRun)
            .join(Assessment, AssessmentRun.assessment_id == Assessment.id)
            .where(AssessmentRun.status == AssessmentStatus.COMPLETED.value)
        )
        if tenant_id:
            stmt = stmt.where(Assessment.tenant_id == tenant_id)
        stmt = stmt.order_by(desc(AssessmentRun.completed_at)).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_score_trends(
        self, tenant_id: str | None = None, days: int = 30
    ) -> list[dict]:
        """Return daily score trend data for the last N days."""
        from datetime import datetime, timedelta
        cutoff = datetime.now(UTC) - timedelta(days=days)
        stmt = (
            select(AssessmentRun)
            .join(Assessment, AssessmentRun.assessment_id == Assessment.id)
            .where(
                AssessmentRun.status == AssessmentStatus.COMPLETED.value,
                AssessmentRun.completed_at >= cutoff,
            )
        )
        if tenant_id:
            stmt = stmt.where(Assessment.tenant_id == tenant_id)
        stmt = stmt.order_by(AssessmentRun.completed_at)
        result = await self.session.execute(stmt)
        runs = result.scalars().all()

        return [
            {
                "date": r.completed_at.strftime("%Y-%m-%d") if r.completed_at else "",
                "security_score": r.security_score or 0.0,
                "compliance_score": r.compliance_score or 0.0,
                "risk_score": r.risk_score or 0.0,
            }
            for r in runs
        ]

    async def get_finding_trends(
        self, tenant_id: str | None = None, days: int = 30
    ) -> list[dict]:
        """Return daily new-finding counts for the past ``days`` days.

        Each row: ``{"date": "YYYY-MM-DD", "total": int, "critical": int,
        "high": int, "medium": int, "low": int}``

        Uses a date-bucket GROUP BY that works on both PostgreSQL and SQLite.
        """
        try:
            from unimonitor.db.models.finding import Finding  # local import avoids circulars

            cutoff = datetime.now(tz=UTC) - timedelta(days=days)

            # Portable date truncation: SQLite uses strftime, PostgreSQL uses date_trunc
            # We detect dialect via the connection URL prefix set at startup
            bind = self.session.get_bind()
            dialect_name = getattr(bind, "dialect", None)
            dialect_name = getattr(dialect_name, "name", "") if dialect_name else ""

            if dialect_name == "postgresql":
                day_col = func.date_trunc("day", Finding.first_detected_at).label("day")
            else:
                # SQLite
                day_col = func.strftime("%Y-%m-%d", Finding.first_detected_at).label("day")

            stmt = (
                select(
                    day_col,
                    func.count().label("total"),
                    func.sum(
                        func.cast(Finding.severity == "critical", type_=func.count().type)
                        if dialect_name == "postgresql"
                        else func.iif(Finding.severity == "critical", 1, 0)
                    ).label("critical"),
                    func.sum(
                        func.iif(Finding.severity == "high", 1, 0)
                    ).label("high"),
                    func.sum(
                        func.iif(Finding.severity == "medium", 1, 0)
                    ).label("medium"),
                    func.sum(
                        func.iif(Finding.severity == "low", 1, 0)
                    ).label("low"),
                )
                .where(Finding.first_detected_at >= cutoff)
                .group_by(text("1"))
                .order_by(text("1"))
            )

            if tenant_id:
                stmt = stmt.where(Finding.tenant_id == tenant_id)

            result = await self.session.execute(stmt)
            rows = result.fetchall()

            return [
                {
                    "date": str(row.day)[:10],  # normalise datetime/str to YYYY-MM-DD
                    "total": row.total or 0,
                    "critical": row.critical or 0,
                    "high": row.high or 0,
                    "medium": row.medium or 0,
                    "low": row.low or 0,
                }
                for row in rows
            ]
        except Exception:
            # DB not available or schema mismatch — return empty rather than 500
            return []


class AssessmentRunRepository(BaseRepository[AssessmentRun]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AssessmentRun, session)

    async def get_running_for_assessment(self, assessment_id: str) -> AssessmentRun | None:
        result = await self.session.execute(
            select(AssessmentRun).where(
                and_(
                    AssessmentRun.assessment_id == assessment_id,
                    AssessmentRun.status == AssessmentStatus.RUNNING.value,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_latest_runs(self, tenant_id: str, limit: int = 10) -> Sequence[AssessmentRun]:
        stmt = (
            select(AssessmentRun)
            .join(Assessment, AssessmentRun.assessment_id == Assessment.id)
            .where(Assessment.tenant_id == tenant_id)
            .order_by(AssessmentRun.started_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def mark_completed(
        self,
        run_id: str,
        *,
        security_score: float,
        compliance_score: float,
        risk_score: float,
        counts: dict,
    ) -> AssessmentRun:
        from datetime import datetime
        run = await self.get_or_raise(run_id)
        run.status = AssessmentStatus.COMPLETED.value
        run.completed_at = datetime.now(UTC)
        run.security_score = security_score
        run.compliance_score = compliance_score
        run.risk_score = risk_score
        run.critical_count = counts.get("critical", 0)
        run.high_count = counts.get("high", 0)
        run.medium_count = counts.get("medium", 0)
        run.low_count = counts.get("low", 0)
        run.informational_count = counts.get("informational", 0)
        run.total_controls_checked = counts.get("total", 0)
        run.controls_passed = counts.get("passed", 0)
        await self.session.flush()
        return run

    async def mark_failed(self, run_id: str, error_message: str) -> AssessmentRun:
        from datetime import datetime
        run = await self.get_or_raise(run_id)
        run.status = AssessmentStatus.FAILED.value
        run.completed_at = datetime.now(UTC)
        run.error_message = error_message
        await self.session.flush()
        return run
