"""Plug-and-play SIEM connectors.

Each connector is a thin, documented mapping from a UniMonitor finding event to
the platform's own ingest API. A connector is "configured" when all of its
credential settings are present; there is no hidden default endpoint, and
nothing is sent unless an administrator asks for it.

Coarse but honest coverage: the named connectors below are the common
commercial SIEM log-intake APIs. Anything else (QRadar, ArcSight, Exabeam,
Securonix, Sentinel via syslog, …) is supported twice over — through the generic
``webhook`` connector, which posts CEF/JSON to any HTTP collector, and through
the ``syslog`` connector, which sends CEF over UDP.
"""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import Any

import httpx

from unimonitor.config import get_settings
from unimonitor.core.logging import get_logger
from unimonitor.integrations.events import finding_cef, finding_event

logger = get_logger(__name__)

JSON_CONTENT_TYPE = "application/json"
TIMEOUT_SECONDS = 10.0


class IntegrationError(RuntimeError):
    """A connector is not configured, or the remote endpoint refused the batch."""


@dataclass(frozen=True)
class Connector:
    slug: str
    name: str
    transport: str  # datadog | splunk | elastic | sentinel | ndjson | json | webhook | syslog
    env: tuple[str, ...]
    docs: str
    description: str


CONNECTORS: dict[str, Connector] = {
    "datadog": Connector(
        slug="datadog",
        name="Datadog Logs",
        transport="datadog",
        env=("DATADOG_API_KEY",),
        docs="https://docs.datadoghq.com/api/latest/logs/",
        description="Posts findings to the Datadog Logs intake (ddsource=unimonitor).",
    ),
    "splunk": Connector(
        slug="splunk",
        name="Splunk HTTP Event Collector",
        transport="splunk",
        env=("SPLUNK_HEC_URL", "SPLUNK_HEC_TOKEN"),
        docs="https://docs.splunk.com/Documentation/Splunk/latest/Data/UsetheHTTPEventCollector",
        description="Sends one HEC event per finding, sourcetype unimonitor:finding.",
    ),
    "elastic": Connector(
        slug="elastic",
        name="Elasticsearch / Elastic Security",
        transport="elastic",
        env=("ELASTIC_URL", "ELASTIC_API_KEY"),
        docs="https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-bulk.html",
        description="Bulk-indexes findings into the configured index.",
    ),
    "microsoft_sentinel": Connector(
        slug="microsoft_sentinel",
        name="Microsoft Sentinel",
        transport="sentinel",
        env=(
            "AZURE_SENTINEL_DCR_ENDPOINT",
            "AZURE_SENTINEL_DCR_RULE_ID",
            "AZURE_SENTINEL_STREAM",
            "AZURE_SENTINEL_ACCESS_TOKEN",
        ),
        docs="https://learn.microsoft.com/azure/azure-monitor/logs/logs-ingestion-api-overview",
        description="Sends findings through the Logs Ingestion API to a DCR stream.",
    ),
    "sumologic": Connector(
        slug="sumologic",
        name="Sumo Logic HTTP Source",
        transport="ndjson",
        env=("SUMOLOGIC_HTTP_URL",),
        docs="https://help.sumologic.com/docs/send-data/hosted-collectors/http-source/logs-metrics/",
        description="Posts newline-delimited JSON to a Sumo Logic HTTP source.",
    ),
    "chronicle": Connector(
        slug="chronicle",
        name="Google Security Operations (Chronicle)",
        transport="json",
        env=("CHRONICLE_INGEST_URL", "CHRONICLE_AUTH_TOKEN"),
        docs="https://cloud.google.com/chronicle/docs/ingestion",
        description="Posts findings to a Chronicle ingestion endpoint with a bearer token.",
    ),
    "wazuh": Connector(
        slug="wazuh",
        name="Wazuh (http-request)",
        transport="ndjson",
        env=("WAZUH_INGEST_URL",),
        docs="https://documentation.wazuh.com/current/user-manual/capabilities/wodle-command/http-request.html",
        description="Posts newline-delimited JSON to a Wazuh http-request listener.",
    ),
    "webhook": Connector(
        slug="webhook",
        name="Generic webhook (CEF or JSON)",
        transport="webhook",
        env=("SIEM_WEBHOOK_URL",),
        docs="",
        description="Posts a JSON batch to any HTTP collector; covers QRadar, ArcSight, Exabeam and in-house pipelines.",
    ),
    "syslog": Connector(
        slug="syslog",
        name="Syslog (CEF over UDP)",
        transport="syslog",
        env=("SIEM_SYSLOG_HOST",),
        docs="",
        description="Sends CEF lines over UDP syslog, which most SIEM collectors already accept.",
    ),
}


