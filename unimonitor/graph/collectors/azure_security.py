"""Azure Security Center / Defender for Cloud collector."""

from __future__ import annotations

from dataclasses import dataclass, field

from unimonitor.core.logging import get_logger
from unimonitor.graph.client import GraphClient

logger = get_logger(__name__)


@dataclass
class AzureSecurityData:
    secure_scores: list[dict] = field(default_factory=list)
    secure_score_controls: list[dict] = field(default_factory=list)
    alerts: list[dict] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


class AzureSecurityCollector:
    NAME = "azure_security"
    DISPLAY_NAME = "Azure Security Center"

    def __init__(self, client: GraphClient) -> None:
        self.client = client

    async def collect(self) -> AzureSecurityData:
        data = AzureSecurityData()
        try:
            resp = await self.client.get("/security/secureScores")
            if resp.usable:
                data.secure_scores = resp.data if isinstance(resp.data, list) else []
        except Exception as e:
            data.errors["secure_scores"] = str(e)
        try:
            resp = await self.client.get("/security/secureScoreControlProfiles")
            if resp.usable:
                data.secure_score_controls = resp.data if isinstance(resp.data, list) else []
        except Exception as e:
            data.errors["secure_score_controls"] = str(e)
        try:
            resp = await self.client.get("/security/alerts_v2", params={"$top": "100"})
            if resp.usable:
                data.alerts = resp.data if isinstance(resp.data, list) else []
        except Exception as e:
            data.errors["alerts"] = str(e)
        logger.info("Azure Security collection complete", secure_scores=len(data.secure_scores))
        return data
