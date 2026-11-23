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

import asyncio
import json
import os
import stat
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from unimonitor.core.logging import get_logger
from unimonitor.secrets.provider import HealthStatus, ProviderType, SecretMetadata

logger = get_logger(__name__)

DEFAULT_VAULT_DIR = Path.home() / ".unimonitor" / "vault"
_VAULT_ENC_FILE = "vault.enc"
_VAULT_META_FILE = "vault.meta"
_VAULT_KEY_FILE = "vault.key"


def _atomic_write(path: Path, data: bytes) -> None:
    """Replace ``path`` with ``data`` without ever exposing a partial file.

    A crash between opening the destination and finishing the write used to
    leave a truncated vault that no key could decrypt. The bytes now land in a
    sibling temporary file that is flushed to disk, then renamed over the
    destination, so a reader always sees either the old blob or the new one.
    """
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with open(temporary, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _owner_only(path: Path) -> None:
    """Restrict a key file to its owner (a no-op where POSIX modes do not apply)."""
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:  # noqa: S110 - Windows has no POSIX modes
        pass


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
        # Vault I/O runs on worker threads, so mutations are serialised here to
        # keep read-modify-write whole and never expose a half-written file.
        self._io_lock = threading.RLock()
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
        _atomic_write(self._key_path, key)
        _owner_only(self._key_path)
        logger.info("New vault master key generated", key_path=str(self._key_path))
        return key

    @property
    def _previous_key_path(self) -> Path:
        return self._key_path.with_name(self._key_path.name + ".previous")

    def _load_keys(self) -> list[bytes]:
        """The current key followed by any retained older keys.

        Retained keys make rotation non-destructive: the vault is decrypted with
        whichever key it was written under, then re-encrypted with the newest one.
        """
        keys = [self._load_or_create_key()]
        if self._previous_key_path.exists():
            for line in self._previous_key_path.read_text().splitlines():
                candidate = line.strip().encode()
                if candidate:
                    keys.append(candidate)
        return keys

    def _get_fernet(self):
        from cryptography.fernet import Fernet, MultiFernet

        if self._fernet is None:
            self._fernet = MultiFernet([Fernet(key) for key in self._load_keys()])
        return self._fernet

    def rotate_master_key(self) -> int:
        """Re-encrypt the vault under a freshly generated master key.

        Returns the number of secrets re-encrypted. The previous keys are kept in
        ``vault.key.previous`` so an interrupted rotation can still read the old
        ciphertext; delete that file once the new key is verified.
        """
        from cryptography.fernet import Fernet, MultiFernet

        with self._io_lock:
            data = self._read_vault()
            old_keys = self._load_keys()
            new_key = Fernet.generate_key()
            # The retained keys are as sensitive as the current one: restrict them
            # before anything else can read the file the temporary blob became.
            _atomic_write(self._previous_key_path, b"\n".join(old_keys))
            _owner_only(self._previous_key_path)
            _atomic_write(self._key_path, new_key)
            _owner_only(self._key_path)
            # Write with only the new key: the ciphertext must not stay readable by
            # the retired keys.
            self._fernet = MultiFernet([Fernet(new_key)])
            self._write_vault(data)
            self._fernet = MultiFernet([Fernet(new_key), *[Fernet(key) for key in old_keys]])
        logger.info("Vault master key rotated", secrets=len(data))
        return len(data)

    # ------------------------------------------------------------------
    # Vault read/write helpers
    # ------------------------------------------------------------------

    def _read_vault(self) -> dict[str, str]:
        """Decrypt and return the vault contents as {name: value}."""
        with self._io_lock:
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
        with self._io_lock:
            self._ensure_vault_dir()
            plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
            ciphertext = self._get_fernet().encrypt(plaintext)
            _atomic_write(self._enc_path, ciphertext)
            _owner_only(self._enc_path)

    def _read_meta(self) -> dict[str, dict]:
        """Return metadata dict (non-sensitive)."""
        with self._io_lock:
            if not self._meta_path.exists():
                return {}
            try:
                return json.loads(self._meta_path.read_text(encoding="utf-8"))
            except Exception:
                return {}

    def _write_meta(self, meta: dict[str, dict]) -> None:
        with self._io_lock:
            self._ensure_vault_dir()
            payload = json.dumps(meta, default=str, indent=2).encode("utf-8")
            _atomic_write(self._meta_path, payload)

    # ------------------------------------------------------------------
    # Provider interface
    # ------------------------------------------------------------------

    async def get_secret(self, name: str, version: str | None = None) -> str:
        # Protocol argument: the local vault stores a single version per secret.
        del version
        vault = await asyncio.to_thread(self._read_vault)
        if name not in vault:
            raise KeyError(f"Secret '{name}' not found in local vault")
        return vault[name]

    async def set_secret(self, name: str, value: str, tags: dict[str, str] | None = None) -> SecretMetadata:
        return await asyncio.to_thread(self._store_secret, name, value, tags)

    def _store_secret(self, name: str, value: str, tags: dict[str, str] | None) -> SecretMetadata:
        """Blocking encrypt-and-write; the lock keeps read-modify-write atomic."""
        with self._io_lock:
            vault = self._read_vault()
            vault[name] = value
            self._write_vault(vault)

            # Update metadata
            meta = self._read_meta()
            meta[name] = {
                "created_at": str(datetime.now(UTC)),
                "tags": tags or {},
            }
            self._write_meta(meta)

        return SecretMetadata(
            name=name,
            provider=self.provider_type,
            created_at=datetime.now(UTC),
            tags=tags or {},
        )

    async def delete_secret(self, name: str) -> None:
        await asyncio.to_thread(self._remove_secret, name)

    def _remove_secret(self, name: str) -> None:
        with self._io_lock:
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
        return await asyncio.to_thread(self._secret_metadata, prefix)

    def _secret_metadata(self, prefix: str) -> list[SecretMetadata]:
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
        return await asyncio.to_thread(self._probe_health)

    def _probe_health(self) -> HealthStatus:
        start = time.monotonic()
        try:
            # Key creation is lazy, so a probe racing a write would otherwise read
            # a half-written key file and report the vault unhealthy.
            with self._io_lock:
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
