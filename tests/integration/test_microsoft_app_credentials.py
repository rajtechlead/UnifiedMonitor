"""Sign-in and Graph pages use the connected Entra app, not the Tenant row.

The `Tenant` row stores a secret *reference*; the app registration and its
certificate/secret live in `cloud_connections` + the vault. Building a Graph client
from the tenant row (or from startup settings, before the wizard's app is hydrated)
is what made "Sign in with Microsoft" report itself unconfigured and made licence
posture and service health answer 502.
"""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from unimonitor.onboarding import service

pytestmark = pytest.mark.asyncio


class _FakeResolver:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    async def get(self, ref: str) -> str:
        return self.values[ref]


@pytest.fixture
def vault_secrets(monkeypatch):
    """Resolve the refs a test connection declares, without touching the real vault."""
    values = {"ref-cert": "-----BEGIN CERTIFICATE-----", "ref-key": "-----BEGIN PRIVATE KEY-----", "ref-secret": "s3cret"}

    async def _resolver():
        return _FakeResolver(values)

    monkeypatch.setattr(service, "get_secret_resolver", _resolver)
    return values


async def _connection(db_session, tenant, *, auth_method: str) -> None:
    from unimonitor.db.models.cloud_connection import CloudConnection

    refs = {"certificate_pem": "ref-cert", "private_key_pem": "ref-key"} if auth_method == "certificate" else {"client_secret": "ref-secret"}
    db_session.add(
        CloudConnection(
            tenant_id=tenant.id,
            provider="microsoft",
            account="00000000-0000-0000-0000-0000000000aa",
            display_name="Contoso",
            status="connected",
            config=json.dumps({"client_id": "00000000-0000-0000-0000-0000000000bb", "auth_method": auth_method}),
            secret_refs=json.dumps(refs),
        )
    )
    await db_session.flush()


async def test_certificate_connection_resolves_the_uploaded_pair(db_session, tenant, vault_secrets):
    await _connection(db_session, tenant, auth_method="certificate")

    app = await service.microsoft_app(db_session, tenant.id)

    assert app["configured"] is True
    assert app["source"] == "connection"
    assert app["client_id"] == "00000000-0000-0000-0000-0000000000bb"
    assert app["directory"] == "00000000-0000-0000-0000-0000000000aa"
    assert app["certificate_pem"].startswith("-----BEGIN CERTIFICATE")
    assert app["private_key_pem"].startswith("-----BEGIN PRIVATE KEY")
    assert app["client_secret"] == ""


async def test_client_secret_connection_resolves_the_secret(db_session, tenant, vault_secrets):
    await _connection(db_session, tenant, auth_method="client_secret")

    app = await service.microsoft_app(db_session, tenant.id)

    assert app["client_secret"] == "s3cret"
    assert app["certificate_pem"] == ""


async def test_no_connection_falls_back_to_settings(db_session, tenant):
    app = await service.microsoft_app(db_session, tenant.id)

    assert app["source"] == "settings"
    # Nothing is configured in the test environment, so sign-in stays disabled.
    assert app["configured"] is False


async def test_graph_page_uses_the_connected_app_credentials(db_session, tenant, vault_secrets, monkeypatch):
    """`_graph_json` must mint its token with the connection's app, certificate included."""
    from unimonitor.api.v1 import monitoring

    await _connection(db_session, tenant, auth_method="certificate")
    captured: dict = {}

    class _Response:
        success = True
        stale = False
        data = {"value": [{"service": "Exchange Online", "status": "serviceOperational"}]}

    class _Client:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, endpoint):
            captured["endpoint"] = endpoint
            return _Response()

    monkeypatch.setattr("unimonitor.graph.client.GraphClient", _Client)

    payload = await monitoring._graph_json(db_session, tenant, "/subscribedSkus", permission="Organization.Read.All")

    assert payload["value"][0]["service"] == "Exchange Online"
    assert captured["client_id"] == "00000000-0000-0000-0000-0000000000bb"
    assert captured["client_secret"] is None
    assert captured["certificate_pem"].startswith("-----BEGIN CERTIFICATE")


async def test_a_missing_permission_is_reported_as_403_not_502(db_session, tenant, vault_secrets, monkeypatch):
    from unimonitor.api.v1 import monitoring
    from unimonitor.exceptions import GraphPermissionError

    await _connection(db_session, tenant, auth_method="certificate")

    class _Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, endpoint):
            raise GraphPermissionError("Insufficient permissions")

    monkeypatch.setattr("unimonitor.graph.client.GraphClient", _Client)

    with pytest.raises(HTTPException) as caught:
        await monitoring._graph_json(db_session, tenant, "/subscribedSkus", permission="Organization.Read.All")

    assert caught.value.status_code == 403
    assert "Organization.Read.All" in caught.value.detail


async def test_a_tenant_without_a_microsoft_connection_is_asked_to_connect(db_session, tenant):
    from unimonitor.api.v1 import monitoring

    with pytest.raises(HTTPException) as caught:
        await monitoring._graph_json(db_session, tenant, "/subscribedSkus", permission="Organization.Read.All")

    assert caught.value.status_code == 503
    assert "not connected" in caught.value.detail
