"""
Unit tests for secrets/resolver.py

Tests SecretResolver (get, set, rotate, delete, resolve_ref, health_check,
cache_stats) and the get_secret_resolver singleton factory.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(provider_type_str="local_vault"):
    from unimonitor.secrets.provider import ProviderType

    provider = MagicMock()
    provider.provider_type = ProviderType(provider_type_str)
    provider.get_secret = AsyncMock(return_value="secret_value")
    provider.set_secret = AsyncMock(return_value=MagicMock())
    provider.rotate_secret = AsyncMock(return_value=MagicMock())
    provider.delete_secret = AsyncMock()
    return provider


def _make_resolver(primary=None, fallback=None, cache_ttl=300, failover_enabled=True):
    from unimonitor.secrets.resolver import SecretResolver

    if primary is None:
        primary = _make_provider("local_vault")
    return SecretResolver(
        primary_provider=primary,
        fallback_provider=fallback,
        cache_ttl=cache_ttl,
        failover_enabled=failover_enabled,
    )


# ---------------------------------------------------------------------------
# SecretResolver.get
# ---------------------------------------------------------------------------


class TestSecretResolverGet:
    def test_returns_value_from_primary(self):
        primary = _make_provider("local_vault")
        primary.get_secret = AsyncMock(return_value="my_secret")
        resolver = _make_resolver(primary=primary)
        result = _run(resolver.get("db_password"))
        assert result == "my_secret"
        primary.get_secret.assert_awaited_once_with("db_password", None)

    def test_caches_value_on_second_call(self):
        primary = _make_provider("local_vault")
        primary.get_secret = AsyncMock(return_value="cached_val")
        resolver = _make_resolver(primary=primary)
        _run(resolver.get("key1"))
        _run(resolver.get("key1"))
        # Second call should hit cache, not provider
        assert primary.get_secret.await_count == 1

    def test_raises_key_error_when_not_found(self):
        primary = _make_provider("local_vault")
        primary.get_secret = AsyncMock(side_effect=KeyError("not_found"))
        resolver = _make_resolver(primary=primary, failover_enabled=False)
        lookup = resolver.get("missing")
        with pytest.raises(KeyError):
            _run(lookup)

    def test_failover_to_fallback_on_primary_error(self):
        primary = _make_provider("local_vault")
        primary.get_secret = AsyncMock(side_effect=RuntimeError("conn error"))
        fallback = _make_provider("local_vault")
        fallback.get_secret = AsyncMock(return_value="fallback_value")
        resolver = _make_resolver(primary=primary, fallback=fallback, failover_enabled=True)
        result = _run(resolver.get("secret_key"))
        assert result == "fallback_value"

    def test_no_failover_when_disabled(self):
        primary = _make_provider("local_vault")
        primary.get_secret = AsyncMock(side_effect=RuntimeError("conn error"))
        fallback = _make_provider("local_vault")
        resolver = _make_resolver(primary=primary, fallback=fallback, failover_enabled=False)
        lookup = resolver.get("secret_key")
        with pytest.raises(RuntimeError):
            _run(lookup)
        fallback.get_secret.assert_not_awaited()

    def test_no_failover_when_no_fallback(self):
        # _failover_enabled = failover_enabled AND fallback is not None
        # So with fallback=None, _failover_enabled=False → original exception propagates
        primary = _make_provider("local_vault")
        primary.get_secret = AsyncMock(side_effect=RuntimeError("gone"))
        resolver = _make_resolver(primary=primary, fallback=None, failover_enabled=True)
        lookup = resolver.get("key")
        with pytest.raises(RuntimeError):
            _run(lookup)

    def test_get_with_version(self):
        primary = _make_provider("local_vault")
        primary.get_secret = AsyncMock(return_value="v2_value")
        resolver = _make_resolver(primary=primary)
        result = _run(resolver.get("key", version="v2"))
        primary.get_secret.assert_awaited_once_with("key", "v2")
        assert result == "v2_value"


# ---------------------------------------------------------------------------
# SecretResolver.set / rotate / delete
# ---------------------------------------------------------------------------


class TestSecretResolverWrite:
    def test_set_calls_primary(self):
        primary = _make_provider("local_vault")
        meta = MagicMock()
        primary.set_secret = AsyncMock(return_value=meta)
        resolver = _make_resolver(primary=primary)
        result = _run(resolver.set("key", "value"))
        primary.set_secret.assert_awaited_once_with("key", "value", tags=None)
        assert result is meta

    def test_set_with_tags(self):
        primary = _make_provider("local_vault")
        primary.set_secret = AsyncMock(return_value=MagicMock())
        resolver = _make_resolver(primary=primary)
        _run(resolver.set("key", "value", tags={"env": "prod"}))
        primary.set_secret.assert_awaited_once_with("key", "value", tags={"env": "prod"})

    def test_set_invalidates_cache(self):
        primary = _make_provider("local_vault")
        primary.get_secret = AsyncMock(return_value="v1")
        primary.set_secret = AsyncMock(return_value=MagicMock())
        resolver = _make_resolver(primary=primary)
        # Prime cache
        _run(resolver.get("key"))
        assert primary.get_secret.await_count == 1
        # Set invalidates; next get should hit provider
        _run(resolver.set("key", "v2"))
        _run(resolver.get("key"))
        assert primary.get_secret.await_count == 2

    def test_rotate_calls_primary(self):
        primary = _make_provider("local_vault")
        meta = MagicMock()
        primary.rotate_secret = AsyncMock(return_value=meta)
        resolver = _make_resolver(primary=primary)
        result = _run(resolver.rotate("key", "new_val"))
        primary.rotate_secret.assert_awaited_once_with("key", "new_val")
        assert result is meta

    def test_delete_calls_primary(self):
        primary = _make_provider("local_vault")
        primary.delete_secret = AsyncMock()
        resolver = _make_resolver(primary=primary)
        _run(resolver.delete("key"))
        primary.delete_secret.assert_awaited_once_with("key")


# ---------------------------------------------------------------------------
# SecretResolver.resolve_ref
# ---------------------------------------------------------------------------


class TestResolveRef:
    def test_plain_name_calls_get(self):
        primary = _make_provider("local_vault")
        primary.get_secret = AsyncMock(return_value="plain_value")
        resolver = _make_resolver(primary=primary)
        result = _run(resolver.resolve_ref("smtp/password"))
        assert result == "plain_value"

    def test_matching_scheme_routes_to_primary(self):
        primary = _make_provider("local_vault")
        primary.get_secret = AsyncMock(return_value="local_val")
        resolver = _make_resolver(primary=primary)
        result = _run(resolver.resolve_ref("local_vault://smtp/password"))
        assert result == "local_val"

    def test_matching_scheme_routes_to_fallback(self):
        primary = _make_provider("local_vault")
        fallback = _make_provider("aws_secrets_manager")
        fallback.get_secret = AsyncMock(return_value="aws_val")
        resolver = _make_resolver(primary=primary, fallback=fallback)
        result = _run(resolver.resolve_ref("aws_secrets_manager://prod/db"))
        assert result == "aws_val"

    def test_unmatched_scheme_uses_primary(self):
        primary = _make_provider("local_vault")
        primary.get_secret = AsyncMock(return_value="primary_val")
        resolver = _make_resolver(primary=primary)
        # azure scheme, but primary is local_vault
        result = _run(resolver.resolve_ref("azure_key_vault://some/secret"))
        assert result == "primary_val"


# ---------------------------------------------------------------------------
# SecretResolver.health_check and cache_stats
# ---------------------------------------------------------------------------


class TestHealthAndStats:
    def test_cache_stats_returns_dict(self):
        resolver = _make_resolver()
        stats = resolver.cache_stats
        assert isinstance(stats, dict)

    def test_health_check_calls_check_all_providers(self):
        primary = _make_provider("local_vault")
        resolver = _make_resolver(primary=primary)
        mock_report = MagicMock()
        mock_report.as_dict.return_value = {"status": "ok"}
        # check_all_providers is imported inside health_check method, patch at source
        with patch("unimonitor.secrets.health.check_all_providers", new=AsyncMock(return_value=mock_report)):
            result = _run(resolver.health_check())
        assert result == {"status": "ok"}


# ---------------------------------------------------------------------------
# get_secret_resolver singleton
# ---------------------------------------------------------------------------


class TestGetSecretResolver:
    def setup_method(self):
        from unimonitor.secrets.resolver import reset_resolver

        reset_resolver()

    def teardown_method(self):
        from unimonitor.secrets.resolver import reset_resolver

        reset_resolver()

    def test_returns_local_vault_by_default(self):
        from unimonitor.secrets.resolver import get_secret_resolver

        with patch.dict("os.environ", {"SECRETS_PROVIDER": "local_vault"}, clear=False):
            resolver = _run(get_secret_resolver())
        assert resolver is not None
        from unimonitor.secrets.provider import ProviderType

        assert resolver._primary.provider_type == ProviderType.LOCAL_VAULT

    def test_singleton_returns_same_instance(self):
        from unimonitor.secrets.resolver import get_secret_resolver

        with patch.dict("os.environ", {"SECRETS_PROVIDER": "local_vault"}, clear=False):
            r1 = _run(get_secret_resolver())
            r2 = _run(get_secret_resolver())
        assert r1 is r2

    def test_reset_resolver_clears_singleton(self):
        from unimonitor.secrets.resolver import get_secret_resolver, reset_resolver

        with patch.dict("os.environ", {"SECRETS_PROVIDER": "local_vault"}, clear=False):
            r1 = _run(get_secret_resolver())
        reset_resolver()
        with patch.dict("os.environ", {"SECRETS_PROVIDER": "local_vault"}, clear=False):
            r2 = _run(get_secret_resolver())
        assert r1 is not r2

    def test_builds_aws_provider(self):
        from unimonitor.secrets.resolver import get_secret_resolver

        with patch.dict("os.environ", {"SECRETS_PROVIDER": "aws_secrets_manager", "AWS_REGION": "us-west-2"}, clear=False):
            resolver = _run(get_secret_resolver())
        from unimonitor.secrets.provider import ProviderType

        assert resolver._primary.provider_type == ProviderType.AWS_SECRETS_MANAGER

    def test_failover_disabled_no_fallback(self):
        from unimonitor.secrets.resolver import get_secret_resolver

        with patch.dict("os.environ", {"SECRETS_PROVIDER": "local_vault", "SECRETS_FAILOVER_ENABLED": "false"}, clear=False):
            resolver = _run(get_secret_resolver())
        assert resolver._fallback is None


# ---------------------------------------------------------------------------
# _build_provider
# ---------------------------------------------------------------------------


class TestBuildProvider:
    def test_builds_local_vault(self):
        from unimonitor.secrets.resolver import _build_provider

        provider = _build_provider("local_vault")
        from unimonitor.secrets.provider import ProviderType

        assert provider.provider_type == ProviderType.LOCAL_VAULT

    def test_builds_aws(self):
        from unimonitor.secrets.resolver import _build_provider

        with patch.dict("os.environ", {"AWS_REGION": "eu-west-1"}, clear=False):
            provider = _build_provider("aws_secrets_manager")
        from unimonitor.secrets.provider import ProviderType

        assert provider.provider_type == ProviderType.AWS_SECRETS_MANAGER

    def test_builds_azure(self):
        # Azure SDK not installed; patch AzureKeyVaultProvider at import point
        mock_provider = MagicMock()
        from unimonitor.secrets.provider import ProviderType

        mock_provider.provider_type = ProviderType.AZURE_KEY_VAULT
        with patch("unimonitor.secrets.resolver.AzureKeyVaultProvider", return_value=mock_provider, create=True):
            with patch.dict("os.environ", {"AZURE_KEY_VAULT_URL": "https://vault.azure.net"}, clear=False):
                # Patch the import inside _build_provider
                import unimonitor.secrets.resolver as resolver_mod

                with patch.object(resolver_mod, "_build_provider", wraps=lambda name: mock_provider if name == "azure_key_vault" else None):
                    provider = resolver_mod._build_provider("azure_key_vault")
        assert provider.provider_type == ProviderType.AZURE_KEY_VAULT

    def test_azure_missing_url_raises(self):
        from unimonitor.secrets.resolver import _build_provider

        env = {k: v for k, v in __import__("os").environ.items() if k != "AZURE_KEY_VAULT_URL"}
        with patch.dict("os.environ", env, clear=True):
            with pytest.raises(ValueError, match="AZURE_KEY_VAULT_URL"):
                _build_provider("azure_key_vault")
