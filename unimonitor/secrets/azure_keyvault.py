"""
Azure Key Vault secret provider.

Requires:
    pip install azure-keyvault-secrets azure-identity

Authentication order (DefaultAzureCredential):
  1. EnvironmentCredential (AZURE_CLIENT_ID + AZURE_CLIENT_SECRET + AZURE_TENANT_ID)
  2. WorkloadIdentityCredential (AKS workload identity)
  3. ManagedIdentityCredential (Azure VM / App Service)
  4. AzureCliCredential (local dev)
"""
from __future__ import annotations

import time

from unimonitor.core.logging import get_logger
from unimonitor.secrets.provider import HealthStatus, ProviderType, SecretMetadata

logger = get_logger(__name__)


class AzureKeyVaultProvider:
    """Azure Key Vault implementation of the SecretProvider protocol."""

    provider_type = ProviderType.AZURE_KEY_VAULT

    def __init__(self, vault_url: str) -> None:
        """
        Args:
            vault_url: e.g. "https://my-vault.vault.azure.net/"
        """
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
        except ImportError as exc:
            raise ImportError(
                "Azure Key Vault support requires: pip install azure-keyvault-secrets azure-identity"
            ) from exc

        self._vault_url = vault_url
        self._credential = DefaultAzureCredential()
        self._client = SecretClient(vault_url=vault_url, credential=self._credential)
        logger.info("Azure Key Vault provider initialized", vault_url=vault_url)

    async def get_secret(self, name: str, version: str | None = None) -> str:
        """Retrieve a secret value. Raises KeyError if not found."""
        import asyncio

        from azure.core.exceptions import ResourceNotFoundError

        try:
            loop = asyncio.get_event_loop()
            secret = await loop.run_in_executor(
                None, lambda: self._client.get_secret(name, version=version)
            )
            if secret.value is None:
                raise KeyError(f"Secret '{name}' has no value in Azure Key Vault")
            return secret.value
        except ResourceNotFoundError:
            raise KeyError(f"Secret '{name}' not found in Azure Key Vault ({self._vault_url})")
        except Exception as exc:
            logger.error("Azure Key Vault get_secret failed", name=name, error=str(exc))
            raise

    async def set_secret(self, name: str, value: str, tags: dict[str, str] | None = None) -> SecretMetadata:
        """Create or update a secret."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            props = await loop.run_in_executor(
                None, lambda: self._client.set_secret(name, value, tags=tags or {})
            )
            return SecretMetadata(
                name=name,
                provider=self.provider_type,
                version=props.properties.version,
                created_at=props.properties.created_on,
                tags=dict(props.properties.tags or {}),
            )
        except Exception as exc:
            logger.error("Azure Key Vault set_secret failed", name=name, error=str(exc))
            raise

    async def delete_secret(self, name: str) -> None:
        """Begin deletion. Azure KV uses a soft-delete with recovery period."""
        import asyncio

        from azure.core.exceptions import ResourceNotFoundError

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self._client.begin_delete_secret(name))
            logger.info("Azure Key Vault secret deletion initiated", name=name)
        except ResourceNotFoundError:
            pass  # Already gone
        except Exception as exc:
            logger.error("Azure Key Vault delete_secret failed", name=name, error=str(exc))
            raise

    async def list_secrets(self, prefix: str = "") -> list[SecretMetadata]:
        """List all secret properties, optionally filtered by name prefix."""
        import asyncio

        loop = asyncio.get_event_loop()
        props_list = await loop.run_in_executor(
            None, lambda: list(self._client.list_properties_of_secrets())
        )
        results = []
        for props in props_list:
            if prefix and not props.name.startswith(prefix):
                continue
            results.append(
                SecretMetadata(
                    name=props.name,
                    provider=self.provider_type,
                    version=props.version,
                    created_at=props.created_on,
                    expires_at=props.expires_on,
                    tags=dict(props.tags or {}),
                )
            )
        return results

    async def rotate_secret(self, name: str, new_value: str) -> SecretMetadata:
        """Rotate secret. Azure KV automatically versions; old version stays accessible."""
        return await self.set_secret(name, new_value)

    async def health_check(self) -> HealthStatus:
        """Ping the vault by listing secrets (page size = 1)."""
        import asyncio

        from azure.core.exceptions import ClientAuthenticationError

        start = time.monotonic()
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: next(iter(self._client.list_properties_of_secrets()), None),
            )
            latency_ms = (time.monotonic() - start) * 1000
            return HealthStatus(
                provider=self.provider_type,
                healthy=True,
                latency_ms=latency_ms,
                message="Azure Key Vault reachable",
            )
        except ClientAuthenticationError as exc:
            return HealthStatus(
                provider=self.provider_type,
                healthy=False,
                message=f"Authentication failed: {exc}",
            )
        except Exception as exc:
            return HealthStatus(
                provider=self.provider_type,
                healthy=False,
                message=f"Health check failed: {exc}",
            )
