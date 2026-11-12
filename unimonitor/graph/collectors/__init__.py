"""Graph API collectors – one per Microsoft 365 service domain."""

from unimonitor.graph.collectors.azure_security import AzureSecurityCollector
from unimonitor.graph.collectors.copilot import CopilotCollector
from unimonitor.graph.collectors.defender import DefenderCollector
from unimonitor.graph.collectors.entra_id import EntraIdCollector
from unimonitor.graph.collectors.exchange import ExchangeCollector
from unimonitor.graph.collectors.intune import IntuneCollector
from unimonitor.graph.collectors.purview import PurviewCollector
from unimonitor.graph.collectors.sharepoint import SharePointCollector
from unimonitor.graph.collectors.teams import TeamsCollector

COLLECTOR_REGISTRY: dict[str, type] = {
    "entra_id": EntraIdCollector,
    "intune": IntuneCollector,
    "defender": DefenderCollector,
    "purview": PurviewCollector,
    "exchange": ExchangeCollector,
    "sharepoint": SharePointCollector,
    "teams": TeamsCollector,
    "copilot": CopilotCollector,
    "azure_security": AzureSecurityCollector,
}

__all__ = list(COLLECTOR_REGISTRY.keys()) + ["COLLECTOR_REGISTRY"]
