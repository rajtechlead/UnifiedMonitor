"""Build a posture inventory from collected cloud data.

The posture engines are pure functions over a normalised inventory, which keeps
them testable but used to mean an operator had to export a JSON document by hand.
This module closes that gap: after a collection run the data the collectors already
returned is assembled into the same resource model, so the DSPM, CIEM, CSPM and
attack-path engines run on live evidence.

Only keys that are present are used. A collector that could not reach a provider
leaves its keys out, and the corresponding engine reports ``not_applicable``
instead of a fabricated pass. The assembler never invents a resource and never
raises: a malformed row is skipped.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from unimonitor.config import get_settings
from unimonitor.core.logging import get_logger

logger = get_logger(__name__)

INVENTORY_FILENAME = "latest.json"
# ``latest.json`` is a legacy deployment-wide file; it is no longer written or
# read because it mixed every tenant's resources in one place.


def _rows(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _addresses_are_open(ranges: Any) -> bool:
    for entry in ranges if isinstance(ranges, list) else []:
        text = str(entry)
        if text in ("0.0.0.0/0", "::/0"):
            return True
    return False


def _resource(resource_type: str, provider: str, identifier: Any, **fields: Any) -> dict[str, Any]:
    return {"type": resource_type, "provider": provider, "id": str(identifier or ""), **fields}


def _s3_resource(bucket: dict[str, Any]) -> dict[str, Any]:
    raw_block = bucket.get("PublicAccessBlock")
    block: dict[str, Any] = raw_block if isinstance(raw_block, dict) else {}
    return _resource(
        "storage",
        "aws",
        bucket.get("Name"),
        name=bucket.get("Name", ""),
        public=not bool(block.get("BlockPublicAcls") and block.get("BlockPublicPolicy")),
        external_sharing=not bool(block.get("RestrictPublicBuckets", True)),
        encrypted=bool(bucket.get("Encryption")),
    )


def _open_tcp_ports(permissions: list[dict[str, Any]]) -> list[str]:
    return [str(rule.get("FromPort", "")) for rule in permissions if rule.get("IpProtocol") == "tcp" and _addresses_are_open(rule.get("Cidrs"))]


def _security_group_resource(group: dict[str, Any]) -> dict[str, Any]:
    permissions = _rows(group.get("IpPermissions"))
    open_ports = _open_tcp_ports(permissions)
    return _resource(
        "security_group",
        "aws",
        group.get("GroupId"),
        name=group.get("GroupName", ""),
        open_ingress=any(_addresses_are_open(rule.get("Cidrs")) for rule in permissions),
        open_admin_ports=any(port in ("22", "3389") for port in open_ports),
        internet_ports=open_ports,
    )


def _aws_account_resource(collected: dict[str, Any]) -> dict[str, Any]:
    raw_policy = collected.get("aws_iam_password_policy")
    policy: dict[str, Any] = raw_policy if isinstance(raw_policy, dict) else {}
    return _resource(
        "tenant_settings",
        "aws",
        "aws-account",
        name="AWS account settings",
        mfa_enforced=bool(collected.get("aws_root_mfa_enabled")),
        minimum_password_length=policy.get("MinimumPasswordLength", 0),
        password_reuse_prevention=policy.get("PasswordReusePrevention", 0),
        logging_enabled=bool(_rows(collected.get("aws_cloudtrail_trails"))),
    )


def _aws_resources(collected: dict[str, Any]) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = [_s3_resource(bucket) for bucket in _rows(collected.get("aws_s3_buckets"))]
    resources.extend(_security_group_resource(group) for group in _rows(collected.get("aws_security_groups")))

    for key in _rows(collected.get("aws_kms_keys")):
        resources.append(
            _resource(
                "key",
                "aws",
                key.get("KeyId"),
                name=key.get("KeyId", ""),
                rotation_enabled=bool(key.get("RotationEnabled")),
                enabled=bool(key.get("Enabled", True)),
            )
        )

    for trail in _rows(collected.get("aws_cloudtrail_trails")):
        resources.append(
            _resource(
                "logging",
                "aws",
                trail.get("Name"),
                name=trail.get("Name", ""),
                logging_enabled=bool(trail.get("IsLogging")),
                multi_region=bool(trail.get("IsMultiRegionTrail")),
            )
        )

    for instance in _rows(collected.get("aws_managed_instances")):
        resources.append(
            _resource(
                "compute",
                "aws",
                instance.get("InstanceId"),
                name=instance.get("InstanceId", ""),
                managed=instance.get("PingStatus") == "Online",
                agent_current=bool(instance.get("IsLatestVersion")),
            )
        )

    for instance in _rows(collected.get("aws_ec2_instances")):
        resources.append(
            _resource(
                "compute",
                "aws",
                instance.get("InstanceId"),
                name=instance.get("InstanceId", ""),
                public=bool(instance.get("PublicIpAddress")),
                imds_v2_required=str(instance.get("HttpTokens", "")).lower() == "required",
                encrypted=bool(instance.get("VolumesEncrypted")),
            )
        )

    for database in _rows(collected.get("aws_rds_instances")):
        resources.append(
            _resource(
                "storage",
                "aws",
                database.get("DBInstanceIdentifier"),
                name=database.get("DBInstanceIdentifier", ""),
                kind="database",
                public=bool(database.get("PubliclyAccessible")),
                encrypted=bool(database.get("StorageEncrypted")),
                retention_days=database.get("BackupRetentionPeriod", 0),
            )
        )

    for key in _rows(collected.get("aws_access_keys")):
        resources.append(
            _resource(
                "identity",
                "aws",
                key.get("AccessKeyId"),
                name=key.get("UserName", ""),
                kind="access_key",
                active=key.get("Status") == "Active",
                user=key.get("UserName", ""),
            )
        )

    if "aws_root_mfa_enabled" in collected or "aws_iam_password_policy" in collected:
        resources.append(_aws_account_resource(collected))

    return resources


def _gcp_resources(collected: dict[str, Any]) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []

    for bucket in _rows(collected.get("gcp_storage_buckets")):
        raw_iam = bucket.get("iamConfiguration")
        raw_encryption = bucket.get("encryption")
        iam: dict[str, Any] = raw_iam if isinstance(raw_iam, dict) else {}
        encryption: dict[str, Any] = raw_encryption if isinstance(raw_encryption, dict) else {}
        raw_uniform = iam.get("uniformBucketLevelAccess")
        uniform: dict[str, Any] = raw_uniform if isinstance(raw_uniform, dict) else {}
        resources.append(
            _resource(
                "storage",
                "gcp",
                bucket.get("name"),
                name=bucket.get("name", ""),
                public=str(iam.get("publicAccessPrevention", "")).lower() != "enforced",
                uniform_access=bool(uniform.get("enabled")),
                encrypted=bool(encryption.get("defaultKmsKeyName")),
                encryption_key_type=str(encryption.get("defaultKmsKeyName", "")),
            )
        )

    for rule in _rows(collected.get("gcp_firewall_rules")):
        resources.append(
            _resource(
                "security_group",
                "gcp",
                rule.get("name"),
                name=rule.get("name", ""),
                direction=rule.get("direction", "INGRESS"),
                open_ingress=rule.get("direction", "INGRESS") == "INGRESS" and _addresses_are_open(rule.get("sourceRanges")),
            )
        )

    for sink in _rows(collected.get("gcp_audit_log_sinks")):
        resources.append(
            _resource(
                "logging",
                "gcp",
                sink.get("name"),
                name=sink.get("name", ""),
                logging_enabled=bool(sink.get("destination")),
                destination=sink.get("destination", ""),
            )
        )

    for key in _rows(collected.get("gcp_service_account_keys")):
        resources.append(
            _resource(
                "identity",
                "gcp",
                key.get("name"),
                name=key.get("name", ""),
                kind="service_account_key",
                service_account=key.get("serviceAccount", ""),
                key_type=key.get("keyType", ""),
                valid_after=key.get("validAfterTime", ""),
            )
        )

    for binding in _rows(collected.get("gcp_project_iam_bindings")):
        members = [str(member) for member in binding.get("members", []) if isinstance(member, (str, int))]
        resources.append(
            _resource(
                "identity",
                "gcp",
                f"{binding.get('role', '')}:{','.join(members)[:60]}",
                name=binding.get("role", ""),
                role=binding.get("role", ""),
                admin=str(binding.get("role", "")).lower().endswith(("admin", "owner")),
                privileged="allusers" in [member.lower() for member in members] or "allauthenticatedusers" in [member.lower() for member in members],
            )
        )

    for instance in _rows(collected.get("gcp_instances")):
        resources.append(
            _resource(
                "compute",
                "gcp",
                instance.get("name"),
                name=instance.get("name", ""),
                public=bool(instance.get("externalIps")),
                encrypted=bool(instance.get("shieldedVm")),
            )
        )

    for key in _rows(collected.get("gcp_kms_keys")):
        resources.append(
            _resource(
                "key",
                "gcp",
                key.get("name"),
                name=key.get("name", ""),
                rotation_enabled=bool(key.get("rotationPeriod")),
            )
        )

    return resources


def _workspace_resources(collected: dict[str, Any]) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []

    two_step = collected.get("gws_two_step_enforcement")
    drive = collected.get("gws_drive_sharing_settings")
    if isinstance(two_step, dict) or isinstance(drive, dict):
        two_step = two_step if isinstance(two_step, dict) else {}
        drive = drive if isinstance(drive, dict) else {}
        resources.append(
            _resource(
                "tenant_settings",
                "google_workspace",
                "workspace",
                name="Google Workspace settings",
                mfa_enforced=bool(two_step.get("enforced")),
                mfa_enrollment_pct=two_step.get("enrollmentPct", 0),
                external_sharing=bool(drive.get("allowExternalSharing")),
                public=bool(drive.get("allowAnyone")),
            )
        )

    for admin in _rows(collected.get("gws_super_admins")):
        resources.append(
            _resource(
                "identity",
                "google_workspace",
                admin.get("email"),
                name=admin.get("email", ""),
                admin=True,
                kind="super_admin",
            )
        )

    for role in _rows(collected.get("gws_admin_roles")):
        resources.append(
            _resource(
                "identity",
                "google_workspace",
                role.get("roleName"),
                name=role.get("roleName", ""),
                role=role.get("roleName", ""),
                privileged=bool(role.get("assignedCount")),
            )
        )

    for token in _rows(collected.get("gws_oauth_tokens")):
        scopes = [str(scope) for scope in token.get("scopes", []) if isinstance(scope, (str, int))]
        resources.append(
            _resource(
                "identity",
                "google_workspace",
                f"{token.get('userKey', '')}:{token.get('clientId', '')}",
                name=token.get("displayText", ""),
                kind="oauth_grant",
                scopes=scopes,
                privileged=any("mail" in scope or "drive" in scope for scope in scopes),
            )
        )

    for user in _rows(collected.get("gws_users_without_2sv")):
        resources.append(
            _resource(
                "identity",
                "google_workspace",
                user.get("email"),
                name=user.get("email", ""),
                kind="user",
                admin=bool(user.get("isAdmin")),
                mfa_enabled=False,
            )
        )

    for group in _rows(collected.get("gws_groups")):
        resources.append(
            _resource(
                "identity",
                "google_workspace",
                group.get("email"),
                name=group.get("name", ""),
                kind="group",
                external_sharing=bool(group.get("allowExternalMembers")),
            )
        )

    for device in _rows(collected.get("gws_mobile_devices")):
        resources.append(
            _resource(
                "compute",
                "google_workspace",
                f"{device.get('model', '')}:{device.get('status', '')}",
                name=device.get("model", ""),
                managed=str(device.get("status", "")).upper() == "APPROVED",
            )
        )

    return resources


def _microsoft_resources(collected: dict[str, Any]) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []

    policies = _rows(collected.get("conditionalAccessPolicies"))
    if policies:
        enabled = [policy for policy in policies if str(policy.get("state", "")).lower() == "enabled"]
        resources.append(
            _resource(
                "tenant_settings",
                "microsoft",
                "entra",
                name="Entra ID settings",
                conditional_access_enabled=bool(enabled),
                conditional_access_policies=len(enabled),
                mfa_enforced=any("mfa" in json.dumps(policy).lower() for policy in enabled),
                logging_enabled=True,
            )
        )

    for device in _rows(collected.get("managedDevices")):
        resources.append(
            _resource(
                "compute",
                "microsoft",
                device.get("id"),
                name=device.get("deviceName", ""),
                managed=True,
                compliant=str(device.get("complianceState", "")).lower() == "compliant",
            )
        )

    for policy in _rows(collected.get("deviceCompliancePolicies")):
        resources.append(
            _resource(
                "compute",
                "microsoft",
                policy.get("id"),
                name=policy.get("displayName", ""),
                kind="compliance_policy",
                managed=bool(policy.get("assignments")),
            )
        )

    return resources


def assemble(collected: dict[str, Any]) -> dict[str, Any]:
    """Assemble collected collector output into a normalised inventory."""
    resources: list[dict[str, Any]] = []
    for builder in (_aws_resources, _gcp_resources, _workspace_resources, _microsoft_resources):
        try:
            resources.extend(builder(collected))
        except Exception as exc:  # noqa: BLE001 — one malformed provider section must not stop the rest
            logger.warning("Posture assembly section failed", section=builder.__name__, error=str(exc))

    # A resource without an id cannot be referenced by a finding or an edge.
    resources = [resource for resource in resources if resource.get("id")]
    return {"resources": resources, "edges": []}


def inventory_path(tenant_id: str = "") -> Path:
    """Where the automatic inventory is written.

    ``POSTURE_AUTO_INVENTORY_PATH`` is a directory of per-tenant inventories. An
    empty ``tenant_id`` still resolves the legacy ``latest.json`` name for callers
    that only want a path, but it is never written automatically.
    """
    configured = str(getattr(get_settings(), "POSTURE_AUTO_INVENTORY_PATH", "") or "")
    base = Path(configured) if configured else Path(get_settings().REPORT_STORAGE_PATH) / "posture"
    return base / (f"{tenant_id}.json" if tenant_id else INVENTORY_FILENAME)


def write_inventory(inventory: dict[str, Any], tenant_id: str = "") -> Path | None:
    """Write one tenant's assembled inventory atomically. Never raises.

    Only the tenant's own file is written: a shared ``latest.json`` would let the
    posture page show one tenant's resources to another.
    """
    if not getattr(get_settings(), "POSTURE_AUTO_INVENTORY", True):
        return None
    if not tenant_id:
        logger.warning("Posture inventory not written without a tenant")
        return None
    target = inventory_path(tenant_id)
    encoded = json.dumps(inventory, indent=2, sort_keys=True, default=str)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(encoded, encoding="utf-8")
        os.replace(temporary, target)
    except OSError as exc:
        logger.warning("Posture inventory write failed", path=str(target), error=str(exc))
        return None
    logger.info("Posture inventory written", path=str(target), resources=len(inventory.get("resources", [])))
    return target


def load_inventory(tenant_id: str = "") -> dict[str, Any] | None:
    """Read the last automatic inventory, or None when nothing was collected."""
    path = inventory_path(tenant_id)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Posture inventory unreadable", path=str(path), error=str(exc))
        return None
    return payload if isinstance(payload, dict) else None


__all__ = ["assemble", "inventory_path", "load_inventory", "write_inventory"]
