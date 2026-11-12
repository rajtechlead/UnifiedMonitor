"""
Control Crosswalk Engine — maps controls across frameworks bidirectionally.
Given any control ID, returns its equivalents in all other frameworks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from unimonitor.grc.control_loader import load_all_controls
from unimonitor.grc.frameworks import FRAMEWORKS

if TYPE_CHECKING:
    from unimonitor.grc.control_loader import ControlDefinition


class FrameworkCrosswalk:
    """Index a list of ControlDefinition objects by their compliance mappings.

    Allows fast lookup: "which controls implement framework X, reference Y?"

    Usage::

        loader = ControlLoader(controls_dir=...)
        controls = loader.load_all()
        crosswalk = FrameworkCrosswalk(controls)
        matched = crosswalk.find_by_reference("iso_27001_2022", "A.9.4.2")
    """

    def __init__(self, controls: list["ControlDefinition"]) -> None:
        # index: { framework_id -> { reference_id -> [ControlDefinition, ...] } }
        self._index: dict[str, dict[str, list["ControlDefinition"]]] = {}
        self._controls = controls
        self._build_index()

    def _build_index(self) -> None:
        for ctrl in self._controls:
            mapping = getattr(ctrl, "compliance_mapping", {}) or {}
            for framework_key, refs in mapping.items():
                # Normalise framework key (strip underscores/dashes, lowercase)
                fw_id = framework_key.lower()
                if fw_id not in self._index:
                    self._index[fw_id] = {}
                ref_list: list[str]
                if isinstance(refs, list):
                    ref_list = [str(r) for r in refs]
                elif isinstance(refs, str):
                    ref_list = [refs]
                else:
                    ref_list = []
                for ref in ref_list:
                    if ref not in self._index[fw_id]:
                        self._index[fw_id][ref] = []
                    self._index[fw_id][ref].append(ctrl)

    def find_by_reference(
        self, framework_id: str, reference: str
    ) -> list["ControlDefinition"]:
        """Return controls that map *reference* in *framework_id*."""
        fw_id = framework_id.lower()
        return self._index.get(fw_id, {}).get(reference, [])

    def all_frameworks(self) -> list[str]:
        """Return all framework IDs present in the loaded controls."""
        return list(self._index.keys())

    def coverage_for_framework(self, framework_id: str) -> dict[str, list["ControlDefinition"]]:
        """Return the full reference→controls mapping for a framework."""
        return self._index.get(framework_id.lower(), {})


# Build crosswalk index at module load time (lazy singleton)
_crosswalk_index: dict[str, dict[str, list[str]]] | None = None


def _build_index() -> dict[str, dict[str, list[str]]]:
    """
    Returns: { control_id: { framework_id: [mapped_ids, ...] } }
    """
    controls = load_all_controls()
    index: dict[str, dict[str, list[str]]] = {}

    # Map of compliance_mapping keys to framework IDs
    fw_key_map = {
        "cis": "cis_controls_v8",
        "nist_800_53": "nist_800_53_r5",
        "iso_27001": "iso27001_2022",
        "cis_m365": "cis_m365_benchmark",
        "zero_trust": "zero_trust",
        "soc2": "soc2",
        "pci": "pci_dss_v4",
        "hipaa": "hipaa",
        "gdpr": "gdpr",
        "cmmc": "cmmc_2",
        "nist_csf": "nist_csf_2",
    }

    for ctrl in controls:
        ctrl_id = ctrl["id"]
        mapping = ctrl.get("compliance_mapping", {})
        fw_mappings: dict[str, list[str]] = {}

        for key, refs in mapping.items():
            fw_id = fw_key_map.get(key.lower())
            if fw_id and refs:
                if isinstance(refs, list):
                    ids = [r.get("id", str(r)) if isinstance(r, dict) else str(r) for r in refs]
                else:
                    ids = [str(refs)]
                fw_mappings[fw_id] = ids

        index[ctrl_id] = fw_mappings

    return index


def get_crosswalk_index() -> dict[str, dict[str, list[str]]]:
    global _crosswalk_index
    if _crosswalk_index is None:
        _crosswalk_index = _build_index()
    return _crosswalk_index


def crosswalk_for_control(control_id: str) -> dict[str, list[str]]:
    """Return all framework mappings for a given UniMonitor control ID."""
    index = get_crosswalk_index()
    return index.get(control_id, {})


def controls_for_framework(framework_id: str) -> list[dict]:
    """Return all UniMonitor controls that map to a given framework."""
    controls = load_all_controls()
    result = []
    for ctrl in controls:
        if framework_id in ctrl.get("frameworks", []):
            result.append(ctrl)
    return result


def gap_analysis(
    findings_by_control_id: dict[str, str],  # control_id -> state
    framework_id: str,
) -> dict:
    """
    Returns a gap analysis for a framework:
    - Gaps: controls not_implemented grouped by severity
    - Coverage summary
    """
    framework_controls = controls_for_framework(framework_id)
    gaps_by_severity: dict[str, list[dict]] = {
        "critical": [],
        "high": [],
        "medium": [],
        "low": [],
        "informational": [],
    }
    implemented = 0
    partial = 0
    not_implemented = 0
    not_applicable = 0

    for ctrl in framework_controls:
        ctrl_id = ctrl["id"]
        state = findings_by_control_id.get(ctrl_id, "not_implemented")

        if state == "implemented":
            implemented += 1
        elif state == "partially_implemented":
            partial += 1
        elif state == "not_applicable":
            not_applicable += 1
        else:
            not_implemented += 1
            sev = ctrl.get("severity", "medium")
            gaps_by_severity.get(sev, gaps_by_severity["medium"]).append({
                "control_id": ctrl_id,
                "name": ctrl["name"],
                "category": ctrl["category"],
                "remediation_summary": ctrl.get("remediation_summary", ""),
            })

    total = len(framework_controls) - not_applicable
    coverage_pct = round(((implemented + partial * 0.5) / total) * 100, 2) if total > 0 else 0.0

    return {
        "framework_id": framework_id,
        "framework_name": FRAMEWORKS.get(framework_id, type("", (), {"name": framework_id})()).name if framework_id in FRAMEWORKS else framework_id,
        "total_controls": len(framework_controls),
        "implemented": implemented,
        "partially_implemented": partial,
        "not_implemented": not_implemented,
        "not_applicable": not_applicable,
        "coverage_percent": coverage_pct,
        "gaps_by_severity": gaps_by_severity,
    }
