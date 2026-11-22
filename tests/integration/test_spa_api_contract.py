"""The SPA and the API must agree on names, not just on behaviour.

Three shape defects shipped in one round — a filter the SPA sent that the API never
declared, a dashboard field the SPA read that the API never returned, and a run
status that always said "pending" — and every one was invisible to both suites,
because each side was tested only against itself.

This test reads the API's own OpenAPI document and checks it against the calls in
``frontend/src/hooks/useApi.ts``: every path the SPA requests must exist, every query
parameter the SPA sends must be declared, and the fields the SPA reads must be in the
declared response. Adding a call to the SPA without the endpoint, or renaming a
response field, fails here instead of in a browser.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.asyncio

SPA_SOURCE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "hooks" / "useApi.ts"

_CALL = re.compile(r"""api\.(get|post|put|patch|delete)\(\s*[`'"]([^`'"]+)""")
_TEMPLATE = re.compile(r"\$\{[^}]*\}")
_PARAM = re.compile(r"\{[^}]*\}")


def _normalise(path: str) -> str:
    """Path-template parameter names do not have to match between client and server."""
    return _PARAM.sub("{}", path)


def _spa_paths() -> set[str]:
    assert SPA_SOURCE.exists(), f"SPA API module not found at {SPA_SOURCE}"
    source = SPA_SOURCE.read_text()
    paths: set[str] = set()
    for _method, raw in _CALL.findall(source):
        if not raw.startswith("/"):
            continue
        paths.add(_normalise(_TEMPLATE.sub("{}", raw)))
    return paths


@pytest.fixture(scope="module")
def contract() -> dict:
    """OpenAPI paths, keyed by the normalised path."""
    from unimonitor.main import app

    schema = app.openapi()
    operations: dict[str, dict[str, dict]] = {}
    for path, item in schema["paths"].items():
        methods = {method: op for method, op in item.items() if method in {"get", "post", "put", "patch", "delete"}}
        if methods:
            operations[_normalise(path.removeprefix("/api/v1"))] = methods
    return {"schema": schema, "operations": operations}


def _resolve(schema: dict, ref_or_schema: dict) -> dict:
    """Follow a local ``$ref`` (one level of nesting is all these responses use)."""
    seen = 0
    current = ref_or_schema
    while "$ref" in current and seen < 5:
        node: dict = schema
        for part in current["$ref"].removeprefix("#/").split("/"):
            node = node[part]
        current = node
        seen += 1
    return current


def _response_properties(contract: dict, path: str, method: str = "get") -> dict[str, dict]:
    operation = contract["operations"][path][method]
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    return _resolve(contract["schema"], schema).get("properties", {})


def _item_properties(contract: dict, path: str, method: str = "get") -> dict[str, dict]:
    """Properties of the elements of a paginated ``{items: [...]}`` response."""
    items = _response_properties(contract, path, method).get("items", {})
    resolved = _resolve(contract["schema"], items)
    if resolved.get("type") == "array":
        resolved = _resolve(contract["schema"], resolved.get("items", {}))
    return resolved.get("properties", {})


class TestEverySpaPathExists:
    async def test_spa_calls_only_endpoints_the_api_serves(self, contract):
        spa = _spa_paths()
        # A regex or refactor change must not make this test vacuous.
        assert len(spa) >= 25, f"only {len(spa)} SPA calls parsed: {sorted(spa)}"

        unknown = sorted(path for path in spa if path not in contract["operations"])
        assert not unknown, f"the SPA calls paths the API does not serve: {unknown}"

    async def test_a_bogus_spa_path_would_be_caught(self, contract):
        assert "/definitely-not-a-route" not in contract["operations"]


# Query parameters the SPA builds in pages (they are not visible in the API module).
SPA_QUERY_PARAMS: dict[str, set[str]] = {
    "/findings": {
        "search",
        "severity",
        "state",
        "triage_status",
        "category",
        "sort_by",
        "sort_desc",
        "page",
        "page_size",
        "tenant_id",
    },
    "/findings/summary": {"tenant_id"},
    "/findings/priority": {"tenant_id"},
    "/zerotrust/mapping": {"source"},
    "/zerotrust/evidence-gaps": {"source"},
    "/reports/runs": {"page", "page_size", "tenant_id"},
    "/notifications/settings": {"tenant_id"},
    "/notifications/test": {"tenant_id"},
}


class TestQueryParametersAreDeclared:
    @pytest.mark.parametrize(("path", "params"), sorted(SPA_QUERY_PARAMS.items()))
    async def test_every_parameter_the_spa_sends_is_declared(self, contract, path, params):
        assert path in contract["operations"], f"{path} is not served by the API"
        methods = contract["operations"][path]
        declared = {
            parameter["name"] for operation in methods.values() for parameter in operation.get("parameters", []) if parameter.get("in") == "query"
        }
        missing = sorted(params - declared)
        assert not missing, f"{path} ignores parameters the SPA sends: {missing} (declared: {sorted(declared)})"


# Fields the SPA reads, on the endpoints whose shapes have broken before.
SPA_READ_FIELDS: dict[str, tuple[str, set[str]]] = {
    "/dashboard/soc": ("root", {"alerts_by_severity", "incident_trend", "active_alerts", "acknowledged_alerts"}),
    "/dashboard/ciso": ("root", {"strongest_frameworks", "weakest_frameworks", "state_totals"}),
    "/dashboard/risk": ("root", {"risks", "critical_risks", "overall_risk_score", "heatmap"}),
    "/findings": ("items", {"id", "title", "severity", "state", "triage_status", "category"}),
    "/assessments/{}/runs": ("items", {"id", "status", "error_message", "findings_count", "triggered_by"}),
}


class TestReadableFieldsAreReturned:
    @pytest.mark.parametrize(("path", "spec"), sorted(SPA_READ_FIELDS.items()))
    async def test_fields_the_spa_reads_are_in_the_response_schema(self, contract, path, spec):
        where, fields = spec
        assert path in contract["operations"], f"{path} is not served by the API"
        properties = _response_properties(contract, path) if where == "root" else _item_properties(contract, path)
        missing = sorted(fields - set(properties))
        assert not missing, f"{path} does not return {missing} (returns {sorted(properties)})"


class TestTheSchemaIsNotVacuous:
    async def test_the_endpoints_under_test_are_in_the_schema(self, contract):
        for path, (_, fields) in SPA_READ_FIELDS.items():
            assert path in contract["operations"], path
            assert fields, path
