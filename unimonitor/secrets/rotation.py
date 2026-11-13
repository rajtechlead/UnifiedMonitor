"""
Secret rotation manager.

Supports:
  - Manual rotation (immediate swap)
  - Scheduled rotation via Celery beat task
  - Grace period (old version stays accessible during transition)
  - Pre-rotation and post-rotation hooks

Rotation policy is stored in secret tags:
  rotate_after_days : "90"
  last_rotated_at   : ISO timestamp
  rotation_hook     : "unimonitor.secrets.hooks:on_rotate_client_secret"
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from unimonitor.core.logging import get_logger
from unimonitor.secrets.provider import SecretMetadata

logger = get_logger(__name__)


class RotationManager:
    """Coordinates secret rotation across providers."""

    def __init__(self, provider) -> None:
        self._provider = provider

    async def rotate(
        self,
        name: str,
        new_value: str,
        pre_hook: Callable[[str], Awaitable[None]] | None = None,
        post_hook: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> SecretMetadata:
        """
        Rotate a secret.

        Args:
            name: Secret identifier.
            new_value: Replacement value.
            pre_hook: Coroutine called before rotation (e.g. revoke old token).
            post_hook: Coroutine called after rotation (e.g. warm up connection pool).

        Returns:
            Updated SecretMetadata.
        """
        logger.info("Starting secret rotation", name=name, provider=str(self._provider.provider_type))

        if pre_hook:
            await pre_hook(name)

        metadata = await self._provider.rotate_secret(
            name,
            new_value,
        )

        if post_hook:
            await post_hook(name, new_value)

        logger.info("Secret rotation complete", name=name)
        return metadata

    async def check_rotation_due(self, name: str) -> bool:
        """Return True if the secret's rotation policy says it's due."""
        try:
            secrets = await self._provider.list_secrets(prefix=name)
            for secret in secrets:
                if secret.name != name:
                    continue
                days_str = secret.tags.get("rotate_after_days")
                last_rotated_str = secret.tags.get("last_rotated_at")
                if not days_str or not last_rotated_str:
                    return False
                days = int(days_str)
                last_rotated = datetime.fromisoformat(last_rotated_str)
                return datetime.now(UTC) > last_rotated + timedelta(days=days)
        except Exception as exc:
            logger.warning("Could not check rotation policy", name=name, error=str(exc))
        return False

    async def list_rotation_due(self) -> list[str]:
        """Return names of secrets that are past their rotation due date."""
        due: list[str] = []
        try:
            secrets = await self._provider.list_secrets()
            for secret in secrets:
                days_str = secret.tags.get("rotate_after_days")
                last_rotated_str = secret.tags.get("last_rotated_at")
                if not days_str or not last_rotated_str:
                    continue
                try:
                    days = int(days_str)
                    last_rotated = datetime.fromisoformat(last_rotated_str)
                    if datetime.now(UTC) > last_rotated + timedelta(days=days):
                        due.append(secret.name)
                except (ValueError, TypeError):
                    continue
        except Exception as exc:
            logger.warning("Error listing rotation-due secrets", error=str(exc))
        return due
