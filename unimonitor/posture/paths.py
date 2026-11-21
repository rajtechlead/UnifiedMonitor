"""Identity-driven attack paths.

A flat list of failing controls does not show how an attacker chains them. This
engine walks the snapshot's graph from an identity to the resources it can reach
and reports the chains that end at something valuable — a public data store, a
sensitive data set or a cluster.

Edges are optional. When an export provides ``edges`` they are followed; when it
does not, an identity's own ``resources``/``access`` list is used. A path is only
reported when every hop is present in the snapshot: the engine never invents an
edge, so an incomplete export produces fewer paths rather than speculative ones.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from unimonitor.posture.ciem import actions_of, has_wildcard, is_privileged
from unimonitor.posture.dspm import is_sensitive
from unimonitor.posture.findings import PostureFinding, resource_name, result
from unimonitor.posture.inventory import field, flag, text_list

CATEGORY = "paths"
LABEL = "Identity attack paths"
MAX_DEPTH = 4


def _index(resources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for resource in resources:
        for key in ("id", "name", "arn"):
            value = resource.get(key)
            if value:
                index[str(value)] = resource
    return index


def _adjacency(edges: list[dict[str, Any]]) -> dict[str, list[str]]:
    graph: dict[str, list[str]] = {}
    for edge in edges:
        source = edge.get("from") or edge.get("source")
        target = edge.get("to") or edge.get("target")
        if source and target:
            graph.setdefault(str(source), []).append(str(target))
    return graph


def _declared_targets(identity: dict[str, Any]) -> list[str]:
    targets: list[str] = []
    for name in ("resources", "access", "can_access", "targets"):
        targets.extend(text_list(identity, name))
    return targets


def _reachable(identity: dict[str, Any], graph: dict[str, list[str]], index: dict[str, dict[str, Any]], limit: int = 25) -> list[dict[str, Any]]:
    """Resources reachable from an identity within :data:`MAX_DEPTH` hops."""
    start = str(identity.get("id") or identity.get("name") or "")
    queue: deque[tuple[str, int]] = deque((target, 1) for target in _declared_targets(identity))
    if start:
        queue.extend((target, 1) for target in graph.get(start, []))
    if identity.get("name"):
        queue.extend((target, 1) for target in graph.get(str(identity["name"]), []))

    seen: set[str] = set()
    found: list[dict[str, Any]] = []
    while queue and len(found) < limit:
        node, depth = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        resource = index.get(node)
        if resource is not None and resource is not identity:
            found.append(resource)
        if depth < MAX_DEPTH:
            queue.extend((nxt, depth + 1) for nxt in graph.get(node, []))
    return found


def _severity(identity: dict[str, Any], target: dict[str, Any]) -> tuple[str, str]:
    """Return (severity, impact) for an identity→target pair."""
    target_type = target.get("type")
    if target_type == "storage":
        public = flag(target, "public", "public_access", "is_public", "publicly_accessible")
        sensitive = is_sensitive(target)
        if public and sensitive:
            return "critical", "public exposure of sensitive data"
        if sensitive:
            return "critical", "access to sensitive data"
        if public:
            return "high", "access to a public data store"
        return "high", "access to a data store"
    if target_type == "cluster":
        if flag(target, "public_endpoint", "public_api_server", "public"):
            return "critical", "cluster takeover through a public API server"
        return "high", "cluster access"
    if target_type == "identity":
        if is_privileged(target):
            return "critical", "privilege escalation to an administrative identity"
        return "medium", "lateral movement to another identity"
    if target_type == "key":
        return "high", "access to a decryption key"
    return "medium", f"access to a {target_type or 'resource'}"


def _why(identity: dict[str, Any]) -> str | None:
    """Why the identity is worth starting a path from, or None."""
    actions = actions_of(identity)
    if has_wildcard(actions):
        return "wildcard permissions"
    if is_privileged(identity):
        return "administrative role"
    if not flag(identity, "mfa_enabled", "mfa", "strong_auth", default=False):
        return "no MFA on the identity"
    if actions:
        return "granted cloud permissions"
    return None


def analyse(resources: list[dict[str, Any]], edges: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Walk identity→resource edges and report the valuable chains."""
    index = _index(resources)
    graph = _adjacency(edges or [])
    identities = [resource for resource in resources if resource.get("type") == "identity"]
    findings: list[PostureFinding] = []

    for identity in identities:
        reason = _why(identity)
        if reason is None:
            continue
        name = resource_name(identity)
        targets = _reachable(identity, graph, index)
        for target in targets:
            severity, impact = _severity(identity, target)
            target_name = resource_name(target)
            steps = (
                f"identity {name} ({reason})",
                f"can reach {target.get('type', 'resource')} {target_name}",
                f"impact: {impact}",
            )
            findings.append(
                PostureFinding(
                    f"PATH-{name}-{target_name}",
                    f"{name} can reach {target_name}",
                    severity,
                    CATEGORY,
                    name,
                    " → ".join(steps),
                    "Break the path at the first hop: remove the unnecessary grant, require MFA, or close the public exposure.",
                    steps=steps,
                )
            )

    # Directly reported paths from an export (e.g. a graph product) are kept so
    # the page shows the same chains the operator already trusts.
    findings.extend(_reported_paths(resources))

    return result(
        CATEGORY,
        LABEL,
        findings,
        empty_note="No identity-to-resource edges were present in the snapshot.",
    )


def _reported_paths(resources: list[dict[str, Any]]) -> list[PostureFinding]:
    reported: list[PostureFinding] = []
    for resource in resources:
        if resource.get("type") != "path":
            continue
        steps = tuple(text_list(resource, "steps", "chain"))
        reported.append(
            PostureFinding(
                str(resource.get("id") or "PATH-REPORTED"),
                str(field(resource, "title", "name", default="Reported attack path")),
                str(field(resource, "severity", default="high")),
                CATEGORY,
                resource_name(resource),
                str(field(resource, "detail", "description", default="")),
                str(field(resource, "remediation", default="")),
                steps=steps,
            )
        )
    return reported


__all__ = ["CATEGORY", "LABEL", "analyse"]
