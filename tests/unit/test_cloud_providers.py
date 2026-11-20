"""AWS, Google Cloud and Google Workspace collectors + their controls.

SDK/HTTP calls are faked with realistic payloads; the same collector output is
then fed to the control YAML so the assertion covers the whole path.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from unimonitor.graph.collectors import cloud_providers
from unimonitor.grc.control_loader import ControlLoader

CONTROLS = {c.id: c for c in ControlLoader().load_all()}


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def evaluate(control_id: str, data: dict) -> str:
    return CONTROLS[control_id].run_evaluate(data)


# ── AWS double ─────────────────────────────────────────────────────────────


class _BotoClient:
    def __init__(self, spec: dict) -> None:
        self.spec = spec

    def __getattr__(self, name):
        if name in self.spec:
            return lambda **kwargs: self.spec[name]
        raise AttributeError(name)


class _BotoSession:
    def __init__(self, clients: dict) -> None:
        self.clients = clients

    def client(self, name: str):
        if name not in self.clients:
            raise RuntimeError(f"{name} unavailable")
        return _BotoClient(self.clients[name])


AWS_SESSION = _BotoSession(
    {
        "iam": {
            "get_account_summary": {"SummaryMap": {"AccountMFAEnabled": 1}},
            "get_account_password_policy": {
                "PasswordPolicy": {
                    "MinimumPasswordLength": 14,
                    "RequireUppercaseCharacters": True,
                    "RequireLowercaseCharacters": True,
                    "RequireSymbols": True,
                    "RequireNumbers": True,
                    "PasswordReusePrevention": 24,
                }
            },
            "list_users": {"Users": [{"UserName": "alice"}]},
            "list_access_keys": {
                "AccessKeyMetadata": [
                    {
                        "UserName": "alice",
                        "AccessKeyId": "AKIAEXAMPLE",
                        "Status": "Active",
                        "CreateDate": "2026-11-01 00:00:00+00:00",
                    }
                ]
            },
        },
        "s3": {
            "list_buckets": {"Buckets": [{"Name": "logs-bucket"}]},
            "get_public_access_block": {
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True,
                }
            },
            "get_bucket_encryption": {"ServerSideEncryptionConfiguration": {"Rules": [{"ApplyServerSideEncryptionByDefault": {}}]}},
        },
        "cloudtrail": {"describe_trails": {"trailList": [{"Name": "org-trail", "IsMultiRegionTrail": True, "IsLogging": True}]}},
        "guardduty": {"list_detectors": {"DetectorIds": ["det-1"]}},
        "config": {"describe_configuration_recorders": {"ConfigurationRecorders": [{"name": "default", "recording": True}]}},
        "securityhub": {"describe_hub": {"HubArn": "arn:aws:securityhub:us-east-1:1:hub/default"}},
        "ec2": {
            "describe_security_groups": {
                "SecurityGroups": [
                    {
                        "GroupId": "sg-1",
                        "GroupName": "internal",
                        "IpPermissions": [{"FromPort": 443, "ToPort": 443, "IpProtocol": "tcp", "IpRanges": [{"CidrIp": "10.0.0.0/8"}]}],
                    }
                ]
            },
            "describe_flow_logs": {"FlowLogs": [{"ResourceId": "vpc-1", "FlowLogStatus": "ACTIVE"}]},
        },
        "kms": {
            "list_keys": {"Keys": [{"KeyId": "key-1"}]},
            "describe_key": {"KeyMetadata": {"KeyManager": "CUSTOMER", "Enabled": True}},
            "get_key_rotation_status": {"KeyRotationEnabled": True},
        },
        "ssm": {
            "describe_instance_information": {"InstanceInformationList": [{"InstanceId": "i-1", "PingStatus": "Online", "IsLatestVersion": True}]}
        },
        "accessanalyzer": {"list_analyzers": {"analyzers": [{"name": "default", "status": "ACTIVE"}]}},
        "organizations": {"list_policies": {"Policies": [{"Name": "guardrails", "Type": "SERVICE_CONTROL_POLICY"}]}},
    }
)


@pytest.fixture(scope="module")
def aws_data() -> dict:
    return _run(cloud_providers.collect_aws(session=AWS_SESSION))


def test_aws_collector_maps_sources(aws_data):
    assert aws_data["aws_root_mfa_enabled"] is True
    assert aws_data["aws_s3_buckets"][0]["Name"] == "logs-bucket"
    assert aws_data["aws_cloudtrail_trails"][0]["IsLogging"] is True
    assert aws_data["aws_securityhub_enabled"] is True


def test_aws_controls_evaluate(aws_data):
    for cid in (
        "CTRL-AWS-001",
        "CTRL-AWS-002",
        "CTRL-AWS-003",
        "CTRL-AWS-004",
        "CTRL-AWS-005",
        "CTRL-AWS-006",
        "CTRL-AWS-007",
        "CTRL-AWS-008",
        "CTRL-AWS-009",
        "CTRL-AWS-010",
        "CTRL-AWS-011",
        "CTRL-AWS-012",
        "CTRL-AWS-013",
        "CTRL-AWS-014",
    ):
        assert evaluate(cid, aws_data) == "implemented", cid


def test_aws_zero_trust_controls_detect_gaps(aws_data):
    assert (
        evaluate(
            "CTRL-AWS-009",
            {**aws_data, "aws_security_groups": [{"GroupId": "sg-open", "IpPermissions": [{"FromPort": 22, "ToPort": 22, "Cidrs": ["0.0.0.0/0"]}]}]},
        )
        == "not_implemented"
    )
    assert evaluate("CTRL-AWS-010", {**aws_data, "aws_flow_logs": []}) == "not_implemented"
    assert evaluate("CTRL-AWS-011", {**aws_data, "aws_kms_keys": [{"KeyId": "k", "Enabled": True, "RotationEnabled": False}]}) == "not_implemented"
    assert (
        evaluate(
            "CTRL-AWS-013", {**aws_data, "aws_managed_instances": [{"InstanceId": "i", "PingStatus": "ConnectionLost", "IsLatestVersion": False}]}
        )
        == "not_implemented"
    )


def test_aws_controls_detect_failure():
    data = {"aws_root_mfa_enabled": False, "aws_s3_buckets": [{"Name": "open", "PublicAccessBlock": {}, "Encryption": {}}]}
    assert evaluate("CTRL-AWS-001", data) == "not_implemented"
    assert evaluate("CTRL-AWS-004", data) == "not_implemented"


def test_aws_without_sdk_returns_empty(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == "boto3":
            raise ImportError("no boto3")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    assert _run(cloud_providers.collect_aws()) == {}


# ── Google REST double ─────────────────────────────────────────────────────


class _FakeHTTP:
    def __init__(self, routes: dict) -> None:
        self.routes = routes
        self.calls: list[str] = []

    async def get(self, url, headers=None, params=None):
        self.calls.append(url)
        for needle, payload in self.routes.items():
            if needle in url:
                return SimpleNamespace(status_code=200, json=lambda p=payload: p)
        return SimpleNamespace(status_code=404, json=lambda: {})

    async def aclose(self):
        return None


GCP_ROUTES = {
    "getIamPolicy": {"bindings": [{"role": "roles/viewer", "members": ["user:analyst@example.com"]}]},
    # most specific first: the keys URL contains /serviceAccounts
    "/keys": {"keys": [{"name": "k1", "keyType": "USER_MANAGED", "validAfterTime": "2026-01-01T00:00:00Z"}]},
    "/serviceAccounts": {"accounts": [{"email": "svc@proj.iam.gserviceaccount.com"}]},
    "global/firewalls": {
        "items": [
            {
                "name": "allow-internal-ssh",
                "direction": "INGRESS",
                "sourceRanges": ["10.0.0.0/8"],
                "allowed": [{"IPProtocol": "tcp", "ports": ["22"]}],
            }
        ]
    },
    "sinks": {"sinks": [{"name": "central", "destination": "storage.googleapis.com/audit-bucket"}]},
    "/b/proj": {
        "items": [
            {
                "name": "bucket-1",
                "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}},
                "encryption": {"defaultKmsKeyName": "kms/key"},
            }
        ]
    },
    "cryptoKeys": {"cryptoKeys": [{"name": "key-a", "rotationPeriod": "7776000s"}]},
    "getOrgPolicy": {"constraints": [{"name": "constraints/compute.requireShieldedVm"}]},
    "aggregated/subnetworks": {"items": {"regions/us-central1": {"subnetworks": [{"name": "sn-1", "enableFlowLogs": True}]}}},
    "global/backendServices": {"items": [{"name": "internal-app", "iap": {"enabled": True}}]},
    "securitycenter.googleapis.com": {"sources": [{"name": "organizations/1/sources/2", "displayName": "built-in"}]},
    "accessLevels": {"accessLevels": [{"name": "corp-network"}]},
    "servicePerimeters": {"servicePerimeters": [{"name": "sensitive", "status": {"resources": ["projects/1"]}}]},
    "accessPolicies": {"accessPolicies": [{"name": "accessPolicies/1"}]},
}


@pytest.fixture(scope="module")
def gcp_data() -> dict:
    return _run(cloud_providers.collect_gcp(project_id="proj", token="tok", client=_FakeHTTP(GCP_ROUTES)))


def test_gcp_collector_maps_sources(gcp_data):
    assert gcp_data["gcp_project_iam_bindings"][0]["role"] == "roles/viewer"
    assert gcp_data["gcp_service_account_keys"][0]["keyType"] == "USER_MANAGED"
    assert gcp_data["gcp_audit_log_sinks"][0]["destination"].startswith("storage")


def test_gcp_controls_evaluate(gcp_data):
    for cid in (
        "CTRL-GCP-001",
        "CTRL-GCP-003",
        "CTRL-GCP-004",
        "CTRL-GCP-005",
        "CTRL-GCP-006",
        "CTRL-GCP-007",
        "CTRL-GCP-008",
        "CTRL-GCP-009",
        "CTRL-GCP-010",
        "CTRL-GCP-011",
        "CTRL-GCP-012",
    ):
        assert evaluate(cid, gcp_data) == "implemented", cid
    # the sample has one user-managed key: reported as partial, not a pass
    assert evaluate("CTRL-GCP-002", gcp_data) == "partially_implemented"
    assert evaluate("CTRL-GCP-002", {"gcp_service_account_keys": []}) == "implemented"


def test_gcp_control_flags_internet_ssh():
    data = {"gcp_firewall_rules": [{"name": "open-ssh", "direction": "INGRESS", "sourceRanges": ["0.0.0.0/0"], "allowed": [{"ports": ["22"]}]}]}
    assert evaluate("CTRL-GCP-003", data) == "not_implemented"


def test_gcp_without_token_returns_empty():
    assert _run(cloud_providers.collect_gcp(project_id="proj", token="", client=_FakeHTTP({}))) == {}


# ── Google Workspace ───────────────────────────────────────────────────────

GWS_ROUTES = {
    "users/all/tokens": {"items": [{"clientId": "c1", "displayText": "Calendar App", "scopes": ["openid"], "userKey": "a@x.com"}]},
    "/users": {
        "users": [
            {
                "primaryEmail": "a@x.com",
                "isEnrolledIn2Sv": True,
                "isEnforcedIn2Sv": True,
                "isAdmin": True,
                "isDelegatedAdmin": False,
            },
            {
                "primaryEmail": "b@x.com",
                "isEnrolledIn2Sv": True,
                "isEnforcedIn2Sv": True,
                "isAdmin": False,
            },
        ]
    },
    "/roles": {"items": [{"roleName": "Help Desk", "rolePrivileges": [{"privilegeName": "VIEW"}]}]},
    "drive/v2": {"externalSharingAllowed": False, "allowAnyOneAccess": False},
    "devices/mobile": {"mobiledevices": [{"status": "APPROVED", "model": "Pixel"}]},
}


@pytest.fixture(scope="module")
def gws_data() -> dict:
    return _run(cloud_providers.collect_google_workspace(token="tok", customer="C0123", client=_FakeHTTP(GWS_ROUTES)))


def test_workspace_collector_maps_sources(gws_data):
    assert gws_data["gws_two_step_enforcement"]["enforced"] is True
    assert len(gws_data["gws_super_admins"]) == 1
    assert gws_data["gws_drive_sharing_settings"]["allowAnyone"] is False


def test_workspace_controls_evaluate(gws_data):
    for cid in ("CTRL-GWS-001", "CTRL-GWS-002", "CTRL-GWS-003", "CTRL-GWS-004", "CTRL-GWS-005", "CTRL-GWS-006"):
        assert evaluate(cid, gws_data) == "implemented", cid


def test_workspace_flags_external_sharing_and_high_risk_oauth():
    data = {
        "gws_drive_sharing_settings": {"allowAnyone": True, "allowExternalSharing": True},
        "gws_oauth_tokens": [{"clientId": "c9", "displayText": "Mail Sync", "scopes": ["https://mail.google.com/"]}],
        "gws_two_step_enforcement": {"enforced": False, "enrollmentPct": 20},
    }
    assert evaluate("CTRL-GWS-001", data) == "not_implemented"
    assert evaluate("CTRL-GWS-004", data) == "partially_implemented"
    assert evaluate("CTRL-GWS-005", data) == "not_implemented"


def test_workspace_without_token_returns_empty():
    assert _run(cloud_providers.collect_google_workspace(token="", client=_FakeHTTP({}))) == {}
