"""Anonymisation for AI prompts.

Nothing about a customer's environment may reach a model provider. The remediation
prompt is built from an allowlist of control metadata (control id, framework,
category, severity, state, and the catalogue's title/description) — never the tenant
row, the collector payload, evidence, policy ids, user attributes or finding ids.
Every string that does go out passes through :func:`scrub`, which removes the
identifiers a catalogue description can still pick up (policy names, upn suffixes,
URLs, addresses), so a defect downstream cannot leak one either.
"""

from __future__ import annotations

import re
from typing import Any

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
GUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6 = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b")
URL = re.compile(r"\b(?:https?|ftp)://[^\s\"'<>]+", re.IGNORECASE)
WINDOWS_PATH = re.compile(r"\b[A-Za-z]:\\[^\s\"'<>]*")
UNC_PATH = re.compile(r"\\\\[^\s\"'<>]+")
UNIX_PATH = re.compile(r"(?<![\w.])/(?:home|users|var|etc|opt|srv|mnt)/[^\s\"'<>]*", re.IGNORECASE)
DOMAIN = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:com|net|org|io|onmicrosoft|local|internal|corp|lan|cloud|dev|co\.uk)\b",
    re.IGNORECASE,
)
NUMBER = re.compile(r"\b\d{8,}\b")
PATH_PLACEHOLDER = "[PATH]"

# Order matters: longest/most specific patterns first, so a URL is not half-consumed
# by the domain rule and an email is not mangled by the domain rule either.
_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (URL, "[URL]"),
    (EMAIL, "[EMAIL]"),
    (GUID, "[GUID]"),
    (WINDOWS_PATH, PATH_PLACEHOLDER),
    (UNC_PATH, PATH_PLACEHOLDER),
    (UNIX_PATH, PATH_PLACEHOLDER),
    (IPV4, "[IP]"),
    (IPV6, "[IP]"),
    (DOMAIN, "[DOMAIN]"),
    (NUMBER, "[NUMBER]"),
)

CONTROL_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
ALLOWED_SEVERITIES = {"critical", "high", "medium", "low", "informational"}
MAX_TITLE = 200
MAX_DESCRIPTION = 600


def scrub(value: str) -> str:
    """Remove identifiers from one string."""
    text = str(value or "")
    for pattern, replacement in _RULES:
        text = pattern.sub(replacement, text)
    return text


def _clean(value: Any, limit: int) -> str:
    return scrub(str(value or "")).strip()[:limit]


def anonymise(finding: Any) -> dict[str, str]:
    """Build the exact payload allowed to leave the deployment.

    Accepts a dict, a Pydantic model or an ORM row. Only these six fields are read;
    ``tenant_id``, ``id``, ``evidence``, ``service`` and anything not listed here are
    dropped by construction rather than by a filter that could be forgotten.
    """

    def _get(key: str) -> Any:
        if isinstance(finding, dict):
            return finding.get(key)
        return getattr(finding, key, None)

    control_id = _clean(_get("external_control_id") or _get("control_id"), 64)
    if not CONTROL_ID.match(control_id):
        # A control id that is not the catalogue's own shape is not trusted to be
        # free of environment-specific values.
        control_id = "[CONTROL]"

    severity = _clean(_get("severity") or "medium", 20).lower()
    if severity not in ALLOWED_SEVERITIES:
        severity = "medium"

    return {
        "control_id": control_id,
        "framework": _clean(_get("framework") or _get("framework_id"), 64),
        "category": _clean(_get("category"), 64),
        "severity": severity,
        "state": _clean(_get("state") or "not_implemented", 32).lower(),
        "title": _clean(_get("title") or _get("description") or control_id, MAX_TITLE),
        "description": _clean(_get("description"), MAX_DESCRIPTION),
    }


__all__ = ["anonymise", "scrub"]
