"""Control-level trend series built from immutable control snapshots.

A finding tells you the current state; these series tell you whether a control is
getting better or worse, and how often it flips. Only snapshots inside the window
are considered, and a control with one data point is reported with an explicit
``insufficient_history`` flag instead of a manufactured trend.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from unimonitor.db.models.control_snapshot import ControlSnapshot

OPEN_STATES = {"not_implemented", "partially_implemented"}


def _series(rows: list[tuple[str, datetime, str]]) -> dict[str, Any]:
    """Build one control's series from ``(control_id, checked_at, state)`` rows."""
    points = [{"at": checked_at.isoformat(), "state": state} for control_id, checked_at, state in rows]
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


async def control_trend(session: Any, tenant_id: str | None, control_id: str, days: int = 90) -> dict[str, Any]:
    """State series for one control."""
    since = datetime.now(UTC) - timedelta(days=days)
    stmt = select(ControlSnapshot.control_id, ControlSnapshot.checked_at, ControlSnapshot.state).where(
        ControlSnapshot.control_id == control_id,
        ControlSnapshot.checked_at >= since,
    )
    if tenant_id:
        stmt = stmt.where(ControlSnapshot.tenant_id == tenant_id)
    rows = [(row[0], row[1], row[2]) for row in (await session.execute(stmt.order_by(ControlSnapshot.checked_at))).all()]
    return {"control_id": control_id, "window_days": days, **_series(rows)}


async def control_trends(
    session: Any,
    tenant_id: str | None,
    days: int = 30,
    limit: int = 100,
    *,
    only_changed: bool = False,
) -> dict[str, Any]:
    """State series for the controls seen in the window, newest activity first."""
    since = datetime.now(UTC) - timedelta(days=days)
    stmt = select(ControlSnapshot.control_id, ControlSnapshot.checked_at, ControlSnapshot.state).where(ControlSnapshot.checked_at >= since)
    if tenant_id:
        stmt = stmt.where(ControlSnapshot.tenant_id == tenant_id)
    rows = (await session.execute(stmt.order_by(ControlSnapshot.checked_at))).all()

    grouped: dict[str, list[tuple[str, datetime, str]]] = {}
    for control_id, checked_at, state in rows:
        grouped.setdefault(str(control_id), []).append((str(control_id), checked_at, state))

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


__all__ = ["control_trend", "control_trends"]
