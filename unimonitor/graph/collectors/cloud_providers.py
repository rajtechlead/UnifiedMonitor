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


def _aws_snapshot(session: Any) -> dict[str, Any]:
    """Blocking boto3 calls; runs in a worker thread."""
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

    try:
        s3 = session.client("s3")
        buckets = []
        for bucket in s3.list_buckets().get("Buckets", []):
            name = bucket.get("Name", "")
            row: dict[str, Any] = {"Name": name}
            try:
                row["PublicAccessBlock"] = s3.get_public_access_block(Bucket=name).get("PublicAccessBlockConfiguration", {})
            except Exception:  # noqa: BLE001
                row["PublicAccessBlock"] = {}
            try:
                row["Encryption"] = s3.get_bucket_encryption(Bucket=name).get("ServerSideEncryptionConfiguration", {})
            except Exception:  # noqa: BLE001
                row["Encryption"] = {}
            buckets.append(row)
        data["aws_s3_buckets"] = buckets
    except Exception as exc:  # noqa: BLE001
        logger.debug("AWS S3 failed", error=str(exc))

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


async def collect_aws(session: Any = None) -> dict[str, Any]:
    """Collect AWS posture via boto3 (default credential chain when no session)."""
    try:
        import boto3
    except ImportError:
        logger.info("boto3 not installed; AWS collector skipped")
        return {}

    if session is None:
        try:
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


async def collect_gcp(
    project_id: str | None = None,
    token: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Collect GCP IAM, firewall, audit, storage and KMS posture."""
    settings = get_settings()
    token = token if token is not None else settings.GCP_ACCESS_TOKEN
    project_id = project_id or settings.GCP_PROJECT_ID
    if not token or not project_id:
        return {}

    data: dict[str, Any] = {}
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=20)

    try:
        policy = await _rest(client, f"{GCP_BASE}/projects/{project_id}:getIamPolicy", token)
        if policy:
            bindings = []
            for binding in policy.get("bindings", []):
                bindings.append({"role": binding.get("role", ""), "members": binding.get("members", [])})
            data["gcp_project_iam_bindings"] = bindings

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
        if emissions := keys:
            data["gcp_service_account_keys"] = emissions

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

        sinks = await _rest(client, f"{GCP_BASE.replace('resourcemanager', 'logging')}/projects/{project_id}/sinks", token)
        if sinks:
            data["gcp_audit_log_sinks"] = [
                {"name": s.get("name", ""), "destination": s.get("destination", ""), "filter": s.get("filter", "")} for s in sinks.get("sinks", [])
            ]

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

        org_policies = await _rest(client, f"{GCP_BASE}/projects/{project_id}:getOrgPolicy", token)
        if org_policies:
            data["gcp_org_policies"] = org_policies.get("constraints", [])

        subnetworks = await _rest(client, f"{GCP_COMPUTE}/projects/{project_id}/aggregated/subnetworks", token)
        if subnetworks:
            data["gcp_subnetworks"] = list(subnetworks.get("items", {}).values())
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
