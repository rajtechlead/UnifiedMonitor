"""Outbound integration endpoints — SIEM connectors and ticketing sync.

A connector is configured either from the product (its settings are written to the
secret vault, never to a database row and never returned in a response) or from the
deployment environment, which remains the fallback for existing installs. These
endpoints report which connectors are wired up, connect/disconnect one, test one,
push the current open findings to one, and open tickets for findings without one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from unimonitor.auth.dependencies import require_role
from unimonitor.db.session import get_db
from unimonitor.integrations.siem import connector_status, send_events
from unimonitor.integrations.siem import test_connector as run_connector_test
from unimonitor.integrations.ticketing import create_ticket, default_provider, ticketing_status

logger = structlog.get_logger(__name__)
router = APIRouter()


class SiemConnectorRow(BaseModel):
    slug: str
    name: str
    description: str
    docs: str
    configured: bool
    managed: bool = False
    required_settings: list[str]
    missing_settings: list[str]


class TicketingRow(BaseModel):
    slug: str
    name: str
    docs: str
    configured: bool
    managed: bool = False
    required_settings: list[str]
    missing_settings: list[str]


class ConnectorConfigIn(BaseModel):
    """Settings entered in the UI; written to the vault, never returned."""

    values: dict[str, str] = Field(default_factory=dict, max_length=20)


class ConnectorConfigResponse(BaseModel):
    kind: str
    provider: str
    stored: list[str]
    configured: bool


class IntegrationsResponse(BaseModel):
    siem: list[SiemConnectorRow]
    ticketing: list[TicketingRow]
    default_ticketing_provider: str | None


class SendRequest(BaseModel):
    tenant_id: str | None = None
    severity: str | None = None
    limit: int = Field(default=200, ge=1, le=2000)


class SendResponse(BaseModel):
    provider: str
    sent: int
    status_code: int | None = None
    test: bool = False


class TicketSyncRequest(BaseModel):
    provider: str | None = None
    finding_ids: list[str] | None = None
    min_severity: str = Field(default="high")
    limit: int = Field(default=25, ge=1, le=200)


class TicketSyncItem(BaseModel):
    finding_id: str
    control: str
    title: str
    ticket: str
    url: str


class TicketSyncResponse(BaseModel):
    provider: str | None
    created: int
    skipped: int
    errors: int
    tickets: list[TicketSyncItem]
    generated_at: datetime


SEVERITY_ORDER = ["informational", "low", "medium", "high", "critical"]


@router.get("")
async def list_integrations(
    current_user: Annotated[Any, Depends(require_role("admin"))],
) -> IntegrationsResponse:
    """Which connectors are configured, and what each one still needs."""
    from unimonitor.integrations.credentials import load_all

    siem_configs = await load_all("siem")
    ticketing_configs = await load_all("ticketing")
    return IntegrationsResponse(
        siem=[SiemConnectorRow(**row) for row in connector_status(siem_configs)],
        ticketing=[TicketingRow(**row) for row in ticketing_status(ticketing_configs)],
        default_ticketing_provider=default_provider(ticketing_configs),
    )


def _connector_kind(kind: str) -> str:
    if kind not in ("siem", "ticketing"):
        raise HTTPException(status_code=404, detail=f"Unknown connector kind '{kind}'")
    return kind


@router.put("/{kind}/{provider}/config", responses={400: {"description": "Bad request"}, 404: {"description": "Not found"}})
async def save_connector_config(
    kind: str,
    provider: str,
    body: ConnectorConfigIn,
    current_user: Annotated[Any, Depends(require_role("admin"))],
) -> ConnectorConfigResponse:
    """Connect a SIEM or ticketing provider by storing its settings in the vault."""
    from unimonitor.integrations.credentials import ConnectorConfigError, load, save

    kind = _connector_kind(kind)
    try:
        stored = await save(kind, provider, body.values)
    except ConnectorConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("connector_connected", kind=kind, provider=provider, fields=stored, by=current_user.id)
    config = await load(kind, provider) or {}
    return ConnectorConfigResponse(kind=kind, provider=provider, stored=stored, configured=bool(config))


@router.delete("/{kind}/{provider}/config", responses={404: {"description": "Not found"}})
async def delete_connector_config(
    kind: str,
    provider: str,
    current_user: Annotated[Any, Depends(require_role("admin"))],
) -> dict[str, Any]:
    """Disconnect a provider and fall back to its deployment environment, if any."""
    from unimonitor.integrations.credentials import ConnectorConfigError, delete

    kind = _connector_kind(kind)
    try:
        await delete(kind, provider)
    except ConnectorConfigError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    logger.info("connector_disconnected", kind=kind, provider=provider, by=current_user.id)
    return {"kind": kind, "provider": provider, "disconnected": True}


async def _open_findings(db: Any, tenant_id: str | None, severity: str | None, limit: int) -> list[Any]:
    from sqlalchemy import select

    from unimonitor.db.models.finding import Finding

    stmt = select(Finding).where(
        Finding.is_suppressed.is_(False),
        Finding.state.in_(["not_implemented", "partially_implemented"]),
    )
    if tenant_id:
        stmt = stmt.where(Finding.tenant_id == tenant_id)
    if severity:
        stmt = stmt.where(Finding.severity == severity.lower())
    stmt = stmt.order_by(Finding.risk_score.desc(), Finding.last_seen_at.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


@router.post("/siem/{provider}/test", responses={400: {"description": "Bad request"}, 404: {"description": "Unknown connector"}})
async def test_siem_connector(
    provider: str,
    current_user: Annotated[Any, Depends(require_role("admin"))],
) -> SendResponse:
    """Send one synthetic event so the wiring can be verified immediately."""
    from unimonitor.integrations.credentials import ConnectorConfigError, load
    from unimonitor.integrations.siem import IntegrationError

    try:
        receipt = await run_connector_test(provider, await load("siem", provider))
    except ConnectorConfigError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SendResponse(**receipt)


@router.post("/siem/{provider}/send", responses={404: {"description": "Unknown connector"}, 502: {"description": "Upstream failure"}})
async def push_to_siem(
    provider: str,
    body: SendRequest,
    current_user: Annotated[Any, Depends(require_role("admin"))],
    db: Annotated[Any, Depends(get_db)],
) -> SendResponse:
    """Push the current open findings to one SIEM connector."""
    from unimonitor.integrations.credentials import ConnectorConfigError, load
    from unimonitor.integrations.events import finding_event
    from unimonitor.integrations.siem import IntegrationError

    findings = await _open_findings(db, body.tenant_id, body.severity, body.limit)
    try:
        receipt = await send_events(provider, [finding_event(finding) for finding in findings], await load("siem", provider))
    except ConnectorConfigError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    logger.info("siem_pushed", provider=provider, sent=receipt.get("sent", 0), by=current_user.id)
    return SendResponse(**receipt)


@router.post("/ticketing/sync", responses={400: {"description": "Bad request"}})
async def sync_tickets(
    body: TicketSyncRequest,
    current_user: Annotated[Any, Depends(require_role("admin"))],
    db: Annotated[Any, Depends(get_db)],
) -> TicketSyncResponse:
    """Open a ticket for every open finding that does not have one yet.

    Idempotent: findings already linked to a ticket for the chosen provider are
    skipped, so a repeated sync never produces duplicates.
    """
    from sqlalchemy import select

    from unimonitor.db.models.external_ticket import ExternalTicket
    from unimonitor.integrations.credentials import load_all
    from unimonitor.integrations.ticketing import TicketError

    ticketing_configs = await load_all("ticketing")
    provider = body.provider or default_provider(ticketing_configs)
    if provider is None:
        raise HTTPException(status_code=400, detail="No ticketing provider is configured")
    if body.min_severity.lower() not in SEVERITY_ORDER:
        raise HTTPException(status_code=400, detail=f"Invalid severity '{body.min_severity}'")

    findings = await _open_findings(db, None, None, body.limit * 4)
    minimum = SEVERITY_ORDER.index(body.min_severity.lower())
    wanted = set(body.finding_ids or [])
    candidates = [
        finding for finding in findings if SEVERITY_ORDER.index(finding.severity.lower()) >= minimum and (not wanted or finding.id in wanted)
    ][: body.limit]

    existing = {row.finding_id for row in (await db.execute(select(ExternalTicket).where(ExternalTicket.provider == provider))).scalars()}

    created: list[TicketSyncItem] = []
    skipped = 0
    errors = 0
    for finding in candidates:
        if finding.id in existing:
            skipped += 1
            continue
        try:
            result = await create_ticket(finding, provider, ticketing_configs.get(provider))
        except TicketError as exc:
            logger.warning("ticket_sync_error", finding_id=finding.id, error=str(exc)[:200])
            errors += 1
            continue
        db.add(
            ExternalTicket(
                finding_id=finding.id,
                provider=provider,
                external_id=str(result.get("external_id", "")),
                url=str(result.get("url", "")),
            )
        )
        created.append(
            TicketSyncItem(
                finding_id=finding.id,
                control=finding.external_control_id,
                title=finding.title,
                ticket=str(result.get("external_id", "")),
                url=str(result.get("url", "")),
            )
        )

    await db.flush()
    logger.info("ticket_sync", provider=provider, created=len(created), skipped=skipped, errors=errors, by=current_user.id)
    return TicketSyncResponse(
        provider=provider,
        created=len(created),
        skipped=skipped,
        errors=errors,
        tickets=created,
        generated_at=datetime.now(UTC),
    )
