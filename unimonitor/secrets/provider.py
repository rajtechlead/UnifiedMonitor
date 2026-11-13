"""
Abstract SecretProvider protocol.

All concrete providers (Azure Key Vault, AWS Secrets Manager, Local Vault)
implement this protocol so the resolver can swap them without changing call sites.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable


class ProviderType(StrEnum):
    AZURE_KEY_VAULT = "azure_key_vault"
    AWS_SECRETS_MANAGER = "aws_secrets_manager"
    LOCAL_VAULT = "local_vault"


@dataclass
class SecretMetadata:
    """Non-sensitive metadata about a secret."""

    name: str
    provider: ProviderType
    version: str | None = None
    created_at: datetime | None = None
    expires_at: datetime | None = None
    tags: dict[str, str] = field(default_factory=dict)

    @property
    def reference(self) -> str:
        """Return a provider-specific reference string (safe to store in DB)."""
        return f"{self.provider.value}://{self.name}"


@dataclass
class HealthStatus:
    provider: ProviderType
    healthy: bool
    latency_ms: float | None = None
    message: str = ""
    checked_at: datetime = field(default_factory=datetime.utcnow)


@runtime_checkable
class SecretProvider(Protocol):
    """Protocol that all secret providers must satisfy."""

    provider_type: ProviderType

    async def get_secret(self, name: str, version: str | None = None) -> str:
        """Retrieve a secret value by name. Raises KeyError if not found."""
        ...

    async def set_secret(self, name: str, value: str, tags: dict[str, str] | None = None) -> SecretMetadata:
        """Create or update a secret. Returns metadata (never the value)."""
        ...

    async def delete_secret(self, name: str) -> None:
        """Delete a secret. No-op if already absent."""
        ...

    async def list_secrets(self, prefix: str = "") -> list[SecretMetadata]:
        """List secrets with optional name prefix filter."""
        ...

    async def rotate_secret(self, name: str, new_value: str) -> SecretMetadata:
        """Rotate a secret to a new value, retaining the old version for a grace period."""
        ...

    async def health_check(self) -> HealthStatus:
        """Verify provider connectivity and authentication."""
        ...
