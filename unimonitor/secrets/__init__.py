"""
UniMonitor Secret Management — enterprise secret provider abstraction.

No plaintext secrets are stored in source code, configuration files,
database rows, Docker manifests, or installer assets.

Supported providers:
  - Azure Key Vault
  - AWS Secrets Manager
  - Encrypted Local Vault (Fernet, default fallback)

Usage::

    from unimonitor.secrets import get_secret_resolver
    resolver = await get_secret_resolver()
    value = await resolver.get("unimonitor/db/password")
"""

from __future__ import annotations

from unimonitor.secrets.provider import SecretMetadata, SecretProvider
from unimonitor.secrets.resolver import SecretResolver, get_secret_resolver

__all__ = [
    "SecretResolver",
    "get_secret_resolver",
    "SecretProvider",
    "SecretMetadata",
]
