"""
Secret provider health checks and aggregated health reporting.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from unimonitor.core.logging import get_logger
from unimonitor.secrets.provider import HealthStatus, ProviderType

logger = get_logger(__name__)


@dataclass
class AggregatedHealthReport:
    """Health report across all configured providers."""

    statuses: list[HealthStatus]
    checked_at: datetime
    all_healthy: bool
    primary_healthy: bool

    def as_dict(self) -> dict:
        return {
            "checked_at": self.checked_at.isoformat(),
            "all_healthy": self.all_healthy,
            "primary_healthy": self.primary_healthy,
            "providers": [
                {
                    "provider": s.provider.value,
                    "healthy": s.healthy,
                    "latency_ms": s.latency_ms,
                    "message": s.message,
                }
                for s in self.statuses
            ],
        }


async def check_all_providers(
    providers: Sequence,
    primary_provider_type: ProviderType | None = None,
) -> AggregatedHealthReport:
    """Run health checks against all provided secret providers in parallel."""
    import asyncio

    tasks = [p.health_check() for p in providers]
    statuses: list[HealthStatus] = await asyncio.gather(*tasks, return_exceptions=False)

    all_healthy = all(s.healthy for s in statuses)
    primary_healthy = True
    if primary_provider_type:
        for s in statuses:
            if s.provider == primary_provider_type:
                primary_healthy = s.healthy
                break

    report = AggregatedHealthReport(
        statuses=list(statuses),
        checked_at=datetime.utcnow(),
        all_healthy=all_healthy,
        primary_healthy=primary_healthy,
    )

    if not all_healthy:
        unhealthy = [s.provider.value for s in statuses if not s.healthy]
        logger.warning("Secret provider health check failed", unhealthy_providers=unhealthy)

    return report
