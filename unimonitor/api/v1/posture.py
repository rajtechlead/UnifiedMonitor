"""Cloud posture analysis endpoints.

The engines are pure functions (see :mod:`unimonitor.posture`), so these routes
only resolve the snapshot, enforce access and cap the request size. Analysis is
read-only: nothing here writes to the database or to a cloud account.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from unimonitor.auth.dependencies import get_current_user, require_role
from unimonitor.graph.collectors.snapshot import load_snapshot
from unimonitor.posture.analysis import analyse, supported_platforms

logger = structlog.get_logger(__name__)
router = APIRouter()

# An inventory larger than this is almost certainly a wrong file (or an attempt
# to exhaust memory); the limit is documented rather than guessed at call time.
MAX_INVENTORY_BYTES = 8 * 1024 * 1024


def _analyse(platform: str | None, snapshot: Any) -> dict[str, Any]:
    encoded = len(json.dumps(snapshot, default=str).encode("utf-8"))
    if encoded > MAX_INVENTORY_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Inventory is {encoded} bytes; the limit is {MAX_INVENTORY_BYTES} bytes.",
        )
    try:
        return analyse(platform, snapshot)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid inventory: {exc}") from exc


@router.get("/platforms", responses={401: {"description": "Not authenticated"}})
async def list_platforms(
    current_user: Annotated[Any, Depends(get_current_user)],
) -> dict[str, Any]:
    """CIS packs this deployment can evaluate."""
    return {"platforms": supported_platforms()}


@router.get(
    "/analysis",
    responses={
        400: {"description": "Inventory could not be analysed"},
        401: {"description": "Not authenticated"},
        404: {"description": "No posture snapshot is configured or it cannot be read"},
        413: {"description": "Inventory is too large"},
    },
)
async def get_analysis(
    current_user: Annotated[Any, Depends(get_current_user)],
    platform: Annotated[str | None, Query(description="CIS pack to evaluate, e.g. aws")] = None,
) -> dict[str, Any]:
    """Analyse the configured snapshot, or the inventory the last run assembled.

    A configured ``UNIMONITOR_POSTURE_SNAPSHOT`` wins; otherwise the inventory
    written automatically after the most recent collection is used, so the engines
    run without an operator exporting anything.
    """
    snapshot = load_snapshot()
    source = "configured"
    if not snapshot:
        from unimonitor.posture.assemble import load_inventory

        snapshot = load_inventory() or {}
        source = "collected"
    if not snapshot:
        raise HTTPException(
            status_code=404,
            detail="No posture inventory is available yet. Run a collection, or set UNIMONITOR_POSTURE_SNAPSHOT in Settings.",
        )
    result = _analyse(platform, snapshot)
    result["source"] = source
    result["resources"] = len(snapshot.get("resources", [])) if isinstance(snapshot.get("resources"), list) else 0
    logger.info("posture_analysis", platform=platform, findings=len(result["findings"]), source=source, by=current_user.id)
    return result


@router.post(
    "/analyze",
    responses={
        400: {"description": "Inventory could not be analysed"},
        401: {"description": "Not authenticated"},
        413: {"description": "Inventory is too large"},
    },
)
async def analyze_inventory(
    body: dict[str, Any],
    current_user: Annotated[Any, Depends(require_role("analyst"))],
) -> dict[str, Any]:
    """Analyse an inventory posted by the caller (nothing is stored)."""
    snapshot = body.get("snapshot", body)
    platform = body.get("platform")
    if platform is not None and not isinstance(platform, str):
        raise HTTPException(status_code=400, detail="platform must be a string")
    result = _analyse(platform, snapshot)
    logger.info("posture_analysis_inline", platform=platform, findings=len(result["findings"]), by=current_user.id)
    return result


__all__ = ["router"]
