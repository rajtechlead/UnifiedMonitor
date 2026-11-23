"""Evidence coverage: which Zero Trust controls have collector data behind them.

A control can only be evaluated when the collector returned the data keys its
``evaluate`` function reads. This module answers two questions without needing a
live tenant:

* which keys does each control expect, and does any collector produce them?
* which Zero Trust tests/controls in the latest run have no evidence at all?

Runtime evidence comes from the ``data_coverage`` record the assessment engine
attaches to each finding. Static coverage compares the control YAML against the
collector source, so a control that no collector can ever satisfy is reported as a
build-time gap instead of a permanent silent failure.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.db.models.finding import Finding, FindingEvidence
from unimonitor.grc.control_loader import ControlDefinition, ControlLoader
from unimonitor.zerotrust.platform_tests import tests_for
from unimonitor.zerotrust.service import PLATFORM_SERVICES, _finding_states

COLLECTORS_DIR = Path(__file__).resolve().parents[1] / "graph" / "collectors"
REGISTRY_FILE = Path(__file__).resolve().parents[1] / "graph" / "collector_registry.py"

# Control service -> the collector that is expected to return its data.
SERVICE_COLLECTOR: dict[str, str] = {
    "entra_id": "entra_id",
    "intune": "intune",
    "defender": "defender",
    "defender_office": "defender (defender_office)",
    "defender_cloud_apps": "defender (defender_cloud_apps)",
    "defender_identity": "defender (defender_identity)",
    "purview": "purview",
    "purview_insider_risk": "purview (purview_insider_risk)",
    "purview_ediscovery": "purview (purview_ediscovery)",
    "exchange": "exchange",
    "sharepoint": "sharepoint",
    "teams": "teams",
    "copilot_m365": "copilot",
    "copilot_studio": "posture snapshot (UNIMONITOR_POSTURE_SNAPSHOT)",
    "azure_security": "azure_security",
    "aws": "collect_aws",
    "gcp": "collect_gcp",
    "google_workspace": "collect_google_workspace",
}

# Data keys mix snake_case (cloud) and camelCase (Graph) spellings.
_DATA_GET = re.compile(r"data(?:\.get\(\s*|\[\s*)[\"'](\w+)[\"']")
_QUOTED = re.compile(r"[\"']([A-Za-z]\w{3,})[\"']")


def expected_keys(control: ControlDefinition) -> set[str]:
    """Data keys a control's ``evaluate`` function reads."""
    code = getattr(control, "_evaluate_code", "")
    if not isinstance(code, str):
        return set()
    return set(_DATA_GET.findall(code))


@lru_cache(maxsize=1)
def collector_keys() -> dict[str, set[str]]:
    """Keys each collector module mentions, plus registry-level ``_safe_get`` keys."""
    produced: dict[str, set[str]] = {}
    for path in COLLECTORS_DIR.glob("*.py"):
        produced[path.stem] = set(_QUOTED.findall(path.read_text(encoding="utf-8")))
    registry = set(_QUOTED.findall(REGISTRY_FILE.read_text(encoding="utf-8")))
    produced["collector_registry"] = registry
    produced["posture snapshot (UNIMONITOR_POSTURE_SNAPSHOT)"] = set()
    # Sub-collectors (defender_office, ...) are implemented in the extended module.
    produced["defender (defender_office)"] = produced.get("extended", set())
    produced["defender (defender_cloud_apps)"] = produced.get("extended", set())
    produced["defender (defender_identity)"] = produced.get("extended", set())
    produced["purview (purview_insider_risk)"] = produced.get("extended", set())
    produced["purview (purview_ediscovery)"] = produced.get("extended", set())
    produced["collect_aws"] = produced.get("cloud_providers", set())
    produced["collect_gcp"] = produced.get("cloud_providers", set())
    produced["collect_google_workspace"] = produced.get("cloud_providers", set())
    return produced


def static_missing_keys(control: ControlDefinition) -> list[str]:
    """Expected keys that no collector produces (they need a new collector or snapshot)."""
    keys = expected_keys(control)
    if not keys:
        return []
    collector = SERVICE_COLLECTOR.get(control.service, "")
    produced = collector_keys().get(collector, set())
    # Graph gateway keys (e.g. "organization") live in the registry, not the module.
    produced = produced | collector_keys().get("collector_registry", set())
    return sorted(key for key in keys if key not in produced)


@dataclass
class ControlEvidence:
    id: str
    title: str
    service: str
    pillar: str
    collector: str
    expected_keys: list[str]
    missing_keys: list[str]
    uncollected_keys: list[str]
    state: str | None
    has_finding: bool
    has_evidence: bool


@dataclass
class TestEvidence:
    check_id: str
    title: str
    pillar: str
    reason: str
    controls: list[ControlEvidence] = field(default_factory=list)