class SettingsOverlay:
    """Environment settings with vault-stored connector values taking precedence."""

    def __init__(self, base: Any, overrides: dict[str, str] | None = None) -> None:
        self._base = base
        self._overrides = dict(overrides or {})

    def __getattr__(self, name: str) -> Any:
        overrides = object.__getattribute__(self, "_overrides")
        if name in overrides:
            return overrides[name]
        return getattr(object.__getattribute__(self, "_base"), name, "")


def get_connector(slug: str) -> Connector:
    connector = CONNECTORS.get(slug)
    if connector is None:
        raise IntegrationError(f"Unknown SIEM connector '{slug}'")
    return connector


def _missing_settings(connector: Connector, settings: Any) -> list[str]:
    return [name for name in connector.env if not str(getattr(settings, name, "") or "").strip()]


def connector_status(configs: dict[str, dict[str, str]] | None = None) -> list[dict[str, Any]]:
    """Every connector with whether it is configured and what it still needs.

    ``configs`` carries the per-connector settings stored in the secret vault; the
    environment is used only for connectors that have no vault entry.
    """
    base = get_settings()
    managed = configs or {}
    rows = []
    for connector in CONNECTORS.values():
        settings = SettingsOverlay(base, managed.get(connector.slug))
        missing = _missing_settings(connector, settings)
        rows.append(
            {
                "slug": connector.slug,
                "name": connector.name,
                "description": connector.description,
                "docs": connector.docs,
                "configured": not missing,
                "managed": connector.slug in managed,
                "required_settings": list(connector.env),
                "missing_settings": missing,
            }
        )
    return rows


def _event_payloads(events: list[dict[str, Any]], connector: Connector) -> list[dict[str, Any]]:
    """Wrap the shared event shape in whatever envelope the platform expects."""
    if connector.slug == "datadog":
        return [
            {
                **event,
                "message": f"{event['severity']} {event['control']}: {event['title']}",
                "ddsource": "unimonitor",
                "service": "unimonitor",
                "ddtags": f"severity:{event['severity']},tenant:{event['tenant_id']}",
            }
            for event in events
        ]
    return events


def _datadog_request(settings: Any, payloads: list[dict[str, Any]], _connector: Any) -> tuple[str, dict[str, Any]]:
    site = settings.DATADOG_SITE or "datadoghq.com"
    return (
        f"https://api.{site}/api/v2/logs",
        {"headers": {"DD-API-KEY": settings.DATADOG_API_KEY, "Content-Type": JSON_CONTENT_TYPE}, "json": payloads},
    )


def _splunk_request(settings: Any, payloads: list[dict[str, Any]], _connector: Any) -> tuple[str, dict[str, Any]]:
    url = settings.SPLUNK_HEC_URL.rstrip("/")
    if not url.endswith("/services/collector/event"):
        url = f"{url}/services/collector/event"
    body = "".join(json.dumps({"index": settings.SPLUNK_INDEX, "sourcetype": "unimonitor:finding", "event": event}) for event in payloads)
    return url, {
        "headers": {"Authorization": f"Splunk {settings.SPLUNK_HEC_TOKEN}", "Content-Type": JSON_CONTENT_TYPE},
        "content": body,
    }


def _elastic_request(settings: Any, payloads: list[dict[str, Any]], _connector: Any) -> tuple[str, dict[str, Any]]:
    lines: list[str] = []
    for event in payloads:
        lines.append(json.dumps({"index": {"_index": settings.ELASTIC_INDEX}}))
        lines.append(json.dumps(event))
    return (
        f"{settings.ELASTIC_URL.rstrip('/')}/_bulk",
        {
            "headers": {"Authorization": f"ApiKey {settings.ELASTIC_API_KEY}", "Content-Type": "application/x-ndjson"},
            "content": "\n".join(lines) + "\n",
        },
    )


def _sentinel_request(settings: Any, payloads: list[dict[str, Any]], _connector: Any) -> tuple[str, dict[str, Any]]:
    url = (
        f"{settings.AZURE_SENTINEL_DCR_ENDPOINT.rstrip('/')}"
        f"/dataCollectionRules/{settings.AZURE_SENTINEL_DCR_RULE_ID}"
        f"/streams/{settings.AZURE_SENTINEL_STREAM}?api-version=2023-01-01"
    )
    return url, {
        "headers": {
            "Authorization": f"Bearer {settings.AZURE_SENTINEL_ACCESS_TOKEN}",
            "Content-Type": JSON_CONTENT_TYPE,
        },
        "json": payloads,
    }


def _ndjson_request(settings: Any, payloads: list[dict[str, Any]], connector: Any) -> tuple[str, dict[str, Any]]:
    url = settings.WAZUH_INGEST_URL if connector.slug == "wazuh" else settings.SUMOLOGIC_HTTP_URL
    return url, {
        "headers": {"Content-Type": JSON_CONTENT_TYPE},
        "content": "\n".join(json.dumps(event) for event in payloads),
    }


