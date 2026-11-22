"""AI remediation: anonymisation and provider failover.

Two promises are tested here, because both are easy to break silently:

* the prompt carries only control metadata — no tenant id, no finding id, no user,
  no address, no policy or resource name that identifies an environment;
* when a provider is out of quota (or rate limited, or down) the next configured
  provider answers instead of the user seeing an error.
"""

from types import SimpleNamespace

import httpx
import pytest

from unimonitor.ai.anonymize import anonymise, scrub
from unimonitor.ai.providers import Provider, configured_providers
from unimonitor.ai.service import AIUnavailableError, complete


class TestScrub:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("contact soc@contoso.com now", "contact [EMAIL] now"),
            ("upn john.smith@fabrikam.onmicrosoft.com", "upn [EMAIL]"),
            ("policy 4f9a2c1e-8b3d-4a1f-9e2b-0c7d6a5b4e3f", "policy [GUID]"),
            ("host 10.20.30.40", "host [IP]"),
            ("see https://portal.azure.com/#blade/x", "see [URL]"),
            ("tenant fabrikam.onmicrosoft.com", "tenant [DOMAIN]"),
            ("file C:\\Users\\alice\\policy.json", "file [PATH]"),
            ("subscription 123456789012", "subscription [NUMBER]"),
        ],
    )
    def test_identifiers_are_replaced(self, raw, expected):
        assert scrub(raw) == expected

    def test_plain_control_names_survive(self):
        text = "Ensure multifactor authentication is enabled for all users"
        assert scrub(text) == text


class TestAnonymise:
    def test_only_control_metadata_leaves_the_deployment(self):
        finding = {
            "id": "finding-9000",
            "tenant_id": "tenant-abc",
            "external_control_id": "MCSB-ID-1.1",
            "framework": "mcsb",
            "category": "Identity",
            "severity": "HIGH",
            "state": "not_implemented",
            "title": "Require MFA for admins",
            "description": "Admins must use MFA.",
            # Everything below must not survive into the payload.
            "evidence": {"policy": "Contoso Baseline", "owner": "alice@contoso.com"},
            "service": "graph",
            "assignee_id": "user-1",
        }
        payload = anonymise(finding)

        assert set(payload) == {"control_id", "framework", "category", "severity", "state", "title", "description"}
        assert payload["severity"] == "high"
        serialised = " ".join(payload.values())
        for leaked in ("finding-9000", "tenant-abc", "Contoso Baseline", "alice@contoso.com", "user-1", "graph"):
            assert leaked not in serialised

    def test_a_title_carrying_identifiers_is_scrubbed(self):
        payload = anonymise(
            {
                "external_control_id": "X-1",
                "title": "Block alice@contoso.com and fabrikam.onmicrosoft.com from 10.1.2.3",
                "description": "See https://admin.contoso.com/policy",
            }
        )
        assert "alice@contoso.com" not in payload["title"]
        assert "fabrikam.onmicrosoft.com" not in payload["title"]
        assert "10.1.2.3" not in payload["title"]
        assert "admin.contoso.com" not in payload["description"]

    def test_an_untrusted_control_id_is_replaced(self):
        payload = anonymise({"external_control_id": "policy/Contoso Admins <script>", "severity": "high"})
        assert payload["control_id"] == "[CONTROL]"

    def test_an_unknown_severity_becomes_medium(self):
        assert anonymise({"external_control_id": "A-1", "severity": "catastrophic"})["severity"] == "medium"

    def test_long_description_is_truncated(self):
        payload = anonymise({"external_control_id": "A-1", "description": "x" * 5000})
        assert len(payload["description"]) <= 600


def _provider(name: str, model: str = "m1", kind: str = "openai") -> Provider:
    return Provider(name=name, kind=kind, base_url=f"https://{name}.example/v1", model=model, api_key="k")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=5)


