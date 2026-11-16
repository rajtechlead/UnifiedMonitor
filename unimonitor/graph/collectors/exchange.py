"""Exchange Online security collector."""
from __future__ import annotations
from dataclasses import dataclass, field
from unimonitor.core.logging import get_logger
from unimonitor.graph.client import GraphClient

logger = get_logger(__name__)


@dataclass
class ExchangeData:
    transport_rules: list[dict] = field(default_factory=list)
    dkim_configs: list[dict] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


class ExchangeCollector:
    NAME = "exchange"
    DISPLAY_NAME = "Exchange Online"

    def __init__(self, client: GraphClient) -> None:
        self.client = client

    async def collect(self) -> ExchangeData:
        data = ExchangeData()
        try:
            resp = await self.client.get("/admin/exchangeSettings")
            if resp.success:
                data.transport_rules = resp.data if isinstance(resp.data, list) else []
        except Exception as e:
            data.errors["transport_rules"] = str(e)
        logger.info("Exchange collection complete")
        return data
