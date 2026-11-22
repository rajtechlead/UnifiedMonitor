"""Master-key rotation and provider migration.

Rotation must re-encrypt everything so the retired key no longer opens the vault, while
still being able to read the vault it is rotating. Migration must copy values (and
tags) between providers so switching from the local vault to Key Vault is a config
change, not a re-entry of every credential.
"""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet, InvalidToken

from unimonitor.secrets.local_vault import LocalVaultProvider
from unimonitor.secrets.rotation import migrate_secrets


@pytest.fixture
def vault(tmp_path) -> LocalVaultProvider:
    return LocalVaultProvider(vault_dir=tmp_path / "vault")


class TestMasterKeyRotation:
    async def test_rotation_reencrypts_every_secret(self, vault: LocalVaultProvider):
        await vault.set_secret("a", "one", tags={"purpose": "test"})
        await vault.set_secret("b", "two")

        before = vault._enc_path.read_bytes()
        old_key = vault._key_path.read_bytes().strip()

        assert vault.rotate_master_key() == 2

        assert await vault.get_secret("a") == "one"
        assert await vault.get_secret("b") == "two"
        assert vault._enc_path.read_bytes() != before

        with pytest.raises(InvalidToken):
            Fernet(old_key).decrypt(vault._enc_path.read_bytes())

    async def test_the_previous_key_is_retained_for_recovery(self, vault: LocalVaultProvider):
        await vault.set_secret("a", "one")
        old_key = vault._key_path.read_bytes().strip()

        vault.rotate_master_key()

        previous = vault._previous_key_path.read_bytes().decode().splitlines()
        assert old_key.decode() in previous

        # The retained key still decrypts a ciphertext written before rotation.
        backup = Fernet(old_key).encrypt(b'{"a": "one"}')
        assert Fernet(old_key).decrypt(backup) == b'{"a": "one"}'

    async def test_rotating_twice_keeps_the_latest_key_authoritative(self, vault: LocalVaultProvider):
        await vault.set_secret("a", "one")
        vault.rotate_master_key()
        first_new = vault._key_path.read_bytes().strip()

        vault.rotate_master_key()

        assert vault._key_path.read_bytes().strip() != first_new
        assert await vault.get_secret("a") == "one"

    async def test_rotation_of_an_empty_vault_is_harmless(self, vault: LocalVaultProvider):
        assert vault.rotate_master_key() == 0
        await vault.set_secret("later", "value")
        assert await vault.get_secret("later") == "value"


class TestProviderMigration:
    async def test_every_secret_and_tag_is_copied(self, tmp_path):
        source = LocalVaultProvider(vault_dir=tmp_path / "source")
        target = LocalVaultProvider(vault_dir=tmp_path / "target")
        await source.set_secret("tenant-a-smtp", "secret-1", tags={"purpose": "smtp"})
        await source.set_secret("tenant-b-slack", "secret-2")

        assert await migrate_secrets(source, target) == 2

        assert await target.get_secret("tenant-a-smtp") == "secret-1"
        assert await target.get_secret("tenant-b-slack") == "secret-2"
        names = {metadata.name: metadata for metadata in await target.list_secrets()}
        assert names["tenant-a-smtp"].tags.get("purpose") == "smtp"

    async def test_a_prefix_limits_the_migration(self, tmp_path):
        source = LocalVaultProvider(vault_dir=tmp_path / "source")
        target = LocalVaultProvider(vault_dir=tmp_path / "target")
        await source.set_secret("keep-1", "v1")
        await source.set_secret("keep-2", "v2")
        await source.set_secret("other", "v3")

        assert await migrate_secrets(source, target, prefix="keep") == 2
        assert await target.get_secret("keep-1") == "v1"
        with pytest.raises(KeyError):
            await target.get_secret("other")
