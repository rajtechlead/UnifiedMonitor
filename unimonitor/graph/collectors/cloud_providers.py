"""Multi-cloud posture collectors: AWS, Google Cloud and Google Workspace.

UniMonitor started Microsoft-only; these collectors extend the same contract —
return the data keys the control YAML reads, never raise, and omit a key when the
provider could not be reached (so controls report ``not_implemented`` rather than
a fabricated pass).

AWS uses boto3 (already an optional ``production`` extra) and the standard
credential chain. Google Cloud and Google Workspace are read over their REST APIs
with an OAuth access token from configuration; no Google SDK is added.

shortcut: Google collectors take a pre-issued access token instead of running the
OAuth/service-account flow, refresh it out of band, upgrade to google-auth when
Workload Identity Federation is required.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from unimonitor.config import get_settings
from unimonitor.core.logging import get_logger

logger = get_logger(__name__)

GCP_BASE = "https://cloudresourcemanager.googleapis.com/v1"
GCP_COMPUTE = "https://compute.googleapis.com/compute/v1"
GCP_STORAGE = "https://storage.googleapis.com/storage/v1"
GCP_KMS = "https://cloudkms.googleapis.com/v1"
GWS_ADMIN = "https://admin.googleapis.com/admin"


# ── AWS ────────────────────────────────────────────────────────────────────


def _aws_iam_snapshot(session: Any) -> dict[str, Any]:
    """Account summary, password policy and user access keys."""
    data: dict[str, Any] = {}

    iam = session.client("iam")
    try:
        summary = iam.get_account_summary().get("SummaryMap", {})
        data["aws_account_summary"] = summary
        # AccountMFAEnabled is 1 only when the root user has MFA.
        data["aws_root_mfa_enabled"] = summary.get("AccountMFAEnabled", 0) == 1
    except Exception as exc:  # noqa: BLE001
        logger.debug("AWS account summary failed", error=str(exc))

    try:
        policy = iam.get_account_password_policy().get("PasswordPolicy", {})
        data["aws_iam_password_policy"] = policy
    except Exception as exc:  # noqa: BLE001
        logger.debug("AWS password policy failed", error=str(exc))

    try:
        keys = []
        for user in iam.list_users().get("Users", []):
            for key in iam.list_access_keys(UserName=user["UserName"]).get("AccessKeyMetadata", []):
                keys.append(
                    {
                        "UserName": key.get("UserName", ""),
                        "AccessKeyId": key.get("AccessKeyId", ""),
                        "Status": key.get("Status", ""),
                        "CreateDate": str(key.get("CreateDate", "")),
                    }
                )
        data["aws_access_keys"] = keys
    except Exception as exc:  # noqa: BLE001
        logger.debug("AWS access keys failed", error=str(exc))

    return data


def _aws_bucket_row(s3: Any, name: str) -> dict[str, Any]:
    """One S3 bucket with its public-access-block and encryption settings."""
    row: dict[str, Any] = {"Name": name}
    try:
        row["PublicAccessBlock"] = s3.get_public_access_block(Bucket=name).get("PublicAccessBlockConfiguration", {})
    except Exception:  # noqa: BLE001
        row["PublicAccessBlock"] = {}
    try:
        row["Encryption"] = s3.get_bucket_encryption(Bucket=name).get("ServerSideEncryptionConfiguration", {})
    except Exception:  # noqa: BLE001
        row["Encryption"] = {}
    return row


def _aws_storage_snapshot(session: Any) -> dict[str, Any]:
    """S3 buckets and their exposure/encryption configuration."""
    data: dict[str, Any] = {}
    try:
        s3 = session.client("s3")
        data["aws_s3_buckets"] = [_aws_bucket_row(s3, bucket.get("Name", "")) for bucket in s3.list_buckets().get("Buckets", [])]
    except Exception as exc:  # noqa: BLE001
        logger.debug("AWS S3 failed", error=str(exc))
    return data


def _aws_audit_snapshot(session: Any) -> dict[str, Any]:
    """CloudTrail, GuardDuty, Config and Security Hub state."""
    data: dict[str, Any] = {}

    try:
        ct = session.client("cloudtrail")
        data["aws_cloudtrail_trails"] = [
            {
                "Name": trail.get("Name", ""),
                "IsMultiRegionTrail": trail.get("IsMultiRegionTrail", False),
                "IsLogging": trail.get("IsLogging", False),
            }
            for trail in ct.describe_trails().get("trailList", [])
        ]
    except Exception as exc:  # noqa: BLE001
        logger.debug("AWS CloudTrail failed", error=str(exc))

    try:
        gd = session.client("guardduty")
        data["aws_guardduty_detectors"] = [{"DetectorId": d, "Status": "ENABLED"} for d in gd.list_detectors().get("DetectorIds", [])]
    except Exception as exc:  # noqa: BLE001
        logger.debug("AWS GuardDuty failed", error=str(exc))

    try:
        cfg = session.client("config")
        data["aws_config_recorders"] = [
            {"name": r.get("name", ""), "recording": r.get("recording", False)}
            for r in cfg.describe_configuration_recorders().get("ConfigurationRecorders", [])
        ]
    except Exception as exc:  # noqa: BLE001
        logger.debug("AWS Config failed", error=str(exc))

    try:
        data["aws_securityhub_enabled"] = bool(session.client("securityhub").describe_hub().get("HubArn"))
    except Exception:  # noqa: BLE001
        data["aws_securityhub_enabled"] = False

    return data


def _aws_network_snapshot(session: Any) -> dict[str, Any]:
    """Security groups, flow logs and customer-managed KMS keys."""
    data: dict[str, Any] = {}

    try:
        ec2 = session.client("ec2")
        data["aws_security_groups"] = [
            {
                "GroupId": group.get("GroupId", ""),
                "GroupName": group.get("GroupName", ""),
                "IpPermissions": [
                    {
                        "FromPort": rule.get("FromPort"),
                        "ToPort": rule.get("ToPort"),
                        "IpProtocol": rule.get("IpProtocol", ""),
                        "Cidrs": [rng.get("CidrIp", "") for rng in rule.get("IpRanges", [])],
                    }
                    for rule in group.get("IpPermissions", [])
                ],
            }
            for group in ec2.describe_security_groups().get("SecurityGroups", [])
        ]
        data["aws_flow_logs"] = [
            {"ResourceId": log.get("ResourceId", ""), "Status": log.get("FlowLogStatus", "")} for log in ec2.describe_flow_logs().get("FlowLogs", [])
        ]
    except Exception as exc:  # noqa: BLE001
        logger.debug("AWS network posture failed", error=str(exc))

    try:
        kms = session.client("kms")
        keys = []
        for entry in kms.list_keys().get("Keys", [])[:100]:
            try:
                metadata = kms.describe_key(KeyId=entry["KeyId"])["KeyMetadata"]
                if metadata.get("KeyManager") != "CUSTOMER":
                    continue
                rotation = kms.get_key_rotation_status(KeyId=entry["KeyId"]).get("KeyRotationEnabled", False)
                keys.append({"KeyId": entry["KeyId"], "Enabled": metadata.get("Enabled", False), "RotationEnabled": rotation})
            except Exception as exc:  # noqa: BLE001
                logger.debug("AWS KMS key skipped", key=entry.get("KeyId"), error=str(exc))
        data["aws_kms_keys"] = keys
    except Exception as exc:  # noqa: BLE001
        logger.debug("AWS KMS failed", error=str(exc))

    return data


def _aws_governance_snapshot(session: Any) -> dict[str, Any]:
    """Systems Manager coverage, Access Analyzer and Organizations policies."""
    data: dict[str, Any] = {}

    try:
        managed = session.client("ssm").describe_instance_information().get("InstanceInformationList", [])
        data["aws_managed_instances"] = [
            {"InstanceId": row.get("InstanceId", ""), "PingStatus": row.get("PingStatus", ""), "IsLatestVersion": row.get("IsLatestVersion", False)}
            for row in managed
        ]
    except Exception as exc:  # noqa: BLE001
        logger.debug("AWS Systems Manager failed", error=str(exc))

    try:
        analyzers = session.client("accessanalyzer").list_analyzers().get("analyzers", [])
        data["aws_access_analyzers"] = [{"name": item.get("name", ""), "status": item.get("status", "")} for item in analyzers]
    except Exception as exc:  # noqa: BLE001
        logger.debug("AWS Access Analyzer failed", error=str(exc))

    try:
        policies = session.client("organizations").list_policies(Filter="SERVICE_CONTROL_POLICY").get("Policies", [])
        data["aws_organization_policies"] = [{"name": item.get("Name", ""), "type": item.get("Type", "")} for item in policies]
    except Exception as exc:  # noqa: BLE001
        logger.debug("AWS Organizations failed", error=str(exc))

    return data


def _aws_snapshot(session: Any) -> dict[str, Any]:
    """Blocking boto3 calls; runs in a worker thread."""
    data: dict[str, Any] = {}
    for section in (_aws_iam_snapshot, _aws_storage_snapshot, _aws_audit_snapshot, _aws_network_snapshot, _aws_governance_snapshot):
        data.update(section(session))
    return data


async def collect_aws(session: Any = None) -> dict[str, Any]:
    """Collect AWS posture via boto3 (default credential chain when no session)."""
    try:
        import boto3
    except ImportError:
        logger.info("boto3 not installed; AWS collector skipped")
        return {}

    if session is None:
        try:
            from unimonitor.onboarding.service import aws_credentials_for

            stored = await aws_credentials_for()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Stored AWS credentials unavailable", error=str(exc))
            stored = None
        try:
            # Credentials from the setup wizard win; otherwise boto3's default chain.
            if stored and stored.get("aws_access_key_id"):
                session = boto3.Session(**stored)
            else:
                session = boto3.Session(region_name=get_settings().AWS_REGION)
        except Exception as exc:  # noqa: BLE001
            logger.warning("AWS session creation failed", error=str(exc))
            return {}

    try:
        return await asyncio.to_thread(_aws_snapshot, session)
    except Exception as exc:  # noqa: BLE001
        logger.warning("AWS collection failed", error=str(exc))
        return {}


# ── Google Cloud ───────────────────────────────────────────────────────────


async def _google_token_from_store(provider: str) -> str:
    """Mint a Google token from the connection saved during setup."""
    try:
        from unimonitor.onboarding.service import google_token_for

        return await google_token_for(provider)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Stored Google credentials unavailable", provider=provider, error=str(exc))
        return ""


async def _rest(client: httpx.AsyncClient, url: str, token: str, params: dict | None = None) -> dict:
    try:
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}"}, params=params or {})
        if resp.status_code != 200:
            return {}
        payload = resp.json()
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:  # noqa: BLE001
        logger.debug("Google REST call failed", url=url, error=str(exc))
        return {}


async def _gcp_identity(client: httpx.AsyncClient, project_id: str, token: str) -> dict[str, Any]:
    """Project IAM bindings and user-managed service-account keys."""
    data: dict[str, Any] = {}

    policy = await _rest(client, f"{GCP_BASE}/projects/{project_id}:getIamPolicy", token)
    if policy:
        data["gcp_project_iam_bindings"] = [
            {"role": binding.get("role", ""), "members": binding.get("members", [])} for binding in policy.get("bindings", [])
        ]

    sa_list = await _rest(client, f"{GCP_BASE}/projects/{project_id}/serviceAccounts", token)
    emails = [sa.get("email", "") for sa in sa_list.get("accounts", [])]
    keys = []
    for email in emails[:50]:
        key_payload = await _rest(client, f"{GCP_BASE}/projects/{project_id}/serviceAccounts/{email}/keys", token)
        for key in key_payload.get("keys", []):
            if str(key.get("keyType", "")).upper().startswith("USER"):
                keys.append(
                    {
                        "name": key.get("name", ""),
                        "keyType": key.get("keyType", ""),
                        "validAfterTime": key.get("validAfterTime", ""),
                        "serviceAccount": email,
                    }
                )
    if keys:
        data["gcp_service_account_keys"] = keys

    return data


async def _gcp_network(client: httpx.AsyncClient, project_id: str, token: str) -> dict[str, Any]:
    """Firewall rules, subnetworks and backend services."""
    data: dict[str, Any] = {}

    firewalls = await _rest(client, f"{GCP_COMPUTE}/projects/{project_id}/global/firewalls", token)
    if firewalls:
        data["gcp_firewall_rules"] = [
            {
                "name": fw.get("name", ""),
                "direction": fw.get("direction", "INGRESS"),
                "sourceRanges": fw.get("sourceRanges", []),
                "allowed": fw.get("allowed", []),
            }
            for fw in firewalls.get("items", [])
        ]

    backends = await _rest(client, f"{GCP_COMPUTE}/projects/{project_id}/global/backendServices", token)
    if backends:
        data["gcp_backend_services"] = [{"name": item.get("name", ""), "iap": item.get("iap", {})} for item in backends.get("items", [])]

    subnetworks = await _rest(client, f"{GCP_COMPUTE}/projects/{project_id}/aggregated/subnetworks", token)
    if subnetworks:
        data["gcp_subnetworks"] = list(subnetworks.get("items", {}).values())

    return data


async def _gcp_logging(client: httpx.AsyncClient, project_id: str, token: str) -> dict[str, Any]:
    """Audit-log sinks and organization policies."""
    data: dict[str, Any] = {}

    sinks = await _rest(client, f"{GCP_BASE.replace('resourcemanager', 'logging')}/projects/{project_id}/sinks", token)
    if sinks:
        data["gcp_audit_log_sinks"] = [
            {"name": s.get("name", ""), "destination": s.get("destination", ""), "filter": s.get("filter", "")} for s in sinks.get("sinks", [])
        ]

    org_policies = await _rest(client, f"{GCP_BASE}/projects/{project_id}:getOrgPolicy", token)
    if org_policies:
        data["gcp_org_policies"] = org_policies.get("constraints", [])

    return data


async def _gcp_storage(client: httpx.AsyncClient, project_id: str, token: str) -> dict[str, Any]:
    """Storage buckets and KMS keys."""
    data: dict[str, Any] = {}

    buckets = await _rest(client, f"{GCP_STORAGE}/b/{project_id}", token)
    if buckets:
        data["gcp_storage_buckets"] = [
            {
                "name": b.get("name", ""),
                "iamConfiguration": b.get("iamConfiguration", {}),
                "encryption": b.get("encryption", {}),
            }
            for b in buckets.get("items", [])
        ]

    kms = await _rest(client, f"{GCP_KMS}/projects/{project_id}/locations/-/keyRings/-/cryptoKeys", token)
    if kms:
        data["gcp_kms_keys"] = [
            {"name": k.get("name", ""), "purpose": k.get("purpose", ""), "rotationPeriod": k.get("rotationPeriod", "")}
            for k in kms.get("cryptoKeys", [])
        ]

    return data


async def _gcp_zero_trust(client: httpx.AsyncClient, project_id: str, token: str) -> dict[str, Any]:
    """Security Command Center sources and Access Context Manager levels."""
    data: dict[str, Any] = {}

    scc = await _rest(client, f"https://securitycenter.googleapis.com/v1/projects/{project_id}/sources", token)
    if scc:
        data["gcp_scc_sources"] = [{"name": item.get("name", ""), "displayName": item.get("displayName", "")} for item in scc.get("sources", [])]

    access_policies = await _rest(client, "https://accesscontextmanager.googleapis.com/v1/accessPolicies", token)
    policies = access_policies.get("accessPolicies", []) if access_policies else []
    if policies:
        policy_name = policies[0].get("name", "")
        data["gcp_access_levels"] = (await _rest(client, f"https://accesscontextmanager.googleapis.com/v1/{policy_name}/accessLevels", token)).get(
            "accessLevels", []
        )
        data["gcp_service_perimeters"] = (
            await _rest(client, f"https://accesscontextmanager.googleapis.com/v1/{policy_name}/servicePerimeters", token)
        ).get("servicePerimeters", [])

    return data


async def collect_gcp(
    project_id: str | None = None,
    token: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Collect GCP IAM, firewall, audit, storage and KMS posture."""
    settings = get_settings()
    token = token if token is not None else settings.GCP_ACCESS_TOKEN
    project_id = project_id or settings.GCP_PROJECT_ID
    if not token:
        token = await _google_token_from_store("gcp")
    if not token or not project_id:
        return {}

    data: dict[str, Any] = {}
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=20)

    try:
        for section in (_gcp_identity, _gcp_network, _gcp_logging, _gcp_storage, _gcp_zero_trust):
            data.update(await section(client, project_id, token))
    finally:
        if owns_client:
            await client.aclose()

    return data


