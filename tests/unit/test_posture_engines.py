"""Posture engines: CIS packs, DSPM, CIEM, AI-SPM, Kubernetes and attack paths."""

from __future__ import annotations

from unimonitor.posture.analysis import analyse
from unimonitor.posture.cis import BENCHMARKS, evaluate_cis
from unimonitor.posture.inventory import by_type, normalise

SNAPSHOT = {
    "s3_buckets": [
        {"name": "public-pii", "public": True, "contains_pii": True, "encrypted": False},
        {"name": "private-logs", "public": False, "encrypted": True},
    ],
    "iam_roles": [
        {
            "name": "ci-deployer",
            "permissions": ["*"],
            "mfa_enabled": False,
            "service_account": True,
            "kind": "ci",
            "key_age_days": 200,
            "resources": ["public-pii"],
        }
    ],
    "clusters": [{"name": "prod-eks", "public_api_server": True, "anonymous_auth": True, "network_policy": False, "audit_logging": False}],
    "ai_deployments": [{"name": "support-agent", "public_endpoint": True, "authentication": "none", "tools": ["send_email"], "model_version": ""}],
    "tenant_settings": [{"admin_count": 2, "mfa_enforced": True}],
}


def _groups(payload=SNAPSHOT):
    return by_type(normalise(payload)["resources"])


def test_normalise_accepts_export_family_lists():
    document = normalise(SNAPSHOT)
    assert len(document["resources"]) == 6
    assert {resource["type"] for resource in document["resources"]} == {
        "storage",
        "identity",
        "cluster",
        "ai_deployment",
        "tenant_settings",
    }


def test_cis_pack_without_resources_never_passes():
    result = evaluate_cis("aws", {})
    assert result["score"] is None
    assert all(rule["state"] == "not_applicable" for rule in result["results"])
    assert set(BENCHMARKS) == {"aws", "azure", "gcp", "m365", "google_workspace"}


def test_cis_pack_scores_a_real_failure():
    result = evaluate_cis("aws", _groups())
    assert result["score"] is not None
    assert result["failed"] >= 1
    assert any(rule["state"] == "fail" for rule in result["results"])


def test_dspm_flags_public_sensitive_store():
    from unimonitor.posture import dspm

    resources = normalise(SNAPSHOT)["resources"]
    report = dspm.analyse(resources)
    titles = {(finding["title"], finding["resource"]) for finding in report["findings"]}
    assert ("Sensitive data store is publicly accessible", "public-pii") in titles
    assert ("Data store is publicly accessible", "private-logs") not in titles


def test_ciem_flags_wildcard_and_escalation_material():
    from unimonitor.posture import ciem

    resources = normalise(SNAPSHOT)["resources"]
    report = ciem.analyse(resources)
    ids = {finding["id"] for finding in report["findings"]}
    assert {"CIEM-WILDCARD", "CIEM-PRIVILEGED-NO-MFA", "CIEM-SERVICE-ADMIN", "CIEM-CI-ADMIN"} <= ids
    assert any(finding["severity"] == "critical" for finding in report["findings"])


def test_aispm_flags_unauthenticated_public_agent():
    from unimonitor.posture import aispm

    resources = normalise(SNAPSHOT)["resources"]
    report = aispm.analyse(resources)
    ids = {finding["id"] for finding in report["findings"]}
    assert {"AISPM-PUBLIC-ENDPOINT", "AISPM-NO-AUTH", "AISPM-ACTION-TOOLS", "AISPM-UNPINNED-MODEL"} <= ids


def test_kubernetes_flags_anonymous_public_cluster():
    from unimonitor.posture import kubernetes

    resources = normalise(SNAPSHOT)["resources"]
    report = kubernetes.analyse(resources)
    ids = {finding["id"] for finding in report["findings"]}
    assert {"K8S-PUBLIC-API", "K8S-ANON-AUTH", "K8S-NO-NETWORK-POLICY", "K8S-NO-AUDIT"} <= ids


def test_paths_chain_identity_to_reachable_store():
    from unimonitor.posture import paths

    document = normalise(SNAPSHOT)
    report = paths.analyse(document["resources"], document["edges"])
    assert report["findings"], "the CI role reaches the public bucket through its declared resources"
    chain = report["findings"][0]
    assert chain["steps"]
    assert chain["severity"] in {"critical", "high"}


def test_analysis_returns_every_engine_and_never_claims_a_score_without_data():
    empty = analyse("aws", {})
    assert set(empty["engines"]) == {"dspm", "ciem", "aispm", "kubernetes", "paths"}
    assert empty["benchmarks"][0]["score"] is None
    assert empty["risk_score"] == 100

    result = analyse("aws", SNAPSHOT)
    assert result["inventory"]["resources"] == 6
    assert result["summary"]["total"] == len(result["findings"])
    assert result["risk_score"] < 100


def test_unknown_platform_returns_no_benchmarks_but_still_analyses():
    result = analyse("nope", SNAPSHOT)
    assert result["benchmarks"] == []
    assert result["findings"]
