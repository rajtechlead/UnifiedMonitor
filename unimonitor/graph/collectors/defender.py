"""Microsoft Defender for Endpoint / 365 collector."""
from __future__ import annotations
from dataclasses import dataclass, field
from unimonitor.core.logging import get_logger
from unimonitor.graph.client import GraphClient

logger = get_logger(__name__)


@dataclass
class DefenderData:
    alerts: list[dict] = field(default_factory=list)
    incidents: list[dict] = field(default_factory=list)
    vulnerabilities: list[dict] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


class DefenderCollector:
    NAME = "defender"
    DISPLAY_NAME = "Microsoft Defender"

    def __init__(self, client: GraphClient) -> None:
        self.client = client

    async def collect(self) -> DefenderData:
        data = DefenderData()
        try:
            resp = await self.client.get("/security/alerts_v2", params={"$filter": "serviceSource eq 'microsoftDefenderForEndpoint'", "$top": "100"})
            if resp.success:
                data.alerts = resp.data if isinstance(resp.data, list) else []
        except Exception as e:
            data.errors["alerts"] = str(e)
        try:
            resp = await self.client.get("/security/incidents", params={"$top": "100"})
            if resp.success:
                data.incidents = resp.data if isinstance(resp.data, list) else []
        except Exception as e:
            data.errors["incidents"] = str(e)
        logger.info("Defender collection complete", alerts=len(data.alerts))
        return data
