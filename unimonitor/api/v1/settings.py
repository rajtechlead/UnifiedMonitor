"""Deployment settings that are safe to edit from the UI.

The posture snapshot is a JSON document merged into collected data for keys that
no Graph endpoint exposes. Its path is deployment configuration
(``UNIMONITOR_POSTURE_SNAPSHOT``); this endpoint lets an administrator maintain
the document without shell access, and refuses to create a path that was not
configured.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from unimonitor.auth.dependencies import require_role
from unimonitor.config import get_settings
from unimonitor.graph.collectors.snapshot import load_snapshot

logger = structlog.get_logger(__name__)
router = APIRouter()

MAX_SNAPSHOT_BYTES = 256 * 1024


class PostureSnapshotResponse(BaseModel):
    configured: bool
    path: str
    snapshot: dict[str, Any]


def _snapshot_path() -> Path | None:
    configured = str(getattr(get_settings(), "UNIMONITOR_POSTURE_SNAPSHOT", "") or "")
    return Path(configured) if configured else None


@router.get("/posture-snapshot")
async def get_posture_snapshot(
    current_user: Annotated[Any, Depends(require_role("admin"))],
) -> PostureSnapshotResponse:
    """Read the configured posture snapshot (empty when the path is unset)."""
    path = _snapshot_path()
    return PostureSnapshotResponse(
        configured=path is not None,
        path=str(path) if path else "",
        snapshot=load_snapshot(path),
    )


@router.put("/posture-snapshot")
async def put_posture_snapshot(
    body: dict[str, Any],
    current_user: Annotated[Any, Depends(require_role("admin"))],
) -> PostureSnapshotResponse:
    """Replace the posture snapshot document atomically."""
    path = _snapshot_path()
    if path is None:
        raise HTTPException(
            status_code=409,
            detail="UNIMONITOR_POSTURE_SNAPSHOT is not configured; set it to a writable path first.",
        )
    encoded = json.dumps(body, indent=2, sort_keys=True)
    if len(encoded.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        raise HTTPException(status_code=413, detail=f"Posture snapshot exceeds {MAX_SNAPSHOT_BYTES} bytes")

    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(encoded, encoding="utf-8")
        temporary.replace(path)
    except OSError as exc:
        logger.warning("posture_snapshot_write_failed", path=str(path), error=str(exc))
        raise HTTPException(status_code=500, detail="Could not write the posture snapshot") from exc

    logger.info("posture_snapshot_updated", path=str(path), by=current_user.id, keys=len(body))
    return PostureSnapshotResponse(configured=True, path=str(path), snapshot=load_snapshot(path))
