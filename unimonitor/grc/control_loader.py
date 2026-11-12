"""
Control loader — reads YAML control definitions from the controls/ directory
and resolves framework mappings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from unimonitor.core.logging import get_logger

logger = get_logger(__name__)

# Controls directory, relative to the project root
CONTROLS_DIR = Path(__file__).resolve().parents[2] / "controls"


# ── ControlDefinition dataclass ───────────────────────────────

@dataclass
class ControlDefinition:
    """A parsed control definition from YAML, exposing the test-expected API."""

    id: str
    title: str
    severity: str
    category: str
    service: str
    compliance_mapping: dict
    collector: str = ""
    data_path: str = ""
    _evaluate_code: str = field(default="", repr=False)

    def run_evaluate(self, data: dict) -> str:
        """Execute the ``evaluate(data)`` function defined in the YAML and return the result."""
        namespace: dict = {}
        try:
            exec(self._evaluate_code, namespace)  # noqa: S102
            return namespace["evaluate"](data)
        except Exception as exc:
            logger.warning("evaluate_error", control_id=self.id, error=str(exc))
            return "error"


# ── ControlLoader class ───────────────────────────────────────

class ControlLoader:
    """Load :class:`ControlDefinition` objects from a directory of YAML files.

    YAML format (new list-based format, also used by tests)::

        controls:
          - id: CTRL-001
            title: "MFA Enforcement"
            severity: CRITICAL
            category: identity
            service: entra_id
            compliance_mapping:
              iso_27001_2022: ["A.9.4.2"]
            evaluate: |
              def evaluate(data):
                  return "implemented" if data.get("mfa") else "not_implemented"

    Also supports legacy flat-dict YAML (single control per file with
    ``control_id`` / ``metadata`` / ``check`` / ``remediation`` keys).
    """

    def __init__(self, controls_dir: str | None = None) -> None:
        self.controls_dir = Path(controls_dir) if controls_dir else CONTROLS_DIR

    def load_all(self) -> list[ControlDefinition]:
        """Return all :class:`ControlDefinition` objects found under *controls_dir*."""
        definitions: list[ControlDefinition] = []
        if not self.controls_dir.exists():
            logger.warning("controls_dir_not_found", path=str(self.controls_dir))
            return definitions

        for yaml_file in self.controls_dir.rglob("*.yaml"):
            data = _load_yaml_file(yaml_file)
            if not data:
                continue

            if isinstance(data, dict) and "controls" in data:
                # New list format
                for ctrl in data["controls"]:
                    defn = _parse_list_format(ctrl)
                    if defn:
                        definitions.append(defn)
            elif isinstance(data, dict) and "control_id" in data:
                # Legacy flat-dict format
                defn = _parse_legacy_format(data, yaml_file)
                if defn:
                    definitions.append(defn)

        logger.info("controls_loaded", count=len(definitions), path=str(self.controls_dir))
        return definitions


# ── Parsing helpers ───────────────────────────────────────────

def _parse_list_format(ctrl: dict) -> ControlDefinition | None:
    """Parse a single control entry from the list-based YAML format."""
    ctrl_id = ctrl.get("id", "")
    if not ctrl_id:
        return None

    raw_eval = ctrl.get("evaluate", "")
    if raw_eval and raw_eval.strip():
        # Determine if already a proper function definition
        stripped = raw_eval.strip()
        if stripped.startswith("def evaluate("):
            # Already a proper function — use as-is
            _evaluate_code = raw_eval
        else:
            # Bare code block (top-level return statements) — wrap it
            indented = "\n".join("    " + line for line in raw_eval.splitlines())
            _evaluate_code = f"def evaluate(data):\n{indented}"
    else:
        _evaluate_code = "def evaluate(data): return 'not_implemented'"

    return ControlDefinition(
        id=ctrl_id,
        title=ctrl.get("title", ctrl_id),
        severity=(ctrl.get("severity") or "MEDIUM").upper(),
        category=ctrl.get("category", ""),
        service=ctrl.get("service", ""),
        compliance_mapping=ctrl.get("compliance_mapping", {}),
        collector=ctrl.get("collector", ""),
        data_path=ctrl.get("data_path", ""),
        _evaluate_code=_evaluate_code,
    )


def _parse_legacy_format(raw: dict, path: Path) -> ControlDefinition | None:
    """Parse a legacy flat-dict YAML control (single control per file)."""
    ctrl_id = raw.get("control_id", "")
    if not ctrl_id:
        return None
    metadata = raw.get("metadata", {})
    check = raw.get("check", {})
    compliance = raw.get("compliance_mapping", {})
    service = path.parent.name

    # Build evaluate code from check.evaluation dict
    eval_code = "def evaluate(data): return 'not_implemented'"
    evaluation = check.get("evaluation", {})
    if evaluation:
        condition = evaluation.get("condition", "")
        if condition:
            eval_code = (
                f"def evaluate(data):\n"
                f"    return 'implemented' if {condition} else 'not_implemented'"
            )

    return ControlDefinition(
        id=ctrl_id,
        title=metadata.get("name", ctrl_id),
        severity=(metadata.get("severity") or "MEDIUM").upper(),
        category=service.title(),
        service=service,
        compliance_mapping=compliance,
        _evaluate_code=eval_code,
    )


def _load_yaml_file(path: Path) -> dict | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as exc:
        logger.warning("Failed to load control YAML", path=str(path), error=str(exc))
        return None


def load_all_controls() -> list[dict]:
    """Return all control definitions from the controls/ directory."""
    controls: list[dict] = []
    if not CONTROLS_DIR.exists():
        logger.warning("Controls directory not found", path=str(CONTROLS_DIR))
        return controls

    for yaml_file in CONTROLS_DIR.rglob("*.yaml"):
        data = _load_yaml_file(yaml_file)
        if data and isinstance(data, dict) and "control_id" in data:
            # Normalise to flat dict expected by the engine
            ctrl = _normalise(data, yaml_file)
            controls.append(ctrl)

    logger.info("Controls loaded from disk", count=len(controls))
    return controls


def load_controls_for_frameworks(framework_ids: list[str]) -> list[dict]:
    """Return controls that belong to any of the given frameworks."""
    all_controls = load_all_controls()
    if not framework_ids:
        return all_controls

    framework_set = set(framework_ids)
    filtered = []
    for ctrl in all_controls:
        ctrl_frameworks = set(ctrl.get("frameworks", []))
        if ctrl_frameworks & framework_set or "all" in framework_set:
            filtered.append(ctrl)

    # Also include controls not explicitly tagged — treat them as universal
    if not filtered:
        return all_controls

    return filtered


def _normalise(raw: dict, path: Path) -> dict:
    """Convert raw YAML structure to the flat dict the engine expects."""
    metadata = raw.get("metadata", {})
    check = raw.get("check", {})
    remediation = raw.get("remediation", {})
    compliance = raw.get("compliance_mapping", {})

    # Build framework list from compliance_mapping keys
    frameworks: list[str] = []
    for fw_key in compliance:
        fw_map = {
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
        }
        fw_id = fw_map.get(fw_key.lower())
        if fw_id:
            frameworks.append(fw_id)

    # Determine service from path
    service = path.parent.name  # e.g. "identity", "devices"

    # Category from control_id prefix
    ctrl_id = raw.get("control_id", "UNKNOWN")
    prefix = ctrl_id.split("-")[0].upper() if "-" in ctrl_id else ctrl_id[:3].upper()
    category_map = {
        "APP": "Applications",
        "DEV": "Devices",
        "MON": "Security Operations",
        "OPS": "Operations",
        "IDN": "Identity",
        "ZT": "Zero Trust",
        "ENT": "Entra ID",
        "INT": "Intune",
        "DEF": "Defender",
        "PUR": "Purview",
        "EXO": "Exchange",
        "SPO": "SharePoint",
        "TMS": "Teams",
        "AZR": "Azure",
    }
    category = category_map.get(prefix, service.title())

    # Data keys required from collector
    data_requirements = check.get("data_requirements", [])
    data_keys: list[str] = []
    for req in data_requirements:
        ep = req.get("endpoint", "")
        # Map endpoint to collector data key
        key = ep.strip("/").replace("/", "_").lower()
        data_keys.append(key)

    return {
        "id": ctrl_id,
        "name": metadata.get("name", ctrl_id),
        "description": metadata.get("description", ""),
        "severity": metadata.get("severity", "medium"),
        "category": category,
        "service": service,
        "frameworks": frameworks,
        "data_keys": data_keys,
        "evaluation": check.get("evaluation"),
        "remediation_steps": [
            s.get("action", "") for s in remediation.get("steps", [])
        ],
        "remediation_summary": remediation.get("summary", ""),
        "compliance_mapping": compliance,
        "tags": metadata.get("tags", []),
    }
