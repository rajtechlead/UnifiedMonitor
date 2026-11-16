"""Microsoft 365 Copilot collector."""
from __future__ import annotations
from dataclasses import dataclass, field
from unimonitor.core.logging import get_logger
from unimonitor.graph.client import GraphClient

logger = get_logger(__name__)


@dataclass
class CopilotData:
    usage_reports: list[dict] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


class CopilotCollector:
    NAME = "copilot"
    DISPLAY_NAME = "Microsoft 365 Copilot"

    def __init__(self, client: GraphClient) -> None:
        self.client = client

    async def collect(self) -> CopilotData:
        data = CopilotData()
        try:
            resp = await self.client.get("/reports/getCopilotUsageSummary")
            if resp.success:
                data.usage_reports = resp.data if isinstance(resp.data, list) else []
        except Exception as e:
            data.errors["usage_reports"] = str(e)
        logger.info("Copilot collection complete")
        return data
