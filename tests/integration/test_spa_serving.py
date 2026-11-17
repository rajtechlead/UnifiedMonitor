"""The built React app must be served by the API process.

The installer and Docker image both bundle the Vite build; before this test the
app mounted only `branding` at /static, so the UI was unreachable at /.
"""

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio


def _build_spa(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>UniMonitor UI</title>")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('unimonitor')")
    return tmp_path


class TestSpaServing:
    async def test_index_and_assets_are_served(self, tmp_path, monkeypatch):
        spa = _build_spa(tmp_path)
        monkeypatch.setenv("UNIMONITOR_STATIC_DIR", str(spa))

        from unimonitor.main import create_app

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            root = await client.get("/")
            assert root.status_code == 200
            assert "UniMonitor UI" in root.text

            asset = await client.get("/assets/app.js")
            assert asset.status_code == 200
            assert "unimonitor" in asset.text

    async def test_client_side_routes_fall_back_to_index(self, tmp_path, monkeypatch):
        spa = _build_spa(tmp_path)
        monkeypatch.setenv("UNIMONITOR_STATIC_DIR", str(spa))

        from unimonitor.main import create_app

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for route in ("/clouds", "/clouds/aws", "/ciso"):
                r = await client.get(route)
                assert r.status_code == 200, route
                assert "UniMonitor UI" in r.text, route

    async def test_api_routes_win_over_spa(self, tmp_path, monkeypatch):
        spa = _build_spa(tmp_path)
        monkeypatch.setenv("UNIMONITOR_STATIC_DIR", str(spa))

        from unimonitor.main import create_app

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            health = await client.get("/api/v1/health")
            assert health.status_code == 200
            assert health.json()["status"] == "ok"

            # an authenticated API path must not be swallowed by the SPA fallback
            unauthorized = await client.get("/api/v1/dashboard/clouds")
            assert unauthorized.status_code == 401
