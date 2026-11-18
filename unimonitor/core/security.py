"""Secret management and encryption utilities."""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet

from unimonitor.config import get_settings


def _get_fernet() -> Fernet:
    """Return a Fernet instance keyed from the application secret.

    The secret is already a random 256-bit key, so a hash with a fixed domain prefix
    is enough — stretching a high-entropy key (and its fixed salt) added nothing.
    """
    secret = get_settings().UNIMONITOR_SECRET_KEY.encode()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"unimonitor-fernet-v1" + secret).digest()))


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
