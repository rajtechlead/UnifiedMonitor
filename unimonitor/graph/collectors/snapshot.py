"""Posture snapshot ingestion.

Some control areas have no Microsoft Graph endpoint at all (Copilot Studio
agents, Defender for Cloud Apps policies, Defender for Identity sensors,
Insider Risk policies, LAPS policy, app blocklists) and enterprise tenants often
already export them from PowerShell or a vendor API.

A JSON document supplied at ``UNIMONITOR_POSTURE_SNAPSHOT`` (a path) is merged
into the collected data, keyed exactly as the control YAML expects. Snapshot
values never override live collector data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from unimonitor.config import get_settings
from unimonitor.core.logging import get_logger

logger = get_logger(__name__)


def load_snapshot(path: str | Path | None = None) -> dict[str, Any]:
    """Read the posture snapshot, returning {} when unset or unreadable."""
    target = path or getattr(get_settings(), "UNIMONITOR_POSTURE_SNAPSHOT", "")
    if not target:
        return {}
    file = Path(str(target))
    if not file.is_file():
        logger.warning("Posture snapshot not found", path=str(file))
        return {}
    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Posture snapshot unreadable", path=str(file), error=str(exc))
        return {}
    if not isinstance(payload, dict):
        logger.warning("Posture snapshot must be a JSON object", path=str(file))
        return {}
    return payload


def merge_snapshot(collected: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Merge snapshot keys into collected data without overwriting live values."""
    merged = dict(snapshot)
    merged.update(collected)
    return merged
