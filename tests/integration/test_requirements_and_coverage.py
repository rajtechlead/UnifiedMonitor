"""Requirement-level reporting and per-provider evidence coverage."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_every_framework_offers_a_requirement_catalogue(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/grc/frameworks/nis2/requirements", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["catalogue"] == "mapping"
    assert body["requirement_count"] == len(body["rows"])
    assert body["rows"][0]["controls"]


async def test_a_derived_framework_reports_its_level_name(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/grc/frameworks/fedramp-low/requirements", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["catalogue"] == "derived"
    assert {level["name"] for level in body["levels"]} == {"Low"}
    assert all(row["level_name"] == "Low" for row in body["rows"])


async def test_level_filter_narrows_the_catalogue(client: AsyncClient, auth_headers: dict):
    all_rows = await client.get("/api/v1/grc/frameworks/cpcsc/requirements", headers=auth_headers)
    level2 = await client.get("/api/v1/grc/frameworks/cpcsc/requirements?level=2", headers=auth_headers)
    assert level2.status_code == 200, level2.text
    assert 0 < len(level2.json()["rows"]) < all_rows.json()["requirement_count"]
    assert all(row["level"] == 2 for row in level2.json()["rows"])


async def test_evidence_coverage_is_broken_down_by_provider(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/grc/frameworks/iso27001-2022/evidence-coverage", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    coverage = body["by_provider"]
    assert coverage["providers"]
    assert coverage["missing_providers"] == ["aws", "gcp", "google_workspace", "microsoft"]
    assert sum(entry["controls"] for entry in coverage["providers"].values()) == body["total_controls"]
