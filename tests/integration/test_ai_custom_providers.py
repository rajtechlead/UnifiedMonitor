"""Custom AI providers: a tenant gateway tried before the built-in chain."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from unimonitor.ai import custom
from unimonitor.ai.providers import configured_providers, provider_status
from unimonitor.secrets.local_vault import LocalVaultProvider
from unimonitor.secrets.resolver import SecretResolver

pytestmark = pytest.mark.asyncio

URL = "/api/v1/ai/providers/custom"


@pytest.fixture
def vault(tmp_path, monkeypatch):
    provider = LocalVaultProvider(vault_dir=tmp_path / "vault")

    async def _resolver():
        return SecretResolver(primary_provider=provider)

    monkeypatch.setattr("unimonitor.secrets.get_secret_resolver", _resolver)
    return provider


def _body(*entries: dict) -> dict:
    return {"providers": list(entries)}


class TestProviderCatalogue:
    def test_azure_openai_is_not_offered(self):
        assert "azure_openai" not in [entry["name"] for entry in provider_status()]
        assert all(provider.name != "azure_openai" for provider in configured_providers())


class TestCustomProviders:
    async def test_a_provider_is_stored_with_its_key_in_the_vault(self, client: AsyncClient, auth_headers: dict, db_session, tenant, vault):
        r = await client.put(
            URL,
            json=_body(
                {
                    "name": "internal-gw",
                    "base_url": "https://llm.contoso.internal/v1",
                    "model": "secure-7b",
                    "api_key": "gateway-key",
                }
            ),
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        entry = r.json()[0]
        assert entry["name"] == "internal-gw"
        assert entry["has_key"] is True
        assert entry["api_key"] == custom.MASK

        assert await vault.get_secret(custom.secret_name(tenant.id, "internal-gw")) == "gateway-key"

        await db_session.refresh(tenant)
        assert "gateway-key" not in (tenant.settings_json or "")

    async def test_the_masked_key_keeps_the_stored_one(self, client: AsyncClient, auth_headers: dict, tenant, vault):
        payload = _body({"name": "gw", "base_url": "https://gw.example.com/v1", "model": "m", "api_key": "first-key"})
        await client.put(URL, json=payload, headers=auth_headers)

        payload["providers"][0]["api_key"] = custom.MASK
        r = await client.put(URL, json=payload, headers=auth_headers)
        assert r.status_code == 200
        assert await vault.get_secret(custom.secret_name(tenant.id, "gw")) == "first-key"

    async def test_removing_a_provider_deletes_its_key(self, client: AsyncClient, auth_headers: dict, tenant, vault):
        await client.put(
            URL,
            json=_body(
                {"name": "gw", "base_url": "https://gw.example.com/v1", "model": "m", "api_key": "k"},
                {"name": "gw2", "base_url": "https://gw2.example.com/v1", "model": "m", "api_key": "k2"},
            ),
            headers=auth_headers,
        )
        r = await client.put(
            URL,
            json=_body({"name": "gw", "base_url": "https://gw.example.com/v1", "model": "m", "api_key": custom.MASK}),
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert [entry["name"] for entry in r.json()] == ["gw"]
        removed_key = custom.secret_name(tenant.id, "gw2")
        with pytest.raises(KeyError):
            await vault.get_secret(removed_key)

    async def test_a_custom_provider_joins_the_failover_chain(self, client: AsyncClient, auth_headers: dict, tenant, vault):
        await client.put(
            URL,
            json=_body({"name": "gw", "base_url": "https://gw.example.com/v1", "model": "m", "api_key": "k"}),
            headers=auth_headers,
        )
        chain = await custom.providers_for(tenant)
        assert [provider.name for provider in chain] == ["custom:gw"]
        assert chain[0].api_key == "k"

    async def test_duplicate_names_are_rejected(self, client: AsyncClient, auth_headers: dict, tenant, vault):
        r = await client.put(
            URL,
            json=_body(
                {"name": "gw", "base_url": "https://a.example.com", "model": "m"},
                {"name": "gw", "base_url": "https://b.example.com", "model": "m"},
            ),
            headers=auth_headers,
        )
        assert r.status_code == 400

    async def test_a_plain_http_url_is_rejected(self, client: AsyncClient, auth_headers: dict, tenant, vault):
        r = await client.put(
            URL,
            json=_body({"name": "gw", "base_url": "ftp://gw.example.com", "model": "m"}),
            headers=auth_headers,
        )
        assert r.status_code == 422

    async def test_listing_needs_authentication(self, client: AsyncClient, tenant, vault):
        assert (await client.get(URL)).status_code == 401

    @pytest.mark.parametrize(
        "base_url",
        [
            "https://169.254.169.254/latest/meta-data",
            "http://169.254.169.254/v1",
            "https://metadata.google.internal/computeMetadata/v1",
            "https://[fd00:ec2::254]/v1",
            "https://100.100.100.200/v1",
            "https://[fe80::1]/v1",
        ],
    )
    async def test_metadata_and_link_local_targets_are_rejected(self, client: AsyncClient, auth_headers: dict, tenant, vault, base_url: str):
        r = await client.put(
            URL,
            json=_body({"name": "metadata", "base_url": base_url, "model": "m"}),
            headers=auth_headers,
        )
        assert r.status_code == 422, r.text

    async def test_plain_http_is_only_allowed_for_a_loopback_gateway(self, client: AsyncClient, auth_headers: dict, tenant, vault):
        rejected = await client.put(
            URL,
            json=_body({"name": "gw", "base_url": "http://gw.example.com/v1", "model": "m"}),
            headers=auth_headers,
        )
        assert rejected.status_code == 422

        accepted = await client.put(
            URL,
            json=_body({"name": "local", "base_url": "http://127.0.0.1:11434/v1", "model": "m"}),
            headers=auth_headers,
        )
        assert accepted.status_code == 200, accepted.text

    async def test_a_malformed_stored_entry_does_not_break_the_settings_page(
        self, client: AsyncClient, auth_headers: dict, tenant, db_session, vault
    ):
        tenant.settings_json = (
            '{"ai_providers": ['
            '{"name": "good", "base_url": "https://gw.example.com/v1", "model": "m", "enabled": true},'
            '{"name": "no-model", "base_url": "https://gw.example.com/v1"},'
            '{"name": "bad-url", "base_url": "ftp://x", "model": "m"},'
            '"not-a-dict"'
            "]}"
        )
        await db_session.flush()

        r = await client.get(URL, headers=auth_headers)
        assert r.status_code == 200, r.text
        assert [entry["name"] for entry in r.json()] == ["good"]

        chain = await custom.providers_for(tenant)
        assert chain == []  # the good entry has no key, so it is not in the chain
