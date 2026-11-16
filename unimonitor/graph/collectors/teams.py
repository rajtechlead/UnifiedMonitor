"""Microsoft Teams security collector."""

from __future__ import annotations

from dataclasses import dataclass, field

from unimonitor.core.logging import get_logger
from unimonitor.graph.client import GraphClient

logger = get_logger(__name__)


@dataclass
class TeamsData:
    teams: list[dict] = field(default_factory=list)
    policies: list[dict] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


class TeamsCollector:
    NAME = "teams"
    DISPLAY_NAME = "Microsoft Teams"

    def __init__(self, client: GraphClient) -> None:
        self.client = client

    async def collect(self) -> TeamsData:
        data = TeamsData()
        try:
            teams = await self.client.get_all_pages(
                "/teams", params={"$select": "id,displayName,isArchived,guestSettings", "$top": "100"}, max_pages=10
            )
            data.teams = teams
        except Exception as e:
            data.errors["teams"] = str(e)
        logger.info("Teams collection complete", teams=len(data.teams))
        return data
