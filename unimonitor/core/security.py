"""Secret management and encryption utilities."""

from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from unimonitor.config import get_settings


def _get_fernet() -> Fernet:
    """Return a Fernet instance keyed from the application secret."""
    settings = get_settings()
    secret = settings.UNIMONITOR_SECRET_KEY.encode()
    # Derive a 32-byte key from the secret
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"unimonitor_v1",
        iterations=100_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret))
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret for storage."""
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a stored secret."""
    fernet = _get_fernet()
    return fernet.decrypt(ciphertext.encode()).decode()


def generate_api_key(length: int = 32) -> str:
    """Generate a cryptographically secure API key."""
    return base64.urlsafe_b64encode(os.urandom(length)).decode().rstrip("=")


def constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks."""
    import hmac
    return hmac.compare_digest(a.encode(), b.encode())
