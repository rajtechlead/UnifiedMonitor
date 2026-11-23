"""Ticketing sync for Jira and ServiceNow.

A security finding that only lives in a dashboard does not get fixed. These
connectors create one ticket per finding, carrying the control, severity and
remediation so the assignee never has to open UniMonitor to act.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from unimonitor.config import get_settings
from unimonitor.core.logging import get_logger

logger = get_logger(__name__)

TIMEOUT_SECONDS = 15.0

# ServiceNow urgency/impact are 1 (high) to 3 (low).
_SERVICENOW_URGENCY = {"critical": "1", "high": "1", "medium": "2", "low": "3", "informational": "3"}


class TicketError(RuntimeError):
    """Ticketing is not configured, or the provider refused the ticket."""


@dataclass(frozen=True)
class TicketProvider:
    slug: str
    name: str
    env: tuple[str, ...]
    docs: str


PROVIDERS: dict[str, TicketProvider] = {
    "jira": TicketProvider(
        slug="jira",
        name="Jira Cloud",
        env=("JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_PROJECT_KEY"),
        docs="https://developer.atlassian.com/cloud/jira/platform/rest/v2/api-group-issues/",
    ),
    "servicenow": TicketProvider(
        slug="servicenow",
        name="ServiceNow",
        env=("SERVICENOW_URL", "SERVICENOW_USERNAME", "SERVICENOW_PASSWORD"),
        docs="https://docs.servicenow.com/bundle/utah-api/page/integrate/inbound-rest/concept/c_TableAPI.html",
    ),
    "webhook": TicketProvider(
        slug="webhook",
        name="Generic ticketing webhook",
        env=("TICKET_WEBHOOK_URL",),
        docs="",
    ),
}


def _settings_for(base: Any, config: dict[str, str] | None) -> Any:
    from unimonitor.integrations.siem import SettingsOverlay

    return SettingsOverlay(base, config)


def _missing_settings(provider: TicketProvider, settings: Any) -> list[str]:
    return [name for name in provider.env if not str(getattr(settings, name, "") or "").strip()]


def ticketing_status(configs: dict[str, dict[str, str]] | None = None) -> list[dict[str, Any]]:
    """Every provider with whether it is configured and what it still needs."""
    base = get_settings()
    managed = configs or {}
    rows = []
    for provider in PROVIDERS.values():
        settings = _settings_for(base, managed.get(provider.slug))
        missing = _missing_settings(provider, settings)
        rows.append(
            {
                "slug": provider.slug,
                "name": provider.name,
                "docs": provider.docs,
                "configured": not missing,
                "managed": provider.slug in managed,
                "required_settings": list(provider.env),
                "missing_settings": missing,
            }
        )
    return rows


def default_provider(configs: dict[str, dict[str, str]] | None = None) -> str | None:
    """The first configured provider, in a stable order."""
    configured = {row["slug"] for row in ticketing_status(configs) if row["configured"]}
    for slug in ("jira", "servicenow", "webhook"):
        if slug in configured:
            return slug
    return None


def _summary(finding: Any) -> str:
    return f"[UniMonitor] {finding.severity.upper()} {finding.external_control_id}: {finding.title}"[:250]


def _description(finding: Any) -> str:
    parts = [
        f"Control: {finding.external_control_id}",
        f"Severity: {finding.severity}",
        f"State: {finding.state}",
        f"Category: {finding.category}",
        f"Service: {finding.service}",
        f"Risk score: {finding.risk_score}",
        f"First detected: {finding.first_detected_at.isoformat() if finding.first_detected_at else 'unknown'}",
        "",
        finding.description or "",
    ]
    remediation = getattr(finding, "remediation", "") or ""
    if remediation:
        parts += ["", "Remediation:", remediation]
    return "\n".join(parts)


async def create_ticket(finding: Any, provider: str | None = None, config: dict[str, str] | None = None) -> dict[str, Any]:
    """Create one ticket for *finding*; returns provider, key and URL."""
    slug = provider or default_provider()
    if slug is None:
        raise TicketError("No ticketing provider is configured: connect one in Settings or set Jira, ServiceNow or TICKET_WEBHOOK_URL")
    definition = PROVIDERS.get(slug)
    if definition is None:
        raise TicketError(f"Unknown ticketing provider '{slug}'")

    settings = _settings_for(get_settings(), config)
    missing = _missing_settings(definition, settings)
    if missing:
        raise TicketError(f"{definition.name} is not configured: set {', '.join(missing)}")

    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        if slug == "jira":
            return await _create_jira(client, settings, finding, definition)
        if slug == "servicenow":
            return await _create_servicenow(client, settings, finding, definition)
        return await _create_webhook(client, settings, finding, definition)


async def _create_jira(client: httpx.AsyncClient, settings: Any, finding: Any, definition: TicketProvider) -> dict[str, Any]:
    """POST one issue to Jira and normalise the response."""
    response = await client.post(
        f"{settings.JIRA_URL.rstrip('/')}/rest/api/2/issue",
        auth=(settings.JIRA_EMAIL, settings.JIRA_API_TOKEN),
        json={
            "fields": {
                "project": {"key": settings.JIRA_PROJECT_KEY},
                "issuetype": {"name": "Task"},
                "summary": _summary(finding),
                "description": _description(finding),
                "labels": ["unimonitor", finding.severity.lower()],
            }
        },
    )
    _raise_for(response, definition)
    body = response.json()
    key = str(body.get("key", ""))
    return {"provider": definition.slug, "external_id": key, "url": f"{settings.JIRA_URL.rstrip('/')}/browse/{key}" if key else ""}


async def _create_servicenow(client: httpx.AsyncClient, settings: Any, finding: Any, definition: TicketProvider) -> dict[str, Any]:
    """POST one incident to ServiceNow and normalise the response."""
    response = await client.post(
        f"{settings.SERVICENOW_URL.rstrip('/')}/api/now/table/{settings.SERVICENOW_TABLE}",
        auth=(settings.SERVICENOW_USERNAME, settings.SERVICENOW_PASSWORD),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json={
            "short_description": _summary(finding),
            "description": _description(finding),
            "category": "security",
            "urgency": _SERVICENOW_URGENCY.get(finding.severity, "2"),
            "impact": _SERVICENOW_URGENCY.get(finding.severity, "2"),
            "correlation_id": finding.id,
        },
    )
    _raise_for(response, definition)
    record = (response.json() or {}).get("result", {})
    sys_id = str(record.get("sys_id", ""))
    number = str(record.get("number", sys_id))
    return {
        "provider": definition.slug,
        "external_id": number,
        "url": f"{settings.SERVICENOW_URL.rstrip('/')}/nav_to.do?uri=incident.do?sys_id={sys_id}" if sys_id else "",
    }


async def _create_webhook(client: httpx.AsyncClient, settings: Any, finding: Any, definition: TicketProvider) -> dict[str, Any]:
    """POST the generic webhook payload any other tracker can ingest."""
    response = await client.post(
        settings.TICKET_WEBHOOK_URL,
        json={
            "source": "unimonitor",
            "finding_id": finding.id,
            "tenant_id": finding.tenant_id,
            "control": finding.external_control_id,
            "title": finding.title,
            "severity": finding.severity,
            "state": finding.state,
            "description": _description(finding),
        },
    )
    _raise_for(response, definition)
    external_id = ""
    try:
        external_id = str((response.json() or {}).get("key") or (response.json() or {}).get("id") or "")
    except ValueError:
        external_id = ""
    return {"provider": definition.slug, "external_id": external_id, "url": ""}


def _raise_for(response: httpx.Response, definition: TicketProvider) -> None:
    if response.status_code >= 400:
        detail = response.text[:300]
        logger.warning("ticket_create_failed", provider=definition.slug, status=response.status_code, detail=detail)
        raise TicketError(f"{definition.name} rejected the ticket ({response.status_code}): {detail}")
