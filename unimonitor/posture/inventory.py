"""Normalise a posture snapshot into one resource model.

A snapshot is JSON. Three shapes are accepted, because operators export
inventories in different ways:

1. ``{"resources": [{"type": "...", ...}, ...]}`` — already normalised.
2. A bare list of resource dicts — same, without the wrapper.
3. ``{"s3_buckets": [...], "iam_roles": [...], "instances": [...]}`` — one list
   per resource family, as cloud inventory exports usually look.

Every resource is a dict. The ``type`` field selects which engines consider it:

``storage``         object/blob/file store (bucket, storage account, drive, site)
``compute``         VM, instance, function
``identity``        user, role, service account, service principal
``security_group``  firewall/NSG rule set
``logging``         audit/logging configuration
``key``             KMS/key-vault key
``tenant_settings`` tenant-wide security switches
``cluster``         Kubernetes cluster
``ai_deployment``   Copilot/agent/model deployment

Field names are read tolerantly (``public``/``public_access``/``is_public``) so a
native export does not need rewriting before it can be analysed. Anything the
snapshot omits is reported as absent, never assumed to pass.
"""

from __future__ import annotations

from typing import Any

RESOURCE_TYPES = (
    "storage",
    "compute",
    "identity",
    "security_group",
    "logging",
    "key",
    "tenant_settings",
    "cluster",
    "ai_deployment",
)

# Raw export keys mapped to the canonical resource type.
_TYPE_ALIASES: dict[str, str] = {
    "s3_buckets": "storage",
    "buckets": "storage",
    "storage_accounts": "storage",
    "blobs": "storage",
    "drives": "storage",
    "sites": "storage",
    "file_shares": "storage",
    "instances": "compute",
    "instances_detail": "compute",
    "virtual_machines": "compute",
    "vms": "compute",
    "functions": "compute",
    "iam_roles": "identity",
    "iam_users": "identity",
    "roles": "identity",
    "users": "identity",
    "service_accounts": "identity",
    "principals": "identity",
    "security_groups": "security_group",
    "network_security_groups": "security_group",
    "firewalls": "security_group",
    "cloudtrail": "logging",
    "audit_logs": "logging",
    "logging": "logging",
    "kms_keys": "key",
    "keys": "key",
    "tenant_settings": "tenant_settings",
    "settings": "tenant_settings",
    "clusters": "cluster",
    "kubernetes_clusters": "cluster",
    "eks_clusters": "cluster",
    "aks_clusters": "cluster",
    "gke_clusters": "cluster",
    "ai_deployments": "ai_deployment",
    "copilot": "ai_deployment",
    "deployments": "ai_deployment",
}

_TRUE_STRINGS = ("true", "yes", "enabled", "on", "1", "blocked", "restricted", "enforced", "required")


def truthy(value: Any, *, default: bool = False) -> bool:
    """Read a boolean that an export may have written as a string."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in _TRUE_STRINGS
    if isinstance(value, (int, float)):
        return bool(value)
    return bool(value)


def field(resource: dict[str, Any], *names: str, default: Any = None) -> Any:
    """First present field under any of *names*."""
    for name in names:
        if name in resource:
            return resource[name]
    return default


def flag(resource: dict[str, Any], *names: str, default: bool = False) -> bool:
    return truthy(field(resource, *names, default=None), default=default)


def number(resource: dict[str, Any], *names: str, default: int | None = None) -> int | None:
    value = field(resource, *names, default=None)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(str(value)))
        except (TypeError, ValueError):
            return default


def text_list(resource: dict[str, Any], *names: str) -> list[str]:
    value = field(resource, *names, default=[])
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return []


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _typed_mapping(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split a ``{"storage": [...], "edges": [...]}`` export into resources and edges."""
    resources: list[dict[str, Any]] = []
    edges = _dicts(payload.get("edges"))
    for key, value in payload.items():
        resource_type = _TYPE_ALIASES.get(key.lower())
        if key == "edges" or resource_type is None:
            continue
        resources.extend({**item, "type": item.get("type") or resource_type} for item in _dicts(value))
    return resources, edges


def normalise(payload: Any) -> dict[str, Any]:
    """Return ``{"resources": [...], "edges": [...]}`` from any accepted shape."""
    resources: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    if isinstance(payload, list):
        resources = _dicts(payload)
    elif isinstance(payload, dict) and isinstance(payload.get("resources"), list):
        resources = _dicts(payload["resources"])
        edges = _dicts(payload.get("edges"))
    elif isinstance(payload, dict):
        resources, edges = _typed_mapping(payload)

    for resource in resources:
        resource.setdefault("type", "unknown")
        resource.setdefault("id", str(resource.get("name") or resource.get("arn") or len(resources)))
    return {"resources": resources, "edges": edges}


def by_type(resources: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {name: [] for name in RESOURCE_TYPES}
    for resource in resources:
        groups.setdefault(str(resource.get("type", "unknown")), []).append(resource)
    return groups


def summary(payload: Any) -> dict[str, Any]:
    """A small inventory overview for the API and UI."""
    normalised = normalise(payload)
    groups = by_type(normalised["resources"])
    return {
        "resources": len(normalised["resources"]),
        "edges": len(normalised["edges"]),
        "by_type": {name: len(items) for name, items in sorted(groups.items()) if items},
    }
