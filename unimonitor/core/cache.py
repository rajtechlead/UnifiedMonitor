"""Redis cache utilities."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from unimonitor.config import get_settings

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def cache_get(key: str) -> Any | None:
    try:
        client = await get_redis()
        value = await client.get(key)
        if value is None:
            return None
        return json.loads(value)
    except Exception:
        return None


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    try:
        settings = get_settings()
        client = await get_redis()
        serialised = json.dumps(value, default=str)
        await client.set(key, serialised, ex=ttl or settings.REDIS_CACHE_TTL)
    except Exception:  # noqa: S110
        pass  # Cache failures are non-fatal


async def cache_delete(key: str) -> None:
    try:
        client = await get_redis()
        await client.delete(key)
    except Exception:  # noqa: S110
        pass


async def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching a pattern. Returns count deleted."""
    try:
        client = await get_redis()
        keys = await client.keys(pattern)
        if keys:
            return await client.delete(*keys)
        return 0
    except Exception:
        return 0


def make_graph_cache_key(tenant_id: str, endpoint: str) -> str:
    """Generate a cache key for Graph API responses."""
    safe_endpoint = endpoint.replace("/", "_").strip("_")
    return f"graph:{tenant_id}:{safe_endpoint}"


def make_assessment_cache_key(tenant_id: str, run_id: str) -> str:
    return f"assessment:{tenant_id}:{run_id}"


def make_dashboard_cache_key(tenant_id: str, view: str) -> str:
    return f"dashboard:{tenant_id}:{view}"


# Aliases used by main.py startup/shutdown lifecycle
async def init_cache() -> None:
    """Initialise Redis cache connection (no-op; connection is lazy)."""
    # Redis connections are created lazily on first use; this is a no-op lifecycle hook.
    pass


async def close_cache() -> None:
    """Close Redis cache connection."""
    try:
        redis = await get_redis()
        await redis.close()
    except Exception:  # noqa: S110
        pass
