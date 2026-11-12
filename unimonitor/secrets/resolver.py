"""
SecretResolver — unified interface over all configured secret providers.

Responsibilities:
  1. Selects the active provider based on SECRETS_PROVIDER env var.
  2. Wraps every get with the TTL cache.
  3. Records every access in the audit log.
  4. Implements provider failover: primary → fallback (Local Vault).
  5. Exposes a convenience `resolve_ref()` for secret-reference strings
     of the form "<provider>://<name>" stored in the database.

Provider selection (SECRETS_PROVIDER env var):
  azure_key_vault         — Azure Key Vault (requires AZURE_KEY_VAULT_URL)
  aws_secrets_manager     — AWS Secrets Manager (requires AWS_REGION)
  local_vault             — Fernet-encrypted local file vault (default)

Failover:
  If the primary provider fails, the resolver automatically falls back
  to Local Vault (if it is not already the primary). Set
  SECRETS_FAILOVER_ENABLED=false to disable failover.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from unimonitor.core.logging import get_logger
from unimonitor.secrets.audit import AuditOperation, SecretAuditLog
from unimonitor.secrets.cache import SecretCache
from unimonitor.secrets.provider import ProviderType, SecretMetadata

logger = get_logger(__name__)


class SecretResolver:
    """Unified secret accessor with caching, audit logging, and failover."""

    def __init__(
        self,
        primary_provider,
        fallback_provider=None,
        cache_ttl: int = 300,
        audit_file: Path | None = None,
        failover_enabled: bool = True,
    ) -> None:
        self._primary = primary_provider
        self._fallback = fallback_provider
        self._cache = SecretCache(ttl_seconds=cache_ttl)
        self._audit = SecretAuditLog(audit_file=audit_file)
        self._failover_enabled = failover_enabled and fallback_provider is not None

    async def get(self, name: str, version: str | None = None) -> str:
        """
        Retrieve a secret value.

        Checks cache first, then primary provider, then fallback.
        Every access is audit-logged.

        Raises:
            KeyError: If the secret is not found in any provider.
            RuntimeError: If all providers fail unexpectedly.
        """
        cache_key = f"{name}@{version or 'latest'}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # Try primary
        async with self._audit.track(AuditOperation.GET, name, str(self._primary.provider_type)):
            try:
                value = await self._primary.get_secret(name, version)
                self._cache.set(cache_key, value)
                return value
            except KeyError:
                raise
            except Exception as exc:
                if not self._failover_enabled:
                    raise
                logger.warning(
                    "Primary secret provider failed, trying fallback",
                    name=name,
                    primary=str(self._primary.provider_type),
                    error=str(exc),
                )

        # Failover to fallback
        if self._fallback:
            async with self._audit.track(
                AuditOperation.GET, name, str(self._fallback.provider_type)
            ):
                value = await self._fallback.get_secret(name, version)
                self._cache.set(cache_key, value)
                return value

        raise RuntimeError(f"All secret providers failed for secret '{name}'")

    async def set(self, name: str, value: str, tags: dict[str, str] | None = None) -> SecretMetadata:
        """Write a secret to the primary provider and invalidate cache."""
        async with self._audit.track(AuditOperation.SET, name, str(self._primary.provider_type)):
            metadata = await self._primary.set_secret(name, value, tags=tags)
        self._cache.invalidate(f"{name}@latest")
        return metadata

    async def rotate(self, name: str, new_value: str) -> SecretMetadata:
        """Rotate a secret and invalidate cache."""
        async with self._audit.track(AuditOperation.ROTATE, name, str(self._primary.provider_type)):
            metadata = await self._primary.rotate_secret(name, new_value)
        self._cache.invalidate(f"{name}@latest")
        return metadata

    async def delete(self, name: str) -> None:
        """Delete a secret from the primary provider and invalidate cache."""
        async with self._audit.track(AuditOperation.DELETE, name, str(self._primary.provider_type)):
            await self._primary.delete_secret(name)
        self._cache.invalidate(f"{name}@latest")

    async def resolve_ref(self, ref: str) -> str:
        """
        Resolve a secret reference string stored in the database.

        Reference format: "<provider_type>://<secret_name>"
        Example: "azure_key_vault://unimonitor/tenants/abc/client-secret"
                 "local_vault://smtp/password"

        Falls back to treating the ref as a plain secret name against the
        primary provider if no scheme is present.
        """
        if "://" in ref:
            scheme, name = ref.split("://", 1)
            # Route to correct provider based on scheme
            provider_type = ProviderType(scheme)
            if provider_type == self._primary.provider_type:
                return await self.get(name)
            if self._fallback and provider_type == self._fallback.provider_type:
                return await self._fallback.get_secret(name)
            # Scheme doesn't match any configured provider — try primary anyway
            logger.warning(
                "Secret reference scheme not matched to configured provider, using primary",
                ref_scheme=scheme,
                primary=str(self._primary.provider_type),
            )
            return await self.get(name)
        return await self.get(ref)

    async def health_check(self) -> dict:
        """Run health checks against all providers."""
        from unimonitor.secrets.health import check_all_providers

        providers = [self._primary]
        if self._fallback:
            providers.append(self._fallback)
        report = await check_all_providers(providers, primary_provider_type=self._primary.provider_type)
        return report.as_dict()

    @property
    def cache_stats(self) -> dict:
        return self._cache.stats()


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_resolver: SecretResolver | None = None


async def get_secret_resolver() -> SecretResolver:
    """
    Return the application-level SecretResolver (lazy-initialized singleton).

    Provider is chosen via the SECRETS_PROVIDER environment variable:
      azure_key_vault | aws_secrets_manager | local_vault (default)
    """
    global _resolver
    if _resolver is not None:
        return _resolver

    provider_name = os.environ.get("SECRETS_PROVIDER", "local_vault").lower()
    failover_enabled = os.environ.get("SECRETS_FAILOVER_ENABLED", "true").lower() != "false"
    cache_ttl = int(os.environ.get("SECRETS_CACHE_TTL_SECONDS", "300"))
    audit_file_path = os.environ.get("SECRETS_AUDIT_LOG_PATH")
    audit_file = Path(audit_file_path) if audit_file_path else None

    primary = _build_provider(provider_name)

    # Always have Local Vault available as fallback (unless it IS the primary)
    fallback = None
    if failover_enabled and provider_name != "local_vault":
        try:
            from unimonitor.secrets.local_vault import LocalVaultProvider
            fallback = LocalVaultProvider()
        except Exception as exc:
            logger.warning("Could not initialize Local Vault fallback", error=str(exc))

    _resolver = SecretResolver(
        primary_provider=primary,
        fallback_provider=fallback,
        cache_ttl=cache_ttl,
        audit_file=audit_file,
        failover_enabled=failover_enabled,
    )
    logger.info(
        "SecretResolver initialized",
        primary_provider=provider_name,
        failover=fallback is not None,
        cache_ttl=cache_ttl,
    )
    return _resolver


def _build_provider(provider_name: str):
    if provider_name == "azure_key_vault":
        vault_url = os.environ.get("AZURE_KEY_VAULT_URL")
        if not vault_url:
            raise ValueError(
                "AZURE_KEY_VAULT_URL must be set when SECRETS_PROVIDER=azure_key_vault"
            )
        from unimonitor.secrets.azure_keyvault import AzureKeyVaultProvider
        return AzureKeyVaultProvider(vault_url=vault_url)

    elif provider_name == "aws_secrets_manager":
        region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
        endpoint_url = os.environ.get("AWS_SECRETS_MANAGER_ENDPOINT_URL")
        from unimonitor.secrets.aws_secrets_manager import AWSSecretsManagerProvider
        return AWSSecretsManagerProvider(region_name=region, endpoint_url=endpoint_url)

    else:  # local_vault (default)
        vault_dir = os.environ.get("VAULT_DIR")
        key_path = os.environ.get("VAULT_KEY_PATH")
        from unimonitor.secrets.local_vault import LocalVaultProvider
        return LocalVaultProvider(
            vault_dir=vault_dir,
            key_path=key_path,
        )


def reset_resolver() -> None:
    """Reset the singleton (for tests)."""
    global _resolver
    _resolver = None
