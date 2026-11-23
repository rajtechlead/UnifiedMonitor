"""Validation shared by the global Settings page and the per-tenant settings page.

Both APIs accept the same branding fields, so the rules live in one place rather than
being copied into each validator (and drifting).
"""

from __future__ import annotations

MAX_LOGO_URL = 512
MAX_SUPPORT_EMAIL = 254


def validate_logo_url(value: str | None) -> str | None:
    """Only https or site-relative URLs — never javascript:/data: or plain http."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > MAX_LOGO_URL:
        raise ValueError("logo_url is too long")
    if not trimmed.startswith(("https://", "/")):
        raise ValueError("logo_url must be an https:// URL or a site-relative path")
    if trimmed.startswith("//"):
        raise ValueError("logo_url must not be protocol-relative")
    return trimmed


def validate_support_email(value: str | None) -> str | None:
    """A single address-shaped value with no whitespace or header injection."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > MAX_SUPPORT_EMAIL:
        raise ValueError("support_email is too long")
    if "@" not in trimmed or any(char.isspace() for char in trimmed) or any(char in trimmed for char in "\r\n,;"):
        raise ValueError("support_email must be a single email address")
    return trimmed


__all__ = ["validate_logo_url", "validate_support_email"]
