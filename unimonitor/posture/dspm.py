"""Data security posture management (DSPM).

Answers three questions about the object stores in a snapshot: where is sensitive
data, what is exposed to the internet, and what protection (encryption, external
sharing control, retention) is missing. Sensitivity comes from the export's own
classification — the engine never guesses that an unlabelled bucket is sensitive.
"""

from __future__ import annotations

from typing import Any

from unimonitor.posture.findings import PostureFinding, resource_name, result
from unimonitor.posture.inventory import field, flag, number, text_list

CATEGORY = "dspm"
LABEL = "Data security posture"

_SENSITIVE_WORDS = ("pii", "personal", "sensitive", "confidential", "restricted", "phi", "pci", "secret", "credential")


def is_sensitive(store: dict[str, Any]) -> bool:
    """True when the export labels the store as holding sensitive data."""
    if flag(store, "contains_pii", "pii", "contains_phi", "phi", "pci", "sensitive"):
        return True
    labels = " ".join(text_list(store, "classification", "data_classification", "data_types", "tags", "labels")).lower()
    return any(word in labels for word in _SENSITIVE_WORDS)


def _public(store: dict[str, Any]) -> bool:
    return flag(store, "public", "public_access", "is_public", "publicly_accessible", "internet_exposed")


def _encrypted(store: dict[str, Any]) -> bool | None:
    """Encryption state, or ``None`` when the export does not say."""
    for name in ("encrypted", "encryption_enabled", "encryption_at_rest", "sse_enabled"):
        if name in store:
            return flag(store, name)
    return None


def _external_sharing(store: dict[str, Any]) -> bool:
    return flag(store, "external_sharing", "shared_externally", "anonymous_access", "allows_external_principals") or bool(
        text_list(store, "external_principals")
    )


def analyse(resources: list[dict[str, Any]], _edges: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Assess storage resources for sensitive-data exposure."""
    stores = [resource for resource in resources if resource.get("type") == "storage"]
    findings: list[PostureFinding] = []

    for store in stores:
        name = resource_name(store)
        sensitive = is_sensitive(store)
        public = _public(store)
        encrypted = _encrypted(store)

        if public and sensitive:
            findings.append(
                PostureFinding(
                    "DSPM-PUBLIC-SENSITIVE",
                    "Sensitive data store is publicly accessible",
                    "critical",
                    CATEGORY,
                    name,
                    "The store is marked public and holds data classified as sensitive.",
                    "Remove public access, then review access logs for the exposure window.",
                )
            )
        elif public:
            findings.append(
                PostureFinding(
                    "DSPM-PUBLIC-STORE",
                    "Data store is publicly accessible",
                    "high",
                    CATEGORY,
                    name,
                    "The store allows public access, whether or not it holds sensitive data.",
                    "Block public access unless it is a deliberate static-hosting origin.",
                )
            )

        if encrypted is False:
            severity = "critical" if sensitive else "high"
            findings.append(
                PostureFinding(
                    "DSPM-ENCRYPTION",
                    "Data store is not encrypted at rest",
                    severity,
                    CATEGORY,
                    name,
                    "The export reports encryption at rest as disabled.",
                    "Enable provider-managed encryption at minimum, then move sensitive data to a customer-managed key.",
                )
            )

        if _external_sharing(store):
            findings.append(
                PostureFinding(
                    "DSPM-EXTERNAL-SHARING",
                    "Data store is shared outside the organisation",
                    "critical" if sensitive else "medium",
                    CATEGORY,
                    name,
                    "External principals or anonymous access are configured on the store.",
                    "Remove external principals and require authenticated, audited access.",
                )
            )

        if sensitive:
            key_type = str(field(store, "encryption_key_type", "key_type", default="")).lower()
            if key_type in {"provider", "provider_managed", "default", "service"}:
                findings.append(
                    PostureFinding(
                        "DSPM-CMK",
                        "Sensitive data uses a provider-managed key",
                        "medium",
                        CATEGORY,
                        name,
                        f"Encryption key type is {key_type!r}.",
                        "Use a customer-managed key so access can be revoked independently of the provider.",
                    )
                )
            retention = number(store, "retention_days", "object_lock_days")
            if retention is not None and retention < 30:
                findings.append(
                    PostureFinding(
                        "DSPM-RETENTION",
                        "Sensitive data retention is shorter than 30 days",
                        "low",
                        CATEGORY,
                        name,
                        f"Retention is {retention} days.",
                        "Confirm the retention matches policy; short retention can destroy investigation evidence.",
                    )
                )
            if not any(key in store for key in ("classification", "data_classification", "data_types", "contains_pii", "tags", "labels")):
                findings.append(
                    PostureFinding(
                        "DSPM-UNCLASSIFIED",
                        "Data store has no classification",
                        "low",
                        CATEGORY,
                        name,
                        "No classification field is present, so sensitive-data handling cannot be verified.",
                        "Add a classification tag and include it in the inventory export.",
                    )
                )

    return result(
        CATEGORY,
        LABEL,
        findings,
        empty_note="No storage resources were present in the snapshot.",
    )


__all__ = ["CATEGORY", "LABEL", "analyse", "is_sensitive"]
