"""Remediation metrics — mean time to remediate and open SLA breaches.

The dashboards already show what is open. These metrics answer the question a
board asks next: how long do we take to fix things, and which severities are
drifting past the target window.

SLA targets are deliberately policy, not fact: change ``SLA_HOURS`` to match the
organisation's own commitment, and the numbers stay honest either way because
every response carries the targets it used.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

# Hours allowed before a finding of each severity counts as past its target.
# ``None`` means no target is set, so the severity is reported but never breached.
SLA_HOURS: dict[str, int | None] = {
    "critical": 24 * 7,
    "high": 24 * 30,
    "medium": 24 * 90,
    "low": 24 * 180,
    "informational": None,
}

SEVERITY_ORDER = ("critical", "high", "medium", "low", "informational")
OPEN_STATES = ("not_implemented", "partially_implemented")


def _utc(value: datetime) -> datetime:
    """Treat a naive timestamp (SQLite) as UTC so arithmetic never mixes them."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile; small samples keep their actual values."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return round(ordered[index], 2)


def _mttr_entry(severity: str, hours: list[float]) -> dict[str, Any]:
    """Mean/median/p90 time to remediate one severity, null when nothing resolved."""
    return {
        "severity": severity,
        "resolved": len(hours),
        "mean_hours": round(sum(hours) / len(hours), 2) if hours else None,
        "median_hours": round(median(hours), 2) if hours else None,
        "p90_hours": _percentile(hours, 0.9) if hours else None,
        "sla_hours": SLA_HOURS.get(severity),
    }


def _sla_entry(severity: str, ages: list[float], target: float | None) -> dict[str, Any]:
    """Open findings for one severity, and how many are past its SLA."""
    breached = 0 if target is None else sum(1 for age in ages if age > target)
    return {
        "severity": severity,
        "open": len(ages),
        "breached": breached,
        "sla_hours": target,
        "oldest_hours": round(max(ages), 2) if ages else None,
    }


def summarise_remediation(
    resolved: list[tuple[str, datetime, datetime]],
    open_findings: list[tuple[str, datetime]],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compute MTTR per severity and count open findings past their SLA.

    *resolved* is ``(severity, first_detected_at, resolved_at)`` rows fixed within
    the reporting window; *open_findings* is ``(severity, first_detected_at)`` for
    everything still open. Findings with a negative age (clock skew on a remote
    collector) are clamped at zero rather than skewing the mean.
    """
    now = now or datetime.now(UTC)

    buckets: dict[str, list[float]] = {severity: [] for severity in SEVERITY_ORDER}
    for severity, first_seen, resolved_at in resolved:
        key = (severity or "").lower()
        if key not in buckets:
            continue
        hours = max(0.0, (_utc(resolved_at) - _utc(first_seen)).total_seconds() / 3600)
        buckets[key].append(hours)

    mttr = [_mttr_entry(severity, buckets[severity]) for severity in SEVERITY_ORDER]

    breaches = []
    for severity in SEVERITY_ORDER:
        target = SLA_HOURS.get(severity)
        ages = [
            max(0.0, (_utc(now) - _utc(first_seen)).total_seconds() / 3600)
            for row_severity, first_seen in open_findings
            if (row_severity or "").lower() == severity
        ]
        breaches.append(_sla_entry(severity, ages, target))

    return {"mttr": mttr, "open_sla": breaches}


async def remediation_metrics(session: Any, tenant_id: str | None = None, window_days: int = 90) -> dict[str, Any]:
    """Load the rows :func:`summarise_remediation` needs and summarise them."""
    from sqlalchemy import select

    from unimonitor.db.models.finding import Finding

    since = datetime.now(UTC) - timedelta(days=window_days)

    resolved_stmt = select(Finding.severity, Finding.first_detected_at, Finding.resolved_at).where(
        Finding.resolved_at.is_not(None),
        Finding.resolved_at >= since,
        Finding.first_detected_at.is_not(None),
    )
    if tenant_id:
        resolved_stmt = resolved_stmt.where(Finding.tenant_id == tenant_id)
    resolved_rows = [(row[0], row[1], row[2]) for row in (await session.execute(resolved_stmt)).all() if row[1] is not None and row[2] is not None]

    open_stmt = select(Finding.severity, Finding.first_detected_at).where(
        Finding.state.in_(OPEN_STATES),
        Finding.is_suppressed.is_(False),
        Finding.first_detected_at.is_not(None),
    )
    if tenant_id:
        open_stmt = open_stmt.where(Finding.tenant_id == tenant_id)
    open_rows = [(row[0], row[1]) for row in (await session.execute(open_stmt)).all() if row[1] is not None]

    result = summarise_remediation(resolved_rows, open_rows)
    result["window_days"] = window_days
    return result