def _answer(text: str = '{"executive_summary": "ok"}') -> dict:
    return {"choices": [{"message": {"content": text}}]}


class TestFailover:
    @pytest.mark.asyncio
    async def test_a_quota_error_moves_to_the_next_provider(self):
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url.host))
            if request.url.host.startswith("freebuff"):
                return httpx.Response(429, json={"error": {"message": "quota exhausted"}})
            return httpx.Response(200, json=_answer())

        async with _client(handler) as client:
            result = await complete("sys", "user", providers=[_provider("freebuff"), _provider("groq")], client=client)

        assert result.provider == "groq"
        assert seen == ["freebuff.example", "groq.example"]
        assert any("freebuff" in attempt and "429" in attempt for attempt in result.attempts)

    @pytest.mark.asyncio
    async def test_a_server_error_moves_to_the_next_provider(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host.startswith("down"):
                return httpx.Response(503)
            return httpx.Response(200, json=_answer())

        async with _client(handler) as client:
            result = await complete("sys", "user", providers=[_provider("down"), _provider("ok")], client=client)
        assert result.provider == "ok"

    @pytest.mark.asyncio
    async def test_an_anthropic_answer_is_parsed(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["x-api-key"] == "k"
            return httpx.Response(200, json={"content": [{"type": "text", "text": '{"summary": "s"}'}]})

        async with _client(handler) as client:
            result = await complete("sys", "user", providers=[_provider("claude", kind="anthropic")], client=client)
        assert '{"summary": "s"}' in result.text

    @pytest.mark.asyncio
    async def test_every_provider_failing_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429)

        client = _client(handler)
        with pytest.raises(AIUnavailableError):
            await complete("sys", "user", providers=[_provider("a"), _provider("b")], client=client)
        await client.aclose()

    @pytest.mark.asyncio
    async def test_an_empty_chain_raises(self):
        with pytest.raises(AIUnavailableError):
            await complete("sys", "user", providers=[])

    @pytest.mark.asyncio
    async def test_the_prompt_sent_carries_no_identifiers(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = request.content.decode()
            return httpx.Response(200, json=_answer())

        payload = anonymise(
            {
                "external_control_id": "MCSB-1",
                "title": "Policy for alice@contoso.com",
                "description": "Tenant fabrikam.onmicrosoft.com, host 10.0.0.5.",
            }
        )
        from unimonitor.grc.ai_remediation import build_user_prompt

        async with _client(handler) as client:
            await complete("sys", build_user_prompt(payload), providers=[_provider("p")], client=client)

        body = captured["body"]
        for leaked in ("alice@contoso.com", "fabrikam.onmicrosoft.com", "10.0.0.5"):
            assert leaked not in body
        assert "MCSB-1" in body


class TestProviderOrder:
    def test_only_configured_providers_are_returned_in_order(self, monkeypatch):
        import unimonitor.ai.providers as providers_module

        settings = SimpleNamespace(
            AI_PROVIDER_ORDER="groq,freebuff,anthropic",
            FREEBUFF_BASE_URL="https://freebuff",
            FREEBUFF_API_KEY="",
            FREEBUFF_MODEL="",
            OPENAI_API_KEY="",
            OPENAI_BASE_URL="https://openai",
            OPENAI_MODEL="gpt-4o-mini",
            ANTHROPIC_API_KEY="sk-ant",
            ANTHROPIC_BASE_URL="https://anthropic",
            ANTHROPIC_MODEL="claude",
            GROQ_API_KEY="",
            GROQ_BASE_URL="https://groq",
            GROQ_MODEL="llama",
            AZURE_OPENAI_ENDPOINT="",
            AZURE_OPENAI_API_KEY="",
            AZURE_OPENAI_DEPLOYMENT="gpt-4o",
        )
        monkeypatch.setattr(providers_module, "get_settings", lambda: settings)

        assert [provider.name for provider in configured_providers()] == ["anthropic"]
