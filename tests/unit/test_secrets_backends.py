"""
Unit tests for secrets backend providers: AWS Secrets Manager, Azure Key Vault,
and the RotationManager.

All external SDK calls are mocked — no real AWS/Azure credentials needed.
azure-keyvault-secrets and azure-identity are not installed in the test env,
so we stub their modules before importing the provider under test.
"""

from __future__ import annotations

import asyncio
import sys
import types
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    """Run a coroutine in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _stub_azure_modules():
    """Inject stub azure SDK modules into sys.modules so the provider can be imported."""
    # Build stub module tree
    azure_mod = types.ModuleType("azure")
    azure_identity = types.ModuleType("azure.identity")
    azure_keyvault = types.ModuleType("azure.keyvault")
    azure_keyvault_secrets = types.ModuleType("azure.keyvault.secrets")
    azure_core = types.ModuleType("azure.core")
    azure_core_exceptions = types.ModuleType("azure.core.exceptions")

    class ResourceNotFoundError(Exception):
        pass

    class ClientAuthenticationError(Exception):
        pass

    azure_core_exceptions.ResourceNotFoundError = ResourceNotFoundError
    azure_core_exceptions.ClientAuthenticationError = ClientAuthenticationError
    azure_identity.DefaultAzureCredential = MagicMock
    azure_keyvault_secrets.SecretClient = MagicMock

    # Wire submodule attributes
    azure_mod.identity = azure_identity
    azure_mod.keyvault = azure_keyvault
    azure_keyvault.secrets = azure_keyvault_secrets
    azure_mod.core = azure_core
    azure_core.exceptions = azure_core_exceptions

    for name, mod in [
        ("azure", azure_mod),
        ("azure.identity", azure_identity),
        ("azure.keyvault", azure_keyvault),
        ("azure.keyvault.secrets", azure_keyvault_secrets),
        ("azure.core", azure_core),
        ("azure.core.exceptions", azure_core_exceptions),
    ]:
        sys.modules.setdefault(name, mod)

    return azure_core_exceptions


# Stub Azure modules at import time (once per test session)
_azure_exc = _stub_azure_modules()
_ResourceNotFoundError = _azure_exc.ResourceNotFoundError
_ClientAuthenticationError = _azure_exc.ClientAuthenticationError


# ---------------------------------------------------------------------------
# AWSSecretsManagerProvider
# ---------------------------------------------------------------------------


class TestAWSSecretsManagerProvider:
    def _make_provider(self, client_mock):
        """Create a provider with a mocked boto3 client."""
        from unimonitor.secrets.aws_secrets_manager import AWSSecretsManagerProvider

        with patch("boto3.client", return_value=client_mock):
            return AWSSecretsManagerProvider(region_name="us-east-1")

    def test_get_secret_string(self):
        client = MagicMock()
        client.get_secret_value.return_value = {"SecretString": "my-value"}
        provider = self._make_provider(client)
        result = _run(provider.get_secret("my-secret"))
        assert result == "my-value"

    def test_get_secret_binary(self):
        import base64

        client = MagicMock()
        client.get_secret_value.return_value = {
            "SecretBinary": base64.b64encode(b"binary-secret"),
        }
        provider = self._make_provider(client)
        result = _run(provider.get_secret("my-secret"))
        assert result == "binary-secret"

    def test_get_secret_not_found_raises_key_error(self):
        from botocore.exceptions import ClientError

        client = MagicMock()
        client.get_secret_value.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "not found"}},
            "GetSecretValue",
        )
        provider = self._make_provider(client)
        lookup = provider.get_secret("missing-secret")
        with pytest.raises(KeyError):
            _run(lookup)

    def test_get_secret_invalid_request_raises_key_error(self):
        from botocore.exceptions import ClientError

        client = MagicMock()
        client.get_secret_value.side_effect = ClientError(
            {"Error": {"Code": "InvalidRequestException", "Message": "invalid"}},
            "GetSecretValue",
        )
        provider = self._make_provider(client)
        lookup = provider.get_secret("bad-request")
        with pytest.raises(KeyError):
            _run(lookup)

    def test_set_secret_update_existing(self):
        client = MagicMock()
        client.put_secret_value.return_value = {"VersionId": "v2"}
        provider = self._make_provider(client)
        meta = _run(provider.set_secret("my-secret", "new-value"))
        assert meta.name == "my-secret"
        assert meta.version == "v2"

    def test_set_secret_create_new(self):
        from botocore.exceptions import ClientError

        client = MagicMock()
        client.put_secret_value.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "not found"}},
            "PutSecretValue",
        )
        client.create_secret.return_value = {"VersionId": "v1"}
        provider = self._make_provider(client)
        meta = _run(provider.set_secret("new-secret", "initial-value", tags={"env": "test"}))
        assert meta.name == "new-secret"
        assert meta.version == "v1"

    def test_delete_secret(self):
        client = MagicMock()
        client.delete_secret.return_value = {}
        provider = self._make_provider(client)
        _run(provider.delete_secret("my-secret"))
        client.delete_secret.assert_called_once()

    def test_delete_secret_already_gone(self):
        from botocore.exceptions import ClientError

        client = MagicMock()
        client.delete_secret.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "not found"}},
            "DeleteSecret",
        )
        provider = self._make_provider(client)
        _run(provider.delete_secret("already-gone"))  # should not raise

    def test_list_secrets(self):
        client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "SecretList": [
                    {"Name": "secret-a", "Tags": [{"Key": "env", "Value": "prod"}], "CreatedDate": None},
                    {"Name": "secret-b", "Tags": [], "CreatedDate": None},
                ]
            }
        ]
        client.get_paginator.return_value = paginator
        provider = self._make_provider(client)
        results = _run(provider.list_secrets())
        assert len(results) == 2
        assert results[0].name == "secret-a"

    def test_list_secrets_with_prefix(self):
        client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [{"SecretList": []}]
        client.get_paginator.return_value = paginator
        provider = self._make_provider(client)
        results = _run(provider.list_secrets(prefix="app/"))
        assert results == []

    def test_health_check_success(self):
        client = MagicMock()
        client.list_secrets.return_value = {}
        provider = self._make_provider(client)
        status = _run(provider.health_check())
        assert status.healthy is True

    def test_health_check_no_credentials(self):
        from botocore.exceptions import NoCredentialsError

        client = MagicMock()
        client.list_secrets.side_effect = NoCredentialsError()
        provider = self._make_provider(client)
        status = _run(provider.health_check())
        assert status.healthy is False
        assert "credentials" in status.message.lower()

    def test_health_check_endpoint_error(self):
        from botocore.exceptions import EndpointConnectionError

        client = MagicMock()
        client.list_secrets.side_effect = EndpointConnectionError(endpoint_url="http://localhost")
        provider = self._make_provider(client)
        status = _run(provider.health_check())
        assert status.healthy is False

    def test_health_check_other_error(self):
        client = MagicMock()
        client.list_secrets.side_effect = RuntimeError("unexpected")
        provider = self._make_provider(client)
        status = _run(provider.health_check())
        assert status.healthy is False

    def test_rotate_secret_delegates_to_set(self):
        client = MagicMock()
        client.put_secret_value.return_value = {"VersionId": "v3"}
        provider = self._make_provider(client)
        meta = _run(provider.rotate_secret("my-secret", "rotated-value"))
        assert meta.name == "my-secret"


# ---------------------------------------------------------------------------
# AzureKeyVaultProvider
# ---------------------------------------------------------------------------


class TestAzureKeyVaultProvider:
    def _make_provider(self):
        """Create a provider with stubbed Azure SDK (no real credentials)."""
        from unimonitor.secrets.azure_keyvault import AzureKeyVaultProvider

        provider = AzureKeyVaultProvider.__new__(AzureKeyVaultProvider)
        provider._vault_url = "https://test.vault.azure.net/"
        provider._client = MagicMock()
        from unimonitor.secrets.provider import ProviderType

        provider.provider_type = ProviderType.AZURE_KEY_VAULT
        return provider

    def test_get_secret_success(self):
        provider = self._make_provider()
        secret_obj = MagicMock()
        secret_obj.value = "my-value"
        provider._client.get_secret.return_value = secret_obj
        result = _run(provider.get_secret("my-secret"))
        assert result == "my-value"

    def test_get_secret_none_value_raises_key_error(self):
        provider = self._make_provider()
        secret_obj = MagicMock()
        secret_obj.value = None
        provider._client.get_secret.return_value = secret_obj
        lookup = provider.get_secret("empty-secret")
        with pytest.raises(KeyError):
            _run(lookup)

    def test_get_secret_not_found_raises_key_error(self):
        provider = self._make_provider()
        provider._client.get_secret.side_effect = _ResourceNotFoundError("not found")
        lookup = provider.get_secret("missing")
        with pytest.raises(KeyError):
            _run(lookup)

    def test_set_secret_success(self):
        provider = self._make_provider()
        props = MagicMock()
        props.properties.version = "abc123"
        props.properties.created_on = None
        props.properties.tags = {"env": "test"}
        provider._client.set_secret.return_value = props
        meta = _run(provider.set_secret("my-secret", "value", tags={"env": "test"}))
        assert meta.name == "my-secret"
        assert meta.version == "abc123"

    def test_delete_secret_success(self):
        provider = self._make_provider()
        provider._client.begin_delete_secret.return_value = MagicMock()
        _run(provider.delete_secret("my-secret"))
        provider._client.begin_delete_secret.assert_called_once_with("my-secret")

    def test_delete_secret_not_found_silent(self):
        provider = self._make_provider()
        provider._client.begin_delete_secret.side_effect = _ResourceNotFoundError("not found")
        _run(provider.delete_secret("already-gone"))  # should not raise

    def test_list_secrets_no_prefix(self):
        provider = self._make_provider()
        p1 = MagicMock()
        p1.name = "secret-a"
        p1.version = "v1"
        p1.created_on = None
        p1.expires_on = None
        p1.tags = {}
        p2 = MagicMock()
        p2.name = "secret-b"
        p2.version = "v2"
        p2.created_on = None
        p2.expires_on = None
        p2.tags = {}
        provider._client.list_properties_of_secrets.return_value = [p1, p2]
        results = _run(provider.list_secrets())
        assert len(results) == 2

    def test_list_secrets_with_prefix(self):
        provider = self._make_provider()
        p1 = MagicMock()
        p1.name = "app/secret-a"
        p1.version = "v1"
        p1.created_on = None
        p1.expires_on = None
        p1.tags = {}
        p2 = MagicMock()
        p2.name = "other/secret-b"
        p2.version = "v2"
        p2.created_on = None
        p2.expires_on = None
        p2.tags = {}
        provider._client.list_properties_of_secrets.return_value = [p1, p2]
        results = _run(provider.list_secrets(prefix="app/"))
        assert len(results) == 1
        assert results[0].name == "app/secret-a"

    def test_health_check_success(self):
        provider = self._make_provider()
        provider._client.list_properties_of_secrets.return_value = iter([])
        status = _run(provider.health_check())
        assert status.healthy is True

    def test_health_check_auth_failure(self):
        provider = self._make_provider()
        provider._client.list_properties_of_secrets.side_effect = _ClientAuthenticationError("auth failed")
        status = _run(provider.health_check())
        assert status.healthy is False

    def test_health_check_other_error(self):
        provider = self._make_provider()
        provider._client.list_properties_of_secrets.side_effect = RuntimeError("unexpected")
        status = _run(provider.health_check())
        assert status.healthy is False

    def test_rotate_secret_delegates_to_set(self):
        provider = self._make_provider()
        props = MagicMock()
        props.properties.version = "v-new"
        props.properties.created_on = None
        props.properties.tags = {}
        provider._client.set_secret.return_value = props
        meta = _run(provider.rotate_secret("my-secret", "new-value"))
        assert meta.name == "my-secret"


# ---------------------------------------------------------------------------
# RotationManager
# ---------------------------------------------------------------------------


class TestRotationManager:
    def _make_provider(self):
        from unimonitor.secrets.provider import ProviderType, SecretMetadata

        p = MagicMock()
        p.provider_type = ProviderType.LOCAL_VAULT
        p.rotate_secret = AsyncMock(
            return_value=SecretMetadata(
                name="test-secret",
                provider=ProviderType.LOCAL_VAULT,
            )
        )
        p.list_secrets = AsyncMock(return_value=[])
        return p

    def test_rotate_no_hooks(self):
        from unimonitor.secrets.rotation import RotationManager

        provider = self._make_provider()
        mgr = RotationManager(provider)
        meta = _run(mgr.rotate("test-secret", "new-value"))
        assert meta.name == "test-secret"
        provider.rotate_secret.assert_awaited_once_with("test-secret", "new-value")

    def test_rotate_with_pre_and_post_hooks(self):
        from unimonitor.secrets.rotation import RotationManager

        provider = self._make_provider()
        mgr = RotationManager(provider)

        pre_called = []
        post_called = []

        async def pre_hook(name):
            pre_called.append(name)

        async def post_hook(name, value):
            post_called.append((name, value))

        _run(mgr.rotate("test-secret", "new-value", pre_hook=pre_hook, post_hook=post_hook))
        assert pre_called == ["test-secret"]
        assert post_called == [("test-secret", "new-value")]

    def test_check_rotation_due_true(self):
        from unimonitor.secrets.provider import ProviderType, SecretMetadata
        from unimonitor.secrets.rotation import RotationManager

        past = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        provider = MagicMock()
        provider.list_secrets = AsyncMock(
            return_value=[
                SecretMetadata(
                    name="test-secret",
                    provider=ProviderType.LOCAL_VAULT,
                    tags={"rotate_after_days": "90", "last_rotated_at": past},
                )
            ]
        )
        mgr = RotationManager(provider)
        result = _run(mgr.check_rotation_due("test-secret"))
        assert result is True

    def test_check_rotation_due_false(self):
        from unimonitor.secrets.provider import ProviderType, SecretMetadata
        from unimonitor.secrets.rotation import RotationManager

        recent = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        provider = MagicMock()
        provider.list_secrets = AsyncMock(
            return_value=[
                SecretMetadata(
                    name="test-secret",
                    provider=ProviderType.LOCAL_VAULT,
                    tags={"rotate_after_days": "90", "last_rotated_at": recent},
                )
            ]
        )
        mgr = RotationManager(provider)
        result = _run(mgr.check_rotation_due("test-secret"))
        assert result is False

    def test_check_rotation_no_policy(self):
        from unimonitor.secrets.provider import ProviderType, SecretMetadata
        from unimonitor.secrets.rotation import RotationManager

        provider = MagicMock()
        provider.list_secrets = AsyncMock(return_value=[SecretMetadata(name="test-secret", provider=ProviderType.LOCAL_VAULT, tags={})])
        mgr = RotationManager(provider)
        result = _run(mgr.check_rotation_due("test-secret"))
        assert result is False

    def test_check_rotation_provider_error_returns_false(self):
        from unimonitor.secrets.rotation import RotationManager

        provider = MagicMock()
        provider.list_secrets = AsyncMock(side_effect=RuntimeError("connection failed"))
        mgr = RotationManager(provider)
        result = _run(mgr.check_rotation_due("test-secret"))
        assert result is False

    def test_list_rotation_due(self):
        from unimonitor.secrets.provider import ProviderType, SecretMetadata
        from unimonitor.secrets.rotation import RotationManager

        past = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        recent = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        provider = MagicMock()
        provider.list_secrets = AsyncMock(
            return_value=[
                SecretMetadata(
                    name="overdue-secret",
                    provider=ProviderType.LOCAL_VAULT,
                    tags={"rotate_after_days": "90", "last_rotated_at": past},
                ),
                SecretMetadata(
                    name="fresh-secret",
                    provider=ProviderType.LOCAL_VAULT,
                    tags={"rotate_after_days": "90", "last_rotated_at": recent},
                ),
            ]
        )
        mgr = RotationManager(provider)
        due = _run(mgr.list_rotation_due())
        assert "overdue-secret" in due
        assert "fresh-secret" not in due

    def test_list_rotation_due_empty(self):
        from unimonitor.secrets.rotation import RotationManager

        provider = self._make_provider()
        provider.list_secrets = AsyncMock(return_value=[])
        mgr = RotationManager(provider)
        result = _run(mgr.list_rotation_due())
        assert result == []

    def test_list_rotation_due_provider_error(self):
        from unimonitor.secrets.rotation import RotationManager

        provider = MagicMock()
        provider.list_secrets = AsyncMock(side_effect=RuntimeError("failed"))
        mgr = RotationManager(provider)
        result = _run(mgr.list_rotation_due())
        assert result == []
