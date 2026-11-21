"""Kubernetes and container posture.

Evaluates the cluster-level controls that matter most when a cluster is reachable
from the internet or runs untrusted workloads: API exposure, anonymous auth,
RBAC breadth, network policy, audit logging, secret encryption and privileged
containers.
"""

from __future__ import annotations

from typing import Any

from unimonitor.posture.findings import PostureFinding, resource_name, result
from unimonitor.posture.inventory import field, flag, number

CATEGORY = "kubernetes"
LABEL = "Kubernetes posture"


def analyse(resources: list[dict[str, Any]], _edges: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Assess every Kubernetes cluster in the snapshot."""
    clusters = [resource for resource in resources if resource.get("type") == "cluster"]
    findings: list[PostureFinding] = []

    for cluster in clusters:
        name = resource_name(cluster)
        public = flag(cluster, "public_endpoint", "public_api_server", "api_server_public", "public", "internet_exposed")

        if public:
            findings.append(
                PostureFinding(
                    "K8S-PUBLIC-API",
                    "Kubernetes API server is publicly reachable",
                    "high",
                    CATEGORY,
                    name,
                    "The API endpoint is exposed to the internet.",
                    "Restrict the endpoint to authorised networks or put it behind a private endpoint.",
                )
            )

        if flag(cluster, "anonymous_auth", "anonymous_authentication", "allow_anonymous"):
            findings.append(
                PostureFinding(
                    "K8S-ANON-AUTH",
                    "Anonymous authentication is enabled",
                    "critical",
                    CATEGORY,
                    name,
                    "Unauthenticated requests are accepted by the API server.",
                    "Disable anonymous auth; RBAC cannot protect requests that carry no identity.",
                )
            )

        admin_bindings = number(cluster, "cluster_admin_bindings", default=0) or 0
        if flag(cluster, "rbac_wildcard", "wildcard_rbac") or admin_bindings > 0:
            findings.append(
                PostureFinding(
                    "K8S-RBAC-WILDCARD",
                    "Cluster RBAC grants wildcard or cluster-admin access",
                    "high",
                    CATEGORY,
                    name,
                    "A binding grants * verbs/resources or cluster-admin.",
                    "Bind narrowly scoped ClusterRoles to named service accounts; remove cluster-admin from workloads.",
                )
            )

        if flag(cluster, "network_policy", "network_policies", "default_deny") is False:
            findings.append(
                PostureFinding(
                    "K8S-NO-NETWORK-POLICY",
                    "No default-deny network policy",
                    "medium",
                    CATEGORY,
                    name,
                    "Network policy is reported as absent or not enforcing a default deny.",
                    "Apply a default-deny ingress policy per namespace, then allow only required flows.",
                )
            )

        if flag(cluster, "audit_logging", "audit_log_enabled", "audit") is False:
            findings.append(
                PostureFinding(
                    "K8S-NO-AUDIT",
                    "Kubernetes audit logging is disabled",
                    "high",
                    CATEGORY,
                    name,
                    "Audit logging is reported as disabled.",
                    "Enable audit policy at Metadata level at minimum and ship the log to the SIEM.",
                )
            )

        if flag(cluster, "secrets_encrypted", "encryption_at_rest", "etcd_encryption") is False:
            findings.append(
                PostureFinding(
                    "K8S-SECRETS-UNENCRYPTED",
                    "Kubernetes secrets are not encrypted at rest",
                    "high",
                    CATEGORY,
                    name,
                    "etcd encryption for secrets is reported as disabled.",
                    "Enable a KMS-backed encryption provider for secrets.",
                )
            )

        privileged = number(cluster, "privileged_containers", "privileged_pods", default=0) or 0
        if privileged > 0 or flag(cluster, "host_network", "host_pid", "host_path"):
            findings.append(
                PostureFinding(
                    "K8S-PRIVILEGED-WORKLOAD",
                    "Privileged or host-namespace workload present",
                    "high",
                    CATEGORY,
                    name,
                    f"{privileged} privileged container(s) or host namespace access reported.",
                    "Drop privileged mode, hostPath/hostNetwork and runAsNonRoot via pod security admission.",
                )
            )

        if flag(cluster, "image_scanning", "admission_control", "policy_engine") is False:
            findings.append(
                PostureFinding(
                    "K8S-NO-IMAGE-SCANNING",
                    "No image scanning or admission policy",
                    "low",
                    CATEGORY,
                    name,
                    "Admission control/image scanning is reported as disabled.",
                    "Scan images on push and enforce signed, scanned images at admission.",
                )
            )

        if field(cluster, "version_supported", "supported_version") is not None and not flag(cluster, "version_supported", "supported_version"):
            findings.append(
                PostureFinding(
                    "K8S-VERSION-UNSUPPORTED",
                    "Cluster version is no longer supported",
                    "medium",
                    CATEGORY,
                    name,
                    f"Reported version {field(cluster, 'version', default='unknown')} is outside the supported window.",
                    "Upgrade to a supported minor version; unsupported versions stop receiving security fixes.",
                )
            )

    return result(
        CATEGORY,
        LABEL,
        findings,
        empty_note="No Kubernetes clusters were present in the snapshot.",
    )


__all__ = ["CATEGORY", "LABEL", "analyse"]
