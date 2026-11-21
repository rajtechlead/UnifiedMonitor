"""Control-level trend series built from immutable control snapshots.

A finding tells you the current state; these series tell you whether a control is
getting better or worse, and how often it flips. Only snapshots inside the window
are considered, and a control with one data point is reported with an explicit
``insufficient_history`` flag instead of a manufactured trend.

Snapshots are pruned on write (see :func:`prune_control_snapshots`) because a
15-minute collection schedule over a few hundred controls appends thousands of
rows a day; without a retention window the table would grow without bound.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.db.models.control_snapshot import ControlSnapshot

OPEN_STATES = {"not_implemented", "partially_implemented"}

SnapshotRow = tuple[str, datetime, str]


def _series(rows: list[SnapshotRow]) -> dict[str, Any]:
    """Build one control's series from ``(control_id, checked_at, state)`` rows."""
    points = [{"at": checked_at.isoformat(), "state": state} for _, checked_at, state in rows]
    transitions = sum(1 for previous, current in zip(points, points[1:], strict=False) if previous["state"] != current["state"])
    latest = points[-1]["state"] if points else None
    first = points[0]["state"] if points else None
    return {
        "points": points,
        "observations": len(points),
        "transitions": transitions,
        "current_state": latest,
        "first_state": first,
        "insufficient_history": len(points) < 2,
        "improving": (first in OPEN_STATES and latest not in OPEN_STATES) if first and latest else None,
    }


async def _rows(
    session: AsyncSession,
    tenant_id: str | None,
    days: int,
    control_id: str | None = None,
) -> list[SnapshotRow]:
    """Snapshots inside the window, oldest first."""
    stmt = select(ControlSnapshot.control_id, ControlSnapshot.checked_at, ControlSnapshot.state).where(
        ControlSnapshot.checked_at >= datetime.now(UTC) - timedelta(days=days)
    )
    if tenant_id:
        stmt = stmt.where(ControlSnapshot.tenant_id == tenant_id)
    if control_id:
        stmt = stmt.where(ControlSnapshot.control_id == control_id)
    rows = (await session.execute(stmt.order_by(ControlSnapshot.checked_at))).all()
    return [(str(row[0]), row[1], row[2]) for row in rows]


async def control_trend(session: AsyncSession, tenant_id: str | None, control_id: str, days: int = 90) -> dict[str, Any]:
    """State series for one control."""
    return {"control_id": control_id, "window_days": days, **_series(await _rows(session, tenant_id, days, control_id))}


async def control_trends(
    session: AsyncSession,
    tenant_id: str | None,
    days: int = 30,
    limit: int = 100,
    *,
    only_changed: bool = False,
) -> dict[str, Any]:
    """State series for the controls seen in the window, newest activity first."""
    rows = await _rows(session, tenant_id, days)

    grouped: dict[str, list[SnapshotRow]] = {}
    for row in rows:
        grouped.setdefault(row[0], []).append(row)

    items = [{"control_id": control_id, **_series(series)} for control_id, series in grouped.items()]
    if only_changed:
        items = [item for item in items if item["transitions"] > 0]
    items.sort(key=lambda item: item["points"][-1]["at"] if item["points"] else "", reverse=True)
    return {
        "window_days": days,
        "controls": len(grouped),
        "total_points": len(rows),
        "items": items[:limit],
    }


async def prune_control_snapshots(session: AsyncSession, tenant_id: str | None, retention_days: int) -> int:
    """Delete snapshots older than *retention_days* and return how many went.

    ``0`` (or a negative value) disables pruning, which is the documented escape
    hatch for an operator who wants the full history. The delete is scoped to one
    tenant when *tenant_id* is given so one tenant's policy cannot remove another
    tenant's history.
    """
    if retention_days <= 0:
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    stmt = delete(ControlSnapshot).where(ControlSnapshot.checked_at < cutoff)
    if tenant_id:
        stmt = stmt.where(ControlSnapshot.tenant_id == tenant_id)
    result = await session.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)


__all__ = ["control_trend", "control_trends", "prune_control_snapshots"]
