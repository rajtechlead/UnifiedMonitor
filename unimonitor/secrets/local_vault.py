"""
Encrypted Local Vault — Fernet-symmetric-encryption secret store.

Suitable for:
  - Windows single-user deployments
  - Security consultant / MSSP offline deployments
  - Development environments
  - Fallback when cloud providers are unavailable

Storage layout::

    <vault_path>/
        vault.enc       — encrypted JSON blob (Fernet)
        vault.meta      — unencrypted metadata (names, tags, timestamps; NO values)
        vault.key       — master key file (chmod 600, excluded from git)

The master key file location can be overridden via VAULT_KEY_PATH env var so
the key lives on a USB / separate path from the encrypted data.

Requires:
    pip install cryptography
"""

from __future__ import annotations

import json
import os
import stat
import time
from datetime import datetime
from pathlib import Path

from unimonitor.core.logging import get_logger
from unimonitor.secrets.provider import HealthStatus, ProviderType, SecretMetadata

logger = get_logger(__name__)

DEFAULT_VAULT_DIR = Path.home() / ".unimonitor" / "vault"
_VAULT_ENC_FILE = "vault.enc"
_VAULT_META_FILE = "vault.meta"
_VAULT_KEY_FILE = "vault.key"


class LocalVaultProvider:
    """Fernet-encrypted local secret vault."""

    provider_type = ProviderType.LOCAL_VAULT

    def __init__(
        self,
        vault_dir: Path | str | None = None,
        key_path: Path | str | None = None,
    ) -> None:
        """
        Args:
            vault_dir: Directory to store encrypted vault files. Defaults to ~/.unimonitor/vault
            key_path: Path to master key file. Defaults to <vault_dir>/vault.key
                      Override with VAULT_KEY_PATH env var.
        """
        try:
            from cryptography.fernet import Fernet
        except ImportError as exc:
            raise ImportError("Local Vault support requires: pip install cryptography") from exc

        self._vault_dir = Path(vault_dir or os.environ.get("VAULT_DIR", DEFAULT_VAULT_DIR))
        self._enc_path = self._vault_dir / _VAULT_ENC_FILE
        self._meta_path = self._vault_dir / _VAULT_META_FILE
        self._key_path = Path(key_path or os.environ.get("VAULT_KEY_PATH", self._vault_dir / _VAULT_KEY_FILE))
        self._fernet: Fernet | None = None
        logger.info("Local Vault provider initialized", vault_dir=str(self._vault_dir))

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    def _ensure_vault_dir(self) -> None:
        self._vault_dir.mkdir(parents=True, exist_ok=True)
        # Restrict directory permissions on POSIX
        try:
            os.chmod(self._vault_dir, stat.S_IRWXU)
        except Exception:  # noqa: S110
            pass  # Windows — skip chmod

    def _load_or_create_key(self) -> bytes:
        from cryptography.fernet import Fernet

        if self._key_path.exists():
            key = self._key_path.read_bytes().strip()
            if not key:
                raise ValueError(f"Empty key file at {self._key_path}")
            return key

        # Generate new key
        self._ensure_vault_dir()
        key = Fernet.generate_key()
        self._key_path.write_bytes(key)
        try:
            os.chmod(self._key_path, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:  # noqa: S110
            pass
        logger.info("New vault master key generated", key_path=str(self._key_path))
        return key

    def _get_fernet(self):
        from cryptography.fernet import Fernet

        if self._fernet is None:
            key = self._load_or_create_key()
            self._fernet = Fernet(key)
        return self._fernet

    # ------------------------------------------------------------------
    # Vault read/write helpers
    # ------------------------------------------------------------------

    def _read_vault(self) -> dict[str, str]:
        """Decrypt and return the vault contents as {name: value}."""
        if not self._enc_path.exists():
            return {}
        try:
            ciphertext = self._enc_path.read_bytes()
            plaintext = self._get_fernet().decrypt(ciphertext)
            return json.loads(plaintext.decode("utf-8"))
        except Exception as exc:
            logger.error("Vault decryption failed", error=str(exc))
            raise RuntimeError(f"Cannot read local vault: {exc}") from exc

    def _write_vault(self, data: dict[str, str]) -> None:
        """Encrypt and persist the vault."""
        self._ensure_vault_dir()
        plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
        ciphertext = self._get_fernet().encrypt(plaintext)
        self._enc_path.write_bytes(ciphertext)
        try:
            os.chmod(self._enc_path, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:  # noqa: S110
            pass

    def _read_meta(self) -> dict[str, dict]:
        """Return metadata dict (non-sensitive)."""
        if not self._meta_path.exists():
            return {}
        try:
            return json.loads(self._meta_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_meta(self, meta: dict[str, dict]) -> None:
        self._ensure_vault_dir()
        self._meta_path.write_text(json.dumps(meta, default=str, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Provider interface
    # ------------------------------------------------------------------

    async def get_secret(self, name: str, version: str | None = None) -> str:
        vault = self._read_vault()
        if name not in vault:
            raise KeyError(f"Secret '{name}' not found in local vault")
        return vault[name]

    async def set_secret(self, name: str, value: str, tags: dict[str, str] | None = None) -> SecretMetadata:
        vault = self._read_vault()
        vault[name] = value
        self._write_vault(vault)

        # Update metadata
        meta = self._read_meta()
        meta[name] = {
            "created_at": str(datetime.utcnow()),
            "tags": tags or {},
        }
        self._write_meta(meta)

        return SecretMetadata(
            name=name,
            provider=self.provider_type,
            created_at=datetime.utcnow(),
            tags=tags or {},
        )

    async def delete_secret(self, name: str) -> None:
        vault = self._read_vault()
        if name not in vault:
            return
        del vault[name]
        self._write_vault(vault)

        meta = self._read_meta()
        meta.pop(name, None)
        self._write_meta(meta)
        logger.info("Local vault secret deleted", name=name)

    async def list_secrets(self, prefix: str = "") -> list[SecretMetadata]:
        meta = self._read_meta()
        results = []
        for name, m in meta.items():
            if prefix and not name.startswith(prefix):
                continue
            results.append(
                SecretMetadata(
                    name=name,
                    provider=self.provider_type,
                    created_at=m.get("created_at"),
                    tags=m.get("tags", {}),
                )
            )
        return results

    async def rotate_secret(self, name: str, new_value: str) -> SecretMetadata:
        """Overwrite secret with new value (old value not retained in local vault)."""
        return await self.set_secret(name, new_value)

    async def health_check(self) -> HealthStatus:
        start = time.monotonic()
        try:
            self._ensure_vault_dir()
            # Round-trip encrypt/decrypt a test value
            fernet = self._get_fernet()
            test = fernet.encrypt(b"health_check")
            fernet.decrypt(test)
            latency_ms = (time.monotonic() - start) * 1000
            return HealthStatus(
                provider=self.provider_type,
                healthy=True,
                latency_ms=latency_ms,
                message=f"Local vault healthy ({self._vault_dir})",
            )
        except Exception as exc:
            return HealthStatus(
                provider=self.provider_type,
                healthy=False,
                message=f"Local vault unhealthy: {exc}",
            )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def initialize(self) -> Path:
        """Create vault directory and generate master key. Returns key path."""
        self._ensure_vault_dir()
        self._load_or_create_key()
        return self._key_path

    @property
    def key_path(self) -> Path:
        return self._key_path

    @property
    def vault_dir(self) -> Path:
        return self._vault_dir
