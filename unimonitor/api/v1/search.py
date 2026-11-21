"""Global search across findings, alerts and the control library."""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.auth.dependencies import get_current_user
from unimonitor.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter()


class SearchHit(BaseModel):
    kind: str  # "finding" | "alert" | "control"
    id: str
    title: str
    subtitle: str | None = None
    href: str
    severity: str | None = None


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]


@router.get("")
async def global_search(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str, Query(min_length=2, max_length=120)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> SearchResponse:
    """Search findings, alerts and controls by text; the UI adds static pages."""
    from unimonitor.db.models.alert import Alert
    from unimonitor.db.models.finding import Finding
    from unimonitor.grc.control_loader import ControlLoader

    pattern = f"%{q}%"
    hits: list[SearchHit] = []

    findings = (
        (
            await db.execute(
                select(Finding)
                .where(
                    or_(
                        Finding.title.ilike(pattern),
                        Finding.external_control_id.ilike(pattern),
                        Finding.description.ilike(pattern),
                    )
                )
                .order_by(Finding.last_seen_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    hits += [
        SearchHit(
            kind="finding",
            id=row.id,
            title=row.title,
            subtitle=f"{row.external_control_id} · {row.state.replace('_', ' ')}",
            href="/findings",
            severity=row.severity,
        )
        for row in findings
    ]

    alerts = (
        (
            await db.execute(
                select(Alert).where(or_(Alert.title.ilike(pattern), Alert.detail.ilike(pattern))).order_by(Alert.triggered_at.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    hits += [
        SearchHit(
            kind="alert",
            id=row.id,
            title=row.title,
            subtitle=row.status,
            href="/alerts",
            severity=row.severity,
        )
        for row in alerts
    ]

    needle = q.lower()
    for control in ControlLoader().load_all():
        if needle in control.id.lower() or needle in control.title.lower():
            hits.append(
                SearchHit(
                    kind="control",
                    id=control.id,
                    title=control.title,
                    subtitle=f"{control.id} · {control.category}",
                    href="/compliance",
                    severity=control.severity,
                )
            )
            if sum(1 for hit in hits if hit.kind == "control") >= limit:
                break

    return SearchResponse(query=q, hits=hits)