@dataclass
class PlatformCoverage:
    source: str
    platform: str
    tests_total: int
    tests_evidenced: int
    controls_total: int
    controls_lacking: int
    gaps: list[TestEvidence]
    controls: list[ControlEvidence]


def _runtime_coverage(rows: list[Any]) -> dict[str, dict[str, Any]]:
    """Latest ``data_coverage`` evidence per control, from the newest finding."""
    coverage: dict[str, dict[str, Any]] = {}
    for content, external_id, collected_at in rows:
        try:
            payload = json.loads(content)
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        current = coverage.get(external_id)
        if current is None or collected_at >= current["at"]:
            coverage[external_id] = {"at": collected_at, **payload}
    return coverage


async def _coverage_rows(db: AsyncSession, tenant_id: str) -> list[Any]:
    stmt = (
        select(FindingEvidence.content, Finding.external_control_id, FindingEvidence.collected_at)
        .join(Finding, FindingEvidence.finding_id == Finding.id)
        .where(Finding.tenant_id == tenant_id, FindingEvidence.evidence_type == "data_coverage")
    )
    return list((await db.execute(stmt)).all())


def _control_evidence(control: ControlDefinition, states: dict[str, str], coverage: dict[str, dict[str, Any]]) -> ControlEvidence:
    from unimonitor.zerotrust.service import _control_pillar

    recorded = coverage.get(control.id, {})
    return ControlEvidence(
        id=control.id,
        title=control.title,
        service=control.service,
        pillar=_control_pillar(control.compliance_mapping) or "infrastructure",
        collector=SERVICE_COLLECTOR.get(control.service, control.collector or "unknown"),
        expected_keys=sorted(expected_keys(control)),
        missing_keys=list(recorded.get("missing") or []),
        uncollected_keys=static_missing_keys(control),
        state=states.get(control.id),
        has_finding=control.id in states,
        has_evidence=bool(recorded) and not recorded.get("missing"),
    )


async def platform_coverage(db: AsyncSession, tenant_id: str, platform: str) -> PlatformCoverage:
    """Which controls and tests have evidence for one platform."""
    from unimonitor.zerotrust.normalise import PLATFORMS

    states = await _finding_states(db, tenant_id)
    coverage = _runtime_coverage(await _coverage_rows(db, tenant_id))
    services = set(PLATFORM_SERVICES.get(platform, (platform,)))
    controls = {control.id: control for control in ControlLoader().load_all() if control.service in services}

    evidence = {control_id: _control_evidence(control, states, coverage) for control_id, control in controls.items()}

    tests = tests_for(platform)
    if tests:
        evidenced, gaps = _mapped_gaps(tests, evidence)
    else:
        evidenced, gaps = _unmapped_gaps(evidence)

    lacking = [item for item in evidence.values() if not item.has_evidence]
    return PlatformCoverage(
        source=platform,
        platform=PLATFORMS.get(platform, platform),
        tests_total=len(tests) or len(controls),
        tests_evidenced=evidenced,
        controls_total=len(controls),
        controls_lacking=len(lacking),
        gaps=gaps,
        controls=list(evidence.values()),
    )


def _gap_reason(item: ControlEvidence) -> str:
    if item.uncollected_keys:
        return (
            f"No collector produces {', '.join(item.uncollected_keys)} yet — extend {item.collector or 'the collector'} or supply a posture snapshot."
        )
    if item.missing_keys:
        return f"The collector did not return: {', '.join(item.missing_keys)}."
    if not item.has_finding:
        return "This control has not been assessed yet."
    return "The finding carries no collector evidence."


def _mapped_gaps(tests: Sequence[Any], evidence: dict[str, Any]) -> tuple[int, list[TestEvidence]]:
    """Gaps for a platform whose tests map to controls."""
    gaps: list[TestEvidence] = []
    evidenced = 0
    for test in tests:
        mapped = [evidence[cid] for cid in test.control_ids if cid in evidence]
        if not mapped:
            gaps.append(TestEvidence(test.id, test.title, test.pillar, "No UniMonitor control collects evidence for this test."))
            continue
        if any(item.has_evidence for item in mapped):
            evidenced += 1
            continue
        reason = (
            "Mapped controls have not been assessed yet."
            if not any(item.has_finding for item in mapped)
            else "Collector data for the mapped controls is incomplete."
        )
        gaps.append(TestEvidence(test.id, test.title, test.pillar, reason, mapped))
    return evidenced, gaps


def _unmapped_gaps(evidence: dict[str, Any]) -> tuple[int, list[TestEvidence]]:
    """Microsoft: a test with no mapped control is a mapping gap, reported by the
    mapping endpoint, so here we report controls with no runtime evidence."""
    gaps = [TestEvidence(item.id, item.title, item.pillar, _gap_reason(item), [item]) for item in evidence.values() if not item.has_evidence]
    return sum(1 for item in evidence.values() if item.has_evidence), gaps
