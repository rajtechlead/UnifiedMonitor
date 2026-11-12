"""
TTL-based secret cache.

Keeps decrypted secret values in memory for a configurable duration to avoid
hammering cloud provider APIs on every request. Cache is per-process and
never persisted to disk.

Security notes:
  - Cache is NOT shared across processes (not stored in Redis — that would
    just move the secret into another plaintext store).
  - Default TTL = 300s (5 minutes). Set to 0 to disable caching.
  - Cache is invalidated immediately on rotation.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock


@dataclass
class _CacheEntry:
    value: str
    expires_at: float


class SecretCache:
    """Thread-safe in-memory TTL cache for secret values."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        """
        Args:
            ttl_seconds: How long to keep a cached secret. 0 = no caching.
        """
        self._ttl = ttl_seconds
        self._store: dict[str, _CacheEntry] = {}
        self._lock = Lock()

    def get(self, key: str) -> str | None:
        """Return cached value or None if missing/expired."""
        if self._ttl == 0:
            return None
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.monotonic() > entry.expires_at:
                del self._store[key]
                return None
            return entry.value

    def set(self, key: str, value: str) -> None:
        """Cache a secret value with the configured TTL."""
        if self._ttl == 0:
            return
        with self._lock:
            self._store[key] = _CacheEntry(
                value=value,
                expires_at=time.monotonic() + self._ttl,
            )

    def invalidate(self, key: str) -> None:
        """Remove a specific secret from the cache."""
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Flush the entire cache."""
        with self._lock:
            self._store.clear()

    def stats(self) -> dict:
        """Return cache statistics (no values)."""
        now = time.monotonic()
        with self._lock:
            total = len(self._store)
            expired = sum(1 for e in self._store.values() if now > e.expires_at)
        return {"total_entries": total, "expired_entries": expired, "ttl_seconds": self._ttl}
