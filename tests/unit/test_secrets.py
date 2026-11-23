"""
Unit tests for the secret management system.

Tests run without any cloud provider credentials — Local Vault and in-memory
mocking only.
"""

from __future__ import annotations

import asyncio

import pytest

# ---------------------------------------------------------------------------
# Local Vault tests
# ---------------------------------------------------------------------------


class TestLocalVault:
    @pytest.fixture
    def vault(self, tmp_path):
        from unimonitor.secrets.local_vault import LocalVaultProvider

        return LocalVaultProvider(vault_dir=tmp_path / "vault")

    @pytest.mark.asyncio
    async def test_set_and_get(self, vault):
        await vault.set_secret("test/key", "secret-value")
        value = await vault.get_secret("test/key")
        assert value == "secret-value"

    @pytest.mark.asyncio
    async def test_missing_secret_raises_key_error(self, vault):
        with pytest.raises(KeyError, match="not found"):
            await vault.get_secret("does/not/exist")

    @pytest.mark.asyncio
    async def test_delete(self, vault):
        await vault.set_secret("del/key", "value")
        await vault.delete_secret("del/key")
        with pytest.raises(KeyError):
            await vault.get_secret("del/key")

    @pytest.mark.asyncio
    async def test_delete_nonexistent_is_noop(self, vault):
        # Should not raise
        await vault.delete_secret("does/not/exist")

    @pytest.mark.asyncio
    async def test_list_secrets(self, vault):
        await vault.set_secret("prefix/a", "1")
        await vault.set_secret("prefix/b", "2")
        await vault.set_secret("other/c", "3")
        all_secrets = await vault.list_secrets()
        assert len(all_secrets) == 3
        prefix_secrets = await vault.list_secrets(prefix="prefix/")
        assert len(prefix_secrets) == 2

    @pytest.mark.asyncio
    async def test_rotate(self, vault):
        await vault.set_secret("rotate/key", "old-value")
        await vault.rotate_secret("rotate/key", "new-value")
        value = await vault.get_secret("rotate/key")
        assert value == "new-value"

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, vault):
        health = await vault.health_check()
        assert health.healthy is True
        assert health.latency_ms is not None
        assert health.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_metadata_has_tags(self, vault):
        meta = await vault.set_secret("tagged/key", "value", tags={"env": "test"})
        assert meta.tags == {"env": "test"}
        assert meta.name == "tagged/key"

    @pytest.mark.asyncio
    async def test_encryption_persists(self, tmp_path):
        """Restart the vault and verify data survives."""
        from unimonitor.secrets.local_vault import LocalVaultProvider

        vault1 = LocalVaultProvider(vault_dir=tmp_path / "vault")
        await vault1.set_secret("persistent/key", "persistent-value")

        # New instance same directory
        vault2 = LocalVaultProvider(vault_dir=tmp_path / "vault")
        value = await vault2.get_secret("persistent/key")
        assert value == "persistent-value"

    @pytest.mark.asyncio
    async def test_concurrent_writes_do_not_lose_secrets(self, vault):
        """Vault I/O runs on worker threads, so a write is a read-modify-write race.

        Every set_secret decrypts the current vault, adds one name and writes the
        whole file back. Without the provider's write lock the concurrent writers
        all read the same snapshot and the last write wins, silently discarding
        every secret written by the others; 40 writers against a handful of
        worker threads makes that interleaving effectively certain.
        """
        names = [f"concurrent/key-{i}" for i in range(40)]
        await asyncio.gather(*(vault.set_secret(name, f"value-{i}") for i, name in enumerate(names)))

        stored = {secret.name for secret in await vault.list_secrets(prefix="concurrent/")}
        assert stored == set(names)
        for i, name in enumerate(names):
            assert await vault.get_secret(name) == f"value-{i}"

    @pytest.mark.asyncio
    async def test_failed_write_keeps_the_previous_vault_intact(self, vault, monkeypatch):
        """A crash mid-write must not truncate the vault that was already there.

        The bytes are staged in a temporary file and renamed into place, so a
        failure before the rename leaves the old ciphertext exactly as it was
        and no partial file behind.
        """
        await vault.set_secret("stable/key", "stable-value")

        def _crash(_fd):
            raise OSError("simulated disk failure mid-write")

        monkeypatch.setattr("unimonitor.secrets.local_vault.os.fsync", _crash)

        with pytest.raises(OSError, match="simulated disk failure"):
            await vault.set_secret("lost/key", "lost-value")

        assert await vault.get_secret("stable/key") == "stable-value"
        assert list(vault.vault_dir.glob(".*.tmp")) == []
        with pytest.raises(KeyError):
            await vault.get_secret("lost/key")

    @pytest.mark.asyncio
    async def test_failed_rename_keeps_the_previous_vault_intact(self, vault, monkeypatch):
        """If the rename itself fails the destination is never touched."""
        await vault.set_secret("stable/key", "stable-value")
        before = vault._enc_path.read_bytes()

        def _fail_replace(_source, _destination):
            raise OSError("simulated rename failure")

        monkeypatch.setattr("unimonitor.secrets.local_vault.os.replace", _fail_replace)

        with pytest.raises(OSError, match="simulated rename failure"):
            await vault.set_secret("lost/key", "lost-value")

        assert vault._enc_path.read_bytes() == before
        assert list(vault.vault_dir.glob(".*.tmp")) == []


# ---------------------------------------------------------------------------
# SecretCache tests
# ---------------------------------------------------------------------------


