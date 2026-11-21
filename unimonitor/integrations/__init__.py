"""Outbound integrations: SIEM connectors and ticketing sync.

Everything here is push-only and opt-in: a connector is enabled by the presence
of its credentials, and nothing is sent until an administrator presses send.
"""

from unimonitor.integrations.events import finding_cef, finding_event
from unimonitor.integrations.siem import CONNECTORS, connector_status, send_events, test_connector
from unimonitor.integrations.ticketing import create_ticket, ticketing_status

__all__ = [
    "CONNECTORS",
    "connector_status",
    "create_ticket",
    "finding_cef",
    "finding_event",
    "send_events",
    "test_connector",
    "ticketing_status",
]
