"""Vault-backed SIEM and ticketing connector settings."""

from __future__ import annotations

import json

import pytest

from unimonitor.integrations import credentials
from unimonitor.integrations.siem import connector_status
from unimonitor.integrations.ticketing import ticketing_status


class FakeResolver:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.tags: dict[str, dict[str, str]] = {}

    async def get(self, name: str) -> str:
        if name not in self.values:
            raise KeyError(name)
        return self.values[name]

    async def set(self, name: str, value: str, tags: dict[str, str] | None = None):  # noqa: ANN201
        self.values[name] = value
        self.tags[name] = dict(tags or {})
        return name

    async def delete(self, name: str) -> None:
        self.values.pop(name, None)


@pytest.fixture
def resolver(monkeypatch: pytest.MonkeyPatch) -> FakeResolver:
    fake = FakeResolver()

    async def _resolver() -> FakeResolver:
        return fake

    monkeypatch.setattr("unimonitor.secrets.get_secret_resolver", _resolver)
    return fake


def test_save_and_load_round_trip(resolver: FakeResolver):
    stored = asyncio_run(credentials.save("siem", "splunk", {"SPLUNK_HEC_URL": "https://splunk.example.com", "SPLUNK_HEC_TOKEN": "tok"}))
    assert stored == ["SPLUNK_HEC_TOKEN", "SPLUNK_HEC_URL"]
    assert credentials.secret_name("siem", "splunk") in resolver.values
    loaded = asyncio_run(credentials.load("siem", "splunk"))
    assert loaded == {"SPLUNK_HEC_URL": "https://splunk.example.com", "SPLUNK_HEC_TOKEN": "tok"}
    # The stored document is a JSON object, not a bare token.
    assert json.loads(resolver.values[credentials.secret_name("siem", "splunk")])["SPLUNK_HEC_TOKEN"] == "tok"


def test_save_merges_and_ignores_unknown_fields(resolver: FakeResolver):
    asyncio_run(credentials.save("siem", "elastic", {"ELASTIC_URL": "https://es.example.com", "ELASTIC_API_KEY": "one"}))
    asyncio_run(credentials.save("siem", "elastic", {"ELASTIC_API_KEY": "two", "EVIL": "x"}))
    assert asyncio_run(credentials.load("siem", "elastic")) == {"ELASTIC_URL": "https://es.example.com", "ELASTIC_API_KEY": "two"}


def test_url_fields_reject_internal_and_metadata_targets(resolver: FakeResolver):
    """A webhook must not be able to reach the host's own network or a metadata IP."""
    for target in (
        "http://169.254.169.254/latest/meta-data",
        "http://metadata.google.internal/computeMetadata/v1",
        "http://127.0.0.1:8080/hook",
        "http://localhost/hook",
        "https://10.0.0.5/hook",
        "https://192.168.1.10/hook",
        "https://[::1]/hook",
    ):
        with pytest.raises(credentials.ConnectorConfigError):
            asyncio_run(credentials.save("siem", "webhook", {"SIEM_WEBHOOK_URL": target}))
    # A public https endpoint is still accepted.
    asyncio_run(credentials.save("siem", "webhook", {"SIEM_WEBHOOK_URL": "https://siem.example.com/hook"}))


def test_url_fields_must_be_http(resolver: FakeResolver):
    with pytest.raises(credentials.ConnectorConfigError):
        asyncio_run(credentials.save("siem", "webhook", {"SIEM_WEBHOOK_URL": "file:///etc/passwd"}))
    with pytest.raises(credentials.ConnectorConfigError):
        asyncio_run(credentials.save("siem", "syslog", {"SIEM_SYSLOG_HOST": "https://host"}))


def test_unknown_connector_is_rejected(resolver: FakeResolver):
    with pytest.raises(credentials.ConnectorConfigError):
        asyncio_run(credentials.save("siem", "nope", {"A": "b"}))
    with pytest.raises(credentials.ConnectorConfigError):
        asyncio_run(credentials.save("other", "splunk", {"SPLUNK_HEC_URL": "https://x"}))


def test_blank_values_are_not_stored(resolver: FakeResolver):
    with pytest.raises(credentials.ConnectorConfigError):
        asyncio_run(credentials.save("siem", "splunk", {"SPLUNK_HEC_URL": "  "}))


def test_delete_restores_environment_fallback(resolver: FakeResolver):
    asyncio_run(credentials.save("ticketing", "webhook", {"TICKET_WEBHOOK_URL": "https://tickets.example.com/hook"}))
    asyncio_run(credentials.delete("ticketing", "webhook"))
    assert asyncio_run(credentials.load("ticketing", "webhook")) is None


def test_status_reports_managed_connectors(resolver: FakeResolver):
    asyncio_run(credentials.save("siem", "splunk", {"SPLUNK_HEC_URL": "https://splunk.example.com", "SPLUNK_HEC_TOKEN": "tok"}))
    configs = asyncio_run(credentials.load_all("siem"))
    rows = {row["slug"]: row for row in connector_status(configs)}
    assert rows["splunk"]["configured"] is True
    assert rows["splunk"]["managed"] is True
    assert rows["datadog"]["managed"] is False


def test_ticketing_status_reports_managed_provider(resolver: FakeResolver):
    asyncio_run(
        credentials.save(
            "ticketing",
            "jira",
            {
                "JIRA_URL": "https://acme.atlassian.net",
                "JIRA_EMAIL": "sec@acme.example",
                "JIRA_API_TOKEN": "token",
                "JIRA_PROJECT_KEY": "SEC",
            },
        )
    )
    rows = {row["slug"]: row for row in ticketing_status(asyncio_run(credentials.load_all("ticketing")))}
    assert rows["jira"]["configured"] is True
    assert rows["jira"]["managed"] is True


def asyncio_run(coroutine):  # noqa: ANN001, ANN201 - tiny local runner keeps the test sync
    import asyncio

    return asyncio.run(coroutine)