class TestSecretCache:
    def test_set_and_get(self):
        from unimonitor.secrets.cache import SecretCache

        cache = SecretCache(ttl_seconds=60)
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_miss_returns_none(self):
        from unimonitor.secrets.cache import SecretCache

        cache = SecretCache(ttl_seconds=60)
        assert cache.get("missing") is None

    def test_ttl_zero_disables_caching(self):
        from unimonitor.secrets.cache import SecretCache

        cache = SecretCache(ttl_seconds=0)
        cache.set("key", "value")
        assert cache.get("key") is None

    def test_invalidate(self):
        from unimonitor.secrets.cache import SecretCache

        cache = SecretCache(ttl_seconds=60)
        cache.set("key", "value")
        cache.invalidate("key")
        assert cache.get("key") is None

    def test_clear(self):
        from unimonitor.secrets.cache import SecretCache

        cache = SecretCache(ttl_seconds=60)
        cache.set("a", "1")
        cache.set("b", "2")
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_expired_entry_returns_none(self):
        import time

        from unimonitor.secrets.cache import SecretCache

        cache = SecretCache(ttl_seconds=1)
        cache.set("key", "value")
        # Manually expire by patching the entry's timestamp
        entry = cache._store["key"]
        entry.expires_at = time.monotonic() - 1  # already expired
        assert cache.get("key") is None

    def test_stats(self):
        from unimonitor.secrets.cache import SecretCache

        cache = SecretCache(ttl_seconds=60)
        cache.set("a", "1")
        cache.set("b", "2")
        stats = cache.stats()
        assert stats["total_entries"] == 2
        assert stats["ttl_seconds"] == 60


# ---------------------------------------------------------------------------
# SecretResolver tests
# ---------------------------------------------------------------------------


class TestSecretResolver:
    @pytest.fixture
    def local_provider(self, tmp_path):
        from unimonitor.secrets.local_vault import LocalVaultProvider

        return LocalVaultProvider(vault_dir=tmp_path / "vault")

    @pytest.mark.asyncio
    async def test_get_caches_result(self, local_provider):
        from unimonitor.secrets.resolver import SecretResolver

        resolver = SecretResolver(primary_provider=local_provider, cache_ttl=60)
        await local_provider.set_secret("my/key", "cached-value")

        # First call — hits provider
        v1 = await resolver.get("my/key")
        # Second call — should return from cache
        v2 = await resolver.get("my/key")
        assert v1 == v2 == "cached-value"

    @pytest.mark.asyncio
    async def test_set_and_get(self, local_provider):
        from unimonitor.secrets.resolver import SecretResolver

        resolver = SecretResolver(primary_provider=local_provider)
        await resolver.set("set/key", "set-value")
        assert await resolver.get("set/key") == "set-value"

    @pytest.mark.asyncio
    async def test_rotate_invalidates_cache(self, local_provider):
        from unimonitor.secrets.resolver import SecretResolver

        resolver = SecretResolver(primary_provider=local_provider, cache_ttl=3600)
        await local_provider.set_secret("rotate/key", "old")
        # Warm up cache
        assert await resolver.get("rotate/key") == "old"
        # Rotate
        await resolver.rotate("rotate/key", "new")
        # Cache should be invalidated
        assert await resolver.get("rotate/key") == "new"

    @pytest.mark.asyncio
    async def test_failover_to_fallback(self, tmp_path):
        from unimonitor.secrets.local_vault import LocalVaultProvider
        from unimonitor.secrets.resolver import SecretResolver

        # Primary that always fails
        failing_primary = LocalVaultProvider(vault_dir=tmp_path / "broken_vault")

        # Pre-corrupt the vault
        broken_dir = tmp_path / "broken_vault"
        broken_dir.mkdir(parents=True, exist_ok=True)
        (broken_dir / "vault.enc").write_bytes(b"corrupted-data")
        (broken_dir / "vault.key").write_bytes(b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

        # Fallback that works
        fallback = LocalVaultProvider(vault_dir=tmp_path / "fallback_vault")
        await fallback.set_secret("fallback/key", "fallback-value")

        resolver = SecretResolver(
            primary_provider=failing_primary,
            fallback_provider=fallback,
            failover_enabled=True,
        )

        # Should succeed via fallback
        value = await resolver.get("fallback/key")
        assert value == "fallback-value"

    @pytest.mark.asyncio
    async def test_resolve_ref_with_scheme(self, local_provider):
        from unimonitor.secrets.resolver import SecretResolver

        resolver = SecretResolver(primary_provider=local_provider)
        await local_provider.set_secret("my/secret", "ref-value")
        ref = "local_vault://my/secret"
        value = await resolver.resolve_ref(ref)
        assert value == "ref-value"

    @pytest.mark.asyncio
    async def test_resolve_ref_without_scheme(self, local_provider):
        from unimonitor.secrets.resolver import SecretResolver

        resolver = SecretResolver(primary_provider=local_provider)
        await local_provider.set_secret("plain/key", "plain-value")
        value = await resolver.resolve_ref("plain/key")
        assert value == "plain-value"

    @pytest.mark.asyncio
    async def test_health_check(self, local_provider):
        from unimonitor.secrets.resolver import SecretResolver

        resolver = SecretResolver(primary_provider=local_provider)
        report = await resolver.health_check()
        assert "providers" in report
        assert report["primary_healthy"] is True


# ---------------------------------------------------------------------------
# Provider protocol compliance (duck-type check)
# ---------------------------------------------------------------------------


class TestProviderProtocolCompliance:
    @pytest.mark.asyncio
    async def test_local_vault_satisfies_protocol(self, tmp_path):
        """LocalVaultProvider must satisfy the SecretProvider protocol."""
        from unimonitor.secrets.local_vault import LocalVaultProvider
        from unimonitor.secrets.provider import SecretProvider

        provider = LocalVaultProvider(vault_dir=tmp_path / "prot_vault")
        assert isinstance(provider, SecretProvider)
