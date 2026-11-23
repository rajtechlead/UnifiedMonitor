"""The diagnostics bundle: redacted, in memory, admin only."""

from __future__ import annotations

import io
import json
import zipfile

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

URL = "/api/v1/settings/diagnostics"


async def test_the_bundle_is_a_zip_with_a_redacted_manifest(client: AsyncClient, auth_headers: dict):
    response = await client.get(URL, headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert "manifest.json" in archive.namelist()
        manifest = json.loads(archive.read("manifest.json"))

    assert manifest["application"]["name"] == "UniMonitor"
    assert "collectors" in manifest
    assert "tenants" in manifest["inventory"]
    # Credential-shaped keys are present but never carry their value.
    configuration = manifest["configuration"]
    for key in ("UNIMONITOR_SECRET_KEY", "TENANT_CLIENT_SECRET", "DATABASE_URL"):
        if key in configuration:
            assert configuration[key] == "<redacted>"


async def test_the_bundle_requires_an_administrator(client: AsyncClient):
    assert (await client.get(URL)).status_code == 401