# ── Google Workspace ───────────────────────────────────────────────────────


async def collect_google_workspace(
    token: str | None = None,
    customer: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Collect Workspace 2SV, admin roles, OAuth tokens and sharing posture."""
    settings = get_settings()
    token = token if token is not None else settings.GOOGLE_ACCESS_TOKEN
    customer = customer or settings.GOOGLE_WORKSPACE_CUSTOMER_ID or "my_customer"
    if not token:
        token = await _google_token_from_store("google_workspace")
    if not token:
        return {}

    data: dict[str, Any] = {}
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=20)

    try:
        users = await _rest(client, f"{GWS_ADMIN}/directory/v1/users", token, {"customer": customer, "maxResults": 200})
        user_rows = users.get("users", [])
        if user_rows:
            enrolled = [u for u in user_rows if u.get("isEnrolledIn2Sv") is True]
            data["gws_two_step_enforcement"] = {
                "enforced": bool(user_rows) and all(u.get("isEnforcedIn2Sv") is True for u in user_rows),
                "enrollmentPct": round(len(enrolled) / len(user_rows) * 100, 1),
            }
            data["gws_super_admins"] = [
                {"email": u.get("primaryEmail", "")} for u in user_rows if u.get("isAdmin") is True and u.get("isDelegatedAdmin") is False
            ]

        roles = await _rest(client, f"{GWS_ADMIN}/directory/v1/customer/{customer}/roles", token)
        if roles:
            data["gws_admin_roles"] = [
                {"roleName": r.get("roleName", ""), "assignedCount": r.get("rolePrivileges") and len(r.get("rolePrivileges")) or 0}
                for r in roles.get("items", [])
            ]

        tokens = await _rest(client, f"{GWS_ADMIN}/directory/v1/users/all/tokens", token, {"customer": customer})
        if tokens.get("items") is not None:
            data["gws_oauth_tokens"] = [
                {
                    "clientId": t.get("clientId", ""),
                    "displayText": t.get("displayText", ""),
                    "scopes": t.get("scopes", []),
                    "userKey": t.get("userKey", ""),
                }
                for t in tokens.get("items", [])
            ]

        drive_settings = await _rest(client, f"{GWS_ADMIN}/drive/v2/customer/{customer}/settings", token)
        if drive_settings:
            data["gws_drive_sharing_settings"] = {
                "allowExternalSharing": drive_settings.get("externalSharingAllowed", False),
                "allowAnyone": drive_settings.get("allowAnyOneAccess", False),
            }

        gmail = await _rest(client, f"{GWS_ADMIN}/directory/v1/customer/{customer}/devices/mobile", token)
        if gmail:
            data["gws_mobile_devices"] = [{"status": d.get("status", ""), "model": d.get("model", "")} for d in gmail.get("mobiledevices", [])]
    finally:
        if owns_client:
            await client.aclose()

    return data
