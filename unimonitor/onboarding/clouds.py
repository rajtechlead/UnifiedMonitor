"""Credential collection and live validation for AWS, Google Cloud and Workspace.

Each validator answers one question the setup wizard cares about: given what the
administrator just pasted, can UniMonitor actually read this cloud? The answer comes
from a real API call against the account, not a format check.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from unimonitor.core.logging import get_logger
from unimonitor.onboarding.google_auth import (
    GCP_SCOPES,
    WORKSPACE_SCOPES,
    GoogleAuthError,
    mint_access_token,
)

logger = get_logger(__name__)


class CloudError(RuntimeError):
    """A platform rejected the credentials the administrator supplied."""


async def validate_aws(
    region: str,
    access_key_id: str,
    secret_access_key: str,
    session_token: str | None = None,
) -> str:
    """Return the AWS account id for these keys (STS GetCallerIdentity)."""
    if not (access_key_id and secret_access_key):
        raise CloudError("An access key ID and secret access key are required.")
    try:
        import boto3
    except ImportError as exc:
        raise CloudError("The AWS SDK (boto3) is not installed. Install it with: pip install 'unimonitor[production]'") from exc

    def _call() -> str:
        session = boto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            aws_session_token=session_token or None,
            region_name=region or "us-east-1",
        )
        try:
            return session.client("sts").get_caller_identity()["Account"]
        except Exception as exc:  # noqa: BLE001 — every botocore error means the same thing here
            raise CloudError(f"AWS rejected those credentials: {exc}") from exc

    return await asyncio.to_thread(_call)


def _boto3() -> Any:
    try:
        import boto3
    except ImportError as exc:
        raise CloudError("The AWS SDK (boto3) is not installed. Install it with: pip install 'unimonitor[production]'") from exc
    return boto3


async def validate_aws_role(
    role_arn: str,
    region: str = "us-east-1",
    external_id: str = "",
    session_name: str = "unimonitor-setup",
) -> str:
    """Assume the administrator's IAM role and return the account it belongs to.

    This is the SSO path: the administrator creates one role that trusts UniMonitor
    (or the federated identity it runs under) instead of handing out long-lived
    per-person access keys.
    """
    if not role_arn.startswith("arn:aws:iam::") or ":role/" not in role_arn:
        raise CloudError("An IAM role ARN looks like arn:aws:iam::123456789012:role/UniMonitorReadOnly.")

    creds = await assume_role_credentials(role_arn, external_id, region, session_name)
    return creds["aws_account_id"]


async def assume_role_credentials(
    role_arn: str,
    external_id: str = "",
    region: str = "us-east-1",
    session_name: str = "unimonitor",
) -> dict[str, str]:
    """Assume a role with the ambient credential chain and return temporary keys."""
    boto3 = _boto3()

    def _call() -> dict[str, str]:
        try:
            sts = boto3.Session(region_name=region or "us-east-1").client("sts")
            kwargs: dict[str, str] = {"RoleArn": role_arn, "RoleSessionName": session_name}
            if external_id:
                kwargs["ExternalId"] = external_id
            assumed = sts.assume_role(**kwargs)["Credentials"]
            identity = (
                boto3.Session(
                    aws_access_key_id=assumed["AccessKeyId"],
                    aws_secret_access_key=assumed["SecretAccessKey"],
                    aws_session_token=assumed["SessionToken"],
                    region_name=region or "us-east-1",
                )
                .client("sts")
                .get_caller_identity()
            )
        except Exception as exc:  # noqa: BLE001 — every botocore error means the same thing here
            raise CloudError(f"AWS could not assume {role_arn}: {exc}") from exc
        return {
            "aws_access_key_id": assumed["AccessKeyId"],
            "aws_secret_access_key": assumed["SecretAccessKey"],
            "aws_session_token": assumed["SessionToken"],
            "region_name": region or "us-east-1",
            "aws_account_id": identity.get("Account", ""),
        }

    return await asyncio.to_thread(_call)


async def _google_token(
    credentials_json: str,
    scopes: str,
    subject: str | None,
    access_token: str | None,
) -> str:
    if access_token:
        return access_token
    if not credentials_json:
        raise CloudError("Paste a service-account JSON key or an access token.")
    try:
        return await mint_access_token(credentials_json, scopes, subject=subject)
    except GoogleAuthError as exc:
        raise CloudError(str(exc)) from exc


async def validate_gcp(
    project_id: str,
    credentials_json: str = "",
    access_token: str = "",
    client: httpx.AsyncClient | None = None,
) -> str:
    """Return the project's display name once Google confirms read access."""
    if not project_id:
        raise CloudError("A Google Cloud project ID is required.")
    token = await _google_token(credentials_json, GCP_SCOPES, None, access_token or None)
    owned = client is None
    http = client or httpx.AsyncClient(timeout=20)
    try:
        resp = await http.get(
            f"https://cloudresourcemanager.googleapis.com/v1/projects/{project_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code >= 400:
            raise CloudError(f"Google Cloud rejected the credentials ({resp.status_code}): {resp.text[:200]}")
        data = resp.json()
        if data.get("lifecycleState") not in (None, "ACTIVE"):
            raise CloudError(f"Project {project_id} is {data['lifecycleState']}.")
        return data.get("name") or project_id
    finally:
        if owned:
            await http.aclose()


async def validate_workspace(
    admin_email: str,
    customer_id: str = "my_customer",
    credentials_json: str = "",
    access_token: str = "",
    client: httpx.AsyncClient | None = None,
) -> str:
    """Return the Workspace customer id after a Directory API read.

    Domain-wide delegation needs the administrator's address: the service account
    impersonates it, which is why this cannot be inferred from the key.
    """
    if not admin_email:
        raise CloudError("A Google Workspace administrator email is required for domain-wide delegation.")
    token = await _google_token(credentials_json, WORKSPACE_SCOPES, admin_email, access_token or None)
    owned = client is None
    http = client or httpx.AsyncClient(timeout=20)
    try:
        resp = await http.get(
            "https://admin.googleapis.com/admin/directory/v1/users",
            headers={"Authorization": f"Bearer {token}"},
            params={"customer": customer_id or "my_customer", "maxResults": 1},
        )
        if resp.status_code >= 400:
            raise CloudError(
                f"Google Workspace rejected the credentials ({resp.status_code}): {resp.text[:200]}"
                " — check the domain-wide delegation scopes on the service account."
            )
        return customer_id or "my_customer"
    finally:
        if owned:
            await http.aclose()