def _chronicle_request(settings: Any, payloads: list[dict[str, Any]], _connector: Any) -> tuple[str, dict[str, Any]]:
    return settings.CHRONICLE_INGEST_URL, {
        "headers": {"Authorization": f"Bearer {settings.CHRONICLE_AUTH_TOKEN}", "Content-Type": JSON_CONTENT_TYPE},
        "json": {"events": payloads},
    }


def _webhook_request(settings: Any, payloads: list[dict[str, Any]], _connector: Any) -> tuple[str, dict[str, Any]]:
    headers = {"Content-Type": JSON_CONTENT_TYPE}
    if settings.SIEM_WEBHOOK_TOKEN:
        headers["Authorization"] = f"Bearer {settings.SIEM_WEBHOOK_TOKEN}"
    return settings.SIEM_WEBHOOK_URL, {
        "headers": headers,
        "json": {"source": "unimonitor", "format": "json", "events": payloads},
    }


_REQUEST_BUILDERS = {
    "datadog": _datadog_request,
    "splunk": _splunk_request,
    "elastic": _elastic_request,
    "sentinel": _sentinel_request,
    "ndjson": _ndjson_request,
    "json": _chronicle_request,
    "webhook": _webhook_request,
}


async def send_events(slug: str, events: list[dict[str, Any]], config: dict[str, str] | None = None) -> dict[str, Any]:
    """Send finding events through one connector; returns a small receipt."""
    connector = get_connector(slug)
    settings = SettingsOverlay(get_settings(), config)
    missing = _missing_settings(connector, settings)
    if missing:
        raise IntegrationError(f"{connector.name} is not configured: set {', '.join(missing)}")
    if not events:
        return {"provider": slug, "sent": 0}

    payloads = _event_payloads(events, connector)

    if connector.transport == "syslog":
        _send_syslog(settings, events)
        return {"provider": slug, "sent": len(events)}

    builder = _REQUEST_BUILDERS.get(connector.transport)
    if builder is None:
        raise IntegrationError(f"{connector.name} has an unsupported transport '{connector.transport}'")

    url, request = builder(settings, payloads, connector)
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.post(url, **request)

    if response.status_code >= 400:
        detail = response.text[:300]
        logger.warning("siem_send_failed", provider=slug, status=response.status_code, detail=detail)
        raise IntegrationError(f"{connector.name} rejected the batch ({response.status_code}): {detail}")
    return {"provider": slug, "sent": len(events), "status_code": response.status_code}


def _send_syslog(settings: Any, events: list[dict[str, Any]]) -> None:
    """One CEF datagram per event, using the finding shape rather than a raw object."""

    class _Line:
        """A finding-like view so ``finding_cef`` can format an already-built event."""

        def __init__(self, event: dict[str, Any]) -> None:
            self.id = event["id"]
            self.tenant_id = event["tenant_id"]
            self.external_control_id = event["control"]
            self.title = event["title"]
            self.severity = str(event["severity"]).upper()
            self.state = event["state"]
            self.category = event["category"]
            self.service = event["service"]
            self.risk_score = event["risk_score"]
            self.last_seen_at = None

    host = settings.SIEM_SYSLOG_HOST
    port = int(settings.SIEM_SYSLOG_PORT or 514)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for event in events:
            sock.sendto(finding_cef(_Line(event)).encode("utf-8"), (host, port))
    logger.info("siem_syslog_sent", host=host, port=port, count=len(events))


async def test_connector(slug: str, config: dict[str, str] | None = None) -> dict[str, Any]:
    """Send one synthetic event so an administrator can verify the wiring."""
    connector = get_connector(slug)
    if connector.slug == "syslog":
        sample = {
            "id": "test",
            "tenant_id": "test",
            "control": "TEST-001",
            "title": "UniMonitor connector test",
            "severity": "informational",
            "state": "not_implemented",
            "category": "Test",
            "service": "unimonitor",
            "risk_score": 0,
        }
    else:
        sample = {
            "id": "test",
            "tenant_id": "test",
            "control": "TEST-001",
            "title": "UniMonitor connector test",
            "severity": "informational",
            "state": "not_implemented",
            "category": "Test",
            "service": "unimonitor",
            "risk_score": 0,
            "triage_status": "open",
            "first_detected_at": None,
            "last_seen_at": None,
        }
    receipt = await send_events(slug, [sample], config)
    return {**receipt, "test": True}


def events_for_findings(findings: list[Any]) -> list[dict[str, Any]]:
    """Convert ORM findings to the shared event shape."""
    return [finding_event(finding) for finding in findings]
