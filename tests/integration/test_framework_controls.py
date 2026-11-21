"""Framework control drill-down: state and evidence per mapped control."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_framework_controls_report_state_and_evidence(client: AsyncClient, auth_headers: dict, db_session, tenant) -> None:
    from unimonitor.db.models.finding import Finding
    from unimonitor.grc.control_loader import ControlLoader

    control = next(item for item in ControlLoader().load_all() if {"iso27001-2022", "iso27001_2022"} & set(item.compliance_mapping))
    db_session.add(
        Finding(
            tenant_id=tenant.id,
            external_control_id=control.id,
            title=control.title,
            description="seeded for the framework drill-down",
            severity="high",
            state="implemented",
            category=control.category,
            service=control.service,
        )
    )
    await db_session.flush()

    response = await client.get("/api/v1/grc/frameworks/iso27001-2022/controls", headers=auth_headers)
    assert response.status_code == 200, response.text
    rows = {row["external_id"]: row for row in response.json()}

    assert rows[control.id]["state"] == "implemented"
    assert rows[control.id]["finding_id"]
    assert "remediation" in rows[control.id]
    # A mapped control with no collection yet is "not_run", never an assumed pass.
    assert any(row["state"] == "not_run" for row in rows.values())


@pytest.mark.asyncio
async def test_every_framework_lists_every_mapped_control(client: AsyncClient, auth_headers: dict) -> None:
    """A framework page must never silently drop a control mapped to it."""
    from unimonitor.api.v1.controls import SUPPORTED_FRAMEWORKS
    from unimonitor.grc.control_loader import controls_for_framework

    coverage = await client.get("/api/v1/grc/frameworks", headers=auth_headers)
    totals = {row["framework_id"]: row["controls_total"] for row in coverage.json()}

    for framework in SUPPORTED_FRAMEWORKS:
        expected = {control.id for control in controls_for_framework(framework["id"])}
        response = await client.get(f"/api/v1/grc/frameworks/{framework['id']}/controls", headers=auth_headers)
        assert response.status_code == 200, framework["id"]
        listed = {row["external_id"] for row in response.json()}
        assert listed == expected, f"{framework['id']} lists {len(listed)} of {len(expected)} controls"
        assert totals[framework["id"]] == len(expected), framework["id"]

    # Frameworks whose YAML key differs from their API id used to list nothing.
    assert totals["microsoft-zero-trust"] == 97
    assert totals["cis-m365"] == 82
    assert totals["pci-dss-4"] == 30
    assert totals["iso27001-2022"] == 190


@pytest.mark.asyncio
async def test_control_library_lists_all_controls(client: AsyncClient, auth_headers: dict) -> None:
    """The control library endpoints read the YAML library and work end to end."""
    from unimonitor.grc.control_loader import ControlLoader

    total = len(ControlLoader().load_all())
    listing = await client.get("/api/v1/controls", params={"page_size": 200}, headers=auth_headers)
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == total

    framework = await client.get("/api/v1/controls/frameworks/microsoft-zero-trust", headers=auth_headers)
    assert framework.status_code == 200, framework.text
    assert framework.json()["total_controls"] == 97

    single = await client.get("/api/v1/controls/CTRL-AWS-001", headers=auth_headers)
    assert single.status_code == 200, single.text
    assert any(mapping["framework"] == "microsoft-zero-trust" for mapping in single.json()["framework_mappings"])

    filtered = await client.get("/api/v1/controls", params={"framework": "pci-dss-4", "page_size": 200}, headers=auth_headers)
    assert filtered.json()["total"] == 30


@pytest.mark.asyncio
async def test_every_supported_framework_has_controls(client: AsyncClient, auth_headers: dict) -> None:
    """CPCSC and the 2026-framework additions must never be empty placeholders."""
    from unimonitor.api.v1.controls import SUPPORTED_FRAMEWORKS
    from unimonitor.grc.control_loader import controls_for_framework

    assert len(SUPPORTED_FRAMEWORKS) >= 33
    for framework in SUPPORTED_FRAMEWORKS:
        controls = controls_for_framework(framework["id"])
        assert controls, f"{framework['id']} has no mapped controls"
        assert framework["mapping_note"] or controls, framework["id"]

    # CPCSC resolves all 98 ITSP.10.171 requirements; its Level 1 criteria sit in
    # the access-control, auth, media, physical, communications and integrity families.
    cpcsc = controls_for_framework("cpcsc")
    ids = {control.id for control in cpcsc}
    assert {"CTRL-ENT-001", "CTRL-AWS-001", "CTRL-INT-001", "CTRL-DEF-001"} <= ids
    # FedRAMP baselines derive from the NIST 800-53 mapping.
    assert len(controls_for_framework("fedramp-moderate")) == len(controls_for_framework("nist-800-53-r5"))


def test_framework_key_map_is_generated_and_complete() -> None:
    """Every registry entry resolves through every id form, and no rule is orphaned."""
    from unimonitor.grc.framework_mappings import DERIVED, EXPLICIT
    from unimonitor.grc.frameworks import FRAMEWORK_KEYS, FRAMEWORKS, framework_id_for_key, framework_keys

    slugs = {meta.slug for meta in FRAMEWORKS.values()}
    assert set(FRAMEWORK_KEYS) == slugs, "the key map must be generated from the registry"

    for meta in FRAMEWORKS.values():
        keys = framework_keys(meta.id)
        assert meta.slug in keys, meta.slug
        assert framework_id_for_key(meta.id) == meta.slug, meta.slug
        assert framework_id_for_key(meta.slug) == meta.slug, meta.slug
        assert framework_keys(meta.slug) == keys, meta.slug

    # A mapping rule for a framework nobody registered would never be reached.
    assert set(EXPLICIT) | set(DERIVED) <= slugs
    for slug, rule in DERIVED.items():
        if "source" in rule:
            assert rule["source"] in slugs, f"{slug} derives from unknown source {rule['source']}"

    # Legacy YAML keys resolve even when passed in their underscored form.
    assert framework_id_for_key("zero_trust") == "microsoft-zero-trust"
    assert "zero_trust" in framework_keys("microsoft_zero_trust")


@pytest.mark.asyncio
async def test_unknown_framework_is_404(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.get("/api/v1/grc/frameworks/not-a-framework/controls", headers=auth_headers)
    assert response.status_code == 404
