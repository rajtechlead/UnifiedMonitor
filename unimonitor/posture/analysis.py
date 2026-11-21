"""Top-level posture analysis.

Runs every engine over one normalised snapshot and returns a single document so a
caller does not have to know which engines exist. Adding an engine here is the
only wiring needed for it to appear in the API and the UI.
"""

from __future__ import annotations

from typing import Any

from unimonitor.posture import aispm, ciem, cis, dspm, kubernetes, paths
from unimonitor.posture.findings import risk_score, sort_findings, summarise
from unimonitor.posture.inventory import by_type, normalise, summary

# Engines that are not tied to one cloud provider.
_ENGINES = (dspm, ciem, aispm, kubernetes, paths)


def supported_platforms() -> list[str]:
    return sorted(cis.BENCHMARKS)


def analyse(platform: str | None, payload: Any) -> dict[str, Any]:
    """Analyse *payload* and return inventory, benchmarks, engines and findings.

    ``platform`` selects the CIS pack. Without one, every pack is evaluated; a
    pack whose resources are absent from the snapshot scores ``None`` rather than
    passing, so the response never overstates coverage.
    """
    document = normalise(payload)
    resources = document["resources"]
    edges = document["edges"]
    groups = by_type(resources)

    if platform and platform not in cis.BENCHMARKS:
        benchmarks = []
    elif platform:
        benchmarks = [cis.evaluate_cis(platform, groups)]
    else:
        benchmarks = [cis.evaluate_cis(name, groups) for name in supported_platforms()]

    engines = {module.CATEGORY: module.analyse(resources, edges) for module in _ENGINES}
    combined = [finding for engine in engines.values() for finding in engine["findings"]]

    return {
        "platform": platform,
        "inventory": summary(document),
        "benchmarks": benchmarks,
        "engines": engines,
        "findings": sort_findings(combined),
        "summary": summarise(combined),
        "risk_score": risk_score(combined),
    }


__all__ = ["analyse", "supported_platforms"]
