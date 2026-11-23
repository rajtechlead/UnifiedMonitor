"""Microsoft Purview (Information Protection / DLP) collector."""

from __future__ import annotations

from dataclasses import dataclass, field

from unimonitor.core.logging import get_logger
from unimonitor.graph.client import GraphClient

logger = get_logger(__name__)


@dataclass
class PurviewData:
    sensitivity_labels: list[dict] = field(default_factory=list)
    dlp_policies: list[dict] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


class PurviewCollector:
    NAME = "purview"
    DISPLAY_NAME = "Microsoft Purview"

    def __init__(self, client: GraphClient) -> None:
        self.client = client

    async def collect(self) -> PurviewData:
        data = PurviewData()
        try:
            resp = await self.client.get("/informationProtection/sensitivityLabels")
            if resp.usable:
                data.sensitivity_labels = resp.data if isinstance(resp.data, list) else []
        except Exception as e:
            data.errors["sensitivity_labels"] = str(e)
        try:
            resp = await self.client.get("/security/informationProtection/sensitivityLabels")
            if resp.usable:
                data.dlp_policies = resp.data if isinstance(resp.data, list) else []
        except Exception as e:
            data.errors["dlp_policies"] = str(e)
        logger.info("Purview collection complete", labels=len(data.sensitivity_labels))
        return data
