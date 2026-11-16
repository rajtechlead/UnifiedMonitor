"""Provider registry: service → provider mapping and aliases."""

from unimonitor.grc.providers import PROVIDERS, get_provider, provider_for_service, provider_ids


def test_provider_ids_cover_all_clouds():
    assert provider_ids() == ["microsoft", "aws", "gcp", "google_workspace"]


def test_service_maps_to_provider():
    assert provider_for_service("entra_id").id == "microsoft"
    assert provider_for_service("defender_office").id == "microsoft"
    assert provider_for_service("copilot_studio").id == "microsoft"
    assert provider_for_service("aws").id == "aws"
    assert provider_for_service("gcp").id == "gcp"
    assert provider_for_service("google_workspace").id == "google_workspace"


def test_unknown_service_has_no_provider():
    assert provider_for_service("on_prem_ad") is None
    assert provider_for_service(None) is None


def test_aliases_resolve():
    assert get_provider("m365").id == "microsoft"
    assert get_provider("M365").id == "microsoft"
    assert get_provider("google-cloud").id == "gcp"
    assert get_provider("workspace").id == "google_workspace"
    assert get_provider("nope") is None


def test_every_provider_has_services_and_collectors():
    for provider in PROVIDERS.values():
        assert provider.services
        assert provider.collectors
