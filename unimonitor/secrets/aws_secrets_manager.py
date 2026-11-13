"""
AWS Secrets Manager secret provider.

Requires:
    pip install boto3

Authentication (boto3 standard chain):
  1. Environment variables (AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY)
  2. ~/.aws/credentials
  3. IAM Role (EC2 / ECS task role / Lambda)
  4. IAM Identity Center (SSO)
"""

from __future__ import annotations

import time

from unimonitor.core.logging import get_logger
from unimonitor.secrets.provider import HealthStatus, ProviderType, SecretMetadata

logger = get_logger(__name__)


class AWSSecretsManagerProvider:
    """AWS Secrets Manager implementation of the SecretProvider protocol."""

    provider_type = ProviderType.AWS_SECRETS_MANAGER

    def __init__(self, region_name: str = "us-east-1", endpoint_url: str | None = None) -> None:
        """
        Args:
            region_name: AWS region, e.g. "us-east-1"
            endpoint_url: Override endpoint (useful for LocalStack in tests)
        """
        try:
            import boto3
        except ImportError as exc:
            raise ImportError("AWS Secrets Manager support requires: pip install boto3") from exc

        import boto3

        kwargs: dict = {"region_name": region_name}
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url

        self._client = boto3.client("secretsmanager", **kwargs)
        self._region = region_name
        logger.info("AWS Secrets Manager provider initialized", region=region_name)

    async def get_secret(self, name: str, version: str | None = None) -> str:
        """Retrieve a secret. Raises KeyError if not found."""
        import asyncio

        from botocore.exceptions import ClientError

        kwargs: dict = {"SecretId": name}
        if version:
            kwargs["VersionId"] = version

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: self._client.get_secret_value(**kwargs))
            if "SecretString" in response:
                return response["SecretString"]
            # Binary secret — decode as UTF-8
            import base64

            return base64.b64decode(response["SecretBinary"]).decode("utf-8")
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("ResourceNotFoundException", "InvalidRequestException"):
                raise KeyError(f"Secret '{name}' not found in AWS Secrets Manager ({self._region})") from exc
            logger.error("AWS SM get_secret failed", name=name, error=str(exc))
            raise

    async def set_secret(self, name: str, value: str, tags: dict[str, str] | None = None) -> SecretMetadata:
        """Create or update a secret value."""
        import asyncio

        from botocore.exceptions import ClientError

        loop = asyncio.get_event_loop()
        try:
            # Try update first (cheaper)
            response = await loop.run_in_executor(
                None,
                lambda: self._client.put_secret_value(SecretId=name, SecretString=value),
            )
            version = response.get("VersionId")
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ResourceNotFoundException":
                # Create new secret
                create_kwargs: dict = {"Name": name, "SecretString": value}
                if tags:
                    create_kwargs["Tags"] = [{"Key": k, "Value": v} for k, v in tags.items()]
                response = await loop.run_in_executor(None, lambda: self._client.create_secret(**create_kwargs))
                version = response.get("VersionId")
            else:
                raise

        return SecretMetadata(
            name=name,
            provider=self.provider_type,
            version=version,
            tags=tags or {},
        )

    async def delete_secret(self, name: str, recovery_window_days: int = 7) -> None:
        """Schedule secret deletion. Default recovery window = 7 days."""
        import asyncio

        from botocore.exceptions import ClientError

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._client.delete_secret(SecretId=name, RecoveryWindowInDays=recovery_window_days),
            )
            logger.info("AWS SM secret deletion scheduled", name=name, window_days=recovery_window_days)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ResourceNotFoundException":
                pass  # Already gone
            else:
                raise

    async def list_secrets(self, prefix: str = "") -> list[SecretMetadata]:
        """List secrets with optional name-prefix filter."""
        import asyncio

        loop = asyncio.get_event_loop()
        filters = []
        if prefix:
            filters.append({"Key": "name", "Values": [prefix]})

        def _list():
            paginator = self._client.get_paginator("list_secrets")
            results = []
            for page in paginator.paginate(Filters=filters if filters else []):
                results.extend(page.get("SecretList", []))
            return results

        secrets_raw = await loop.run_in_executor(None, _list)
        return [
            SecretMetadata(
                name=s["Name"],
                provider=self.provider_type,
                created_at=s.get("CreatedDate"),
                tags={t["Key"]: t["Value"] for t in s.get("Tags", [])},
            )
            for s in secrets_raw
        ]

    async def rotate_secret(self, name: str, new_value: str) -> SecretMetadata:
        """Rotate secret to a new value. Stores previous version as AWSPREVIOUS."""
        return await self.set_secret(name, new_value)

    async def health_check(self) -> HealthStatus:
        """Ping AWS SM by listing (1 item) to verify credentials and connectivity."""
        import asyncio

        from botocore.exceptions import (
            EndpointConnectionError,
            NoCredentialsError,
        )

        start = time.monotonic()
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._client.list_secrets(MaxResults=1),
            )
            latency_ms = (time.monotonic() - start) * 1000
            return HealthStatus(
                provider=self.provider_type,
                healthy=True,
                latency_ms=latency_ms,
                message="AWS Secrets Manager reachable",
            )
        except NoCredentialsError:
            return HealthStatus(
                provider=self.provider_type,
                healthy=False,
                message="No AWS credentials found",
            )
        except EndpointConnectionError as exc:
            return HealthStatus(
                provider=self.provider_type,
                healthy=False,
                message=f"Cannot reach AWS endpoint: {exc}",
            )
        except Exception as exc:
            return HealthStatus(
                provider=self.provider_type,
                healthy=False,
                message=f"Health check failed: {exc}",
            )
