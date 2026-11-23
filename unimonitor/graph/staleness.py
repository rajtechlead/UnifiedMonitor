"""Staleness of collected Graph evidence.

When Microsoft Graph cannot be reached, :class:`~unimonitor.graph.client.GraphClient`
answers from the last successful response. That data is usable, but it is not a
fresh measurement, so a control scored from it must not look like a current
evaluation.

The marker travels with the collected data itself: every key filled from a stale
response is listed under :data:`STALE_KEY`. The GRC engine then records the
overlap between a control's expected keys and that list as ``stale_data``
evidence on the finding.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

STALE_KEY = "_stale_keys"


def stale_keys(data: Mapping[str, Any] | None) -> set[str]:
    """The collected keys that came from a last-good response."""
    raw = (data or {}).get(STALE_KEY)
    if isinstance(raw, str):
        return {raw}
    return {str(key) for key in raw} if isinstance(raw, (list, tuple, set)) else set()


def mark_stale(data: dict[str, Any], keys: Iterable[str] | str) -> dict[str, Any]:
    """Record ``keys`` as stale in ``data`` and return it."""
    marked = stale_keys(data) | ({keys} if isinstance(keys, str) else {str(key) for key in keys})
    marked = {key for key in marked if key}
    if marked:
        data[STALE_KEY] = sorted(marked)
    return data


def merge_data(target: dict[str, Any], source: Mapping[str, Any] | None) -> dict[str, Any]:
    """Merge ``source`` into ``target``, unioning stale markers.

    A plain ``dict.update`` would replace the marker list with the last
    collector's, silently dropping the staleness of every other collector.
    """
    if not isinstance(source, dict):
        return target
    for key, value in source.items():
        if key != STALE_KEY:
            target[key] = value
    return mark_stale(target, stale_keys(source)) if stale_keys(source) else target


__all__ = ["STALE_KEY", "mark_stale", "merge_data", "stale_keys"]
