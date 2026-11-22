"""Whether a control's state is actually evidenced.

Three different situations used to look identical in the API: a control that was
evaluated and passed, a control whose last evidence is too old to trust, and a control
no collector has ever produced a result for. Scores and dashboards treated all three as
"not failing", so a framework could look clean simply because nothing had been measured.

A control is:

* ``evaluated`` — measured within ``EVIDENCE_STALE_DAYS``;
* ``stale`` — measured, but not recently enough to support a current claim;
* ``never_evaluated`` — no result exists at all.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

EVALUATED = "evaluated"
STALE = "stale"
NEVER_EVALUATED = "never_evaluated"


@dataclass(frozen=True)
class EvidenceStatus:
    status: str
    evaluated_at: datetime | None
    source_run_id: str | None
    age_days: float | None

    @property
    def counts_towards_score(self) -> bool:
        """Only evidence that is current may support a compliance claim."""
        return self.status == EVALUATED


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def classify(
    evaluated_at: datetime | None,
    *,
    source_run_id: str | None = None,
    now: datetime | None = None,
    stale_after_days: int = 7,
) -> EvidenceStatus:
    """Classify one control's evidence."""
    moment = _as_utc(evaluated_at)
    if moment is None:
        return EvidenceStatus(NEVER_EVALUATED, None, source_run_id, None)

    reference = _as_utc(now) or datetime.now(UTC)
    age_days = max(0.0, (reference - moment).total_seconds() / 86400)
    status = STALE if age_days > stale_after_days else EVALUATED
    return EvidenceStatus(status, moment, source_run_id, round(age_days, 2))


def summarise(statuses: Iterable[EvidenceStatus]) -> dict[str, int | float]:
    """Counts and coverage for a set of controls.

    ``coverage_pct`` is the share with current evidence — the number that says how much
    of a framework's score rests on measurements rather than on absence of findings.
    """
    items = list(statuses)
    counts = {
        EVALUATED: sum(1 for item in items if item.status == EVALUATED),
        STALE: sum(1 for item in items if item.status == STALE),
        NEVER_EVALUATED: sum(1 for item in items if item.status == NEVER_EVALUATED),
    }
    total = len(items)
    return {
        "total_controls": total,
        **counts,
        "coverage_pct": round(counts[EVALUATED] * 100 / total, 1) if total else 0.0,
    }


__all__ = [
    "EVALUATED",
    "NEVER_EVALUATED",
    "STALE",
    "EvidenceStatus",
    "classify",
    "summarise",
]
