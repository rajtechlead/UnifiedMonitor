"""SharePoint Online security collector."""
from __future__ import annotations
from dataclasses import dataclass, field
from unimonitor.core.logging import get_logger
from unimonitor.graph.client import GraphClient

logger = get_logger(__name__)


@dataclass
class SharePointData:
    sites: list[dict] = field(default_factory=list)
    sharing_policies: list[dict] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


class SharePointCollector:
    NAME = "sharepoint"
    DISPLAY_NAME = "SharePoint Online"

    def __init__(self, client: GraphClient) -> None:
        self.client = client

    async def collect(self) -> SharePointData:
        data = SharePointData()
        try:
            sites = await self.client.get_all_pages("/sites", params={"$select": "id,displayName,webUrl,siteCollection", "$top": "200"}, max_pages=5)
            data.sites = sites
        except Exception as e:
            data.errors["sites"] = str(e)
        logger.info("SharePoint collection complete", sites=len(data.sites))
        return data
