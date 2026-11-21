"""
Control loader — reads YAML control definitions from the controls/ directory
and resolves framework mappings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from unimonitor.core.logging import get_logger

logger = get_logger(__name__)

# Controls directory, relative to the project root
CONTROLS_DIR = Path(__file__).resolve().parents[2] / "controls"


# Map legacy pass/fail to canonical finding states (module-level constants)
_RESULT_MAP: dict[str, str] = {
    "pass": "implemented",
    "fail": "not_implemented",
    "partial": "partially_implemented",
    "n/a": "not_applicable",
    "na": "not_applicable",
}
_VALID_STATES: frozenset[str] = frozenset({"implemented", "partially_implemented", "not_implemented", "not_applicable"})


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
    description: str = ""
    # Remediation ROI inputs: security impact (1–10) and effort/complexity (1–5).
    # Optional; findings fall back to the severity weight and an effort of 3.
    impact: int = 0
    effort: int = 3
    # Remediation carried by the control itself, shown in the Zero Trust assessment
    # and the control library. Empty when the YAML has no ``remediation`` block.
    remediation_summary: str = ""
    remediation_steps: list[str] = field(default_factory=list)
    # Microsoft Zero Trust Assessment tests this control provides evidence for.
    # The Zero Trust engine reports every upstream test and fills its result from
    # the control's finding, so the mapping is what makes a test evaluated.
    ms_zt_tests: list[str] = field(default_factory=list)
    _evaluate_code: str = field(default="", repr=False)

    def run_evaluate(self, data: dict) -> str:
        """Execute the ``evaluate(data)`` function defined in the YAML and return the result.

        Normalises legacy ``pass`` / ``fail`` return values to canonical
        finding states (``implemented`` / ``not_implemented``).
        """
        namespace: dict = {}
        try:
            exec(self._evaluate_code, namespace)  # noqa: S102
            raw: str = namespace["evaluate"](data)
        except Exception as exc:
            logger.warning("evaluate_error", control_id=self.id, error=str(exc))
            return "error"
        # Normalise to canonical finding states
        normalised = _RESULT_MAP.get(str(raw).lower(), raw)
        if normalised not in _VALID_STATES:
            logger.warning(
                "evaluate_unexpected_result",
                control_id=self.id,
                raw=raw,
                normalised=normalised,
            )
        return normalised


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
            definitions.extend(_definitions_from_file(data, yaml_file))

        logger.info("controls_loaded", count=len(definitions), path=str(self.controls_dir))
        return definitions


def _definitions_from_file(data: dict, yaml_file: Path) -> list[ControlDefinition]:
    """Parse one YAML document in either the list or the legacy flat format."""
    if "controls" in data:
        definitions: list[ControlDefinition] = []
        for ctrl in data["controls"]:
            defn = _parse_list_format(ctrl)
            if defn:
                definitions.append(defn)
        return definitions
    if "control_id" in data:
        legacy = _parse_legacy_format(data, yaml_file)
        return [legacy] if legacy else []
    return []


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

    remediation_summary, remediation_steps = _parse_remediation(ctrl.get("remediation"))

    return ControlDefinition(
        id=ctrl_id,
        title=ctrl.get("title", ctrl_id),
        severity=(ctrl.get("severity") or "MEDIUM").upper(),
        category=ctrl.get("category", ""),
        service=ctrl.get("service", ""),
        compliance_mapping=ctrl.get("compliance_mapping", {}),
        collector=ctrl.get("collector", ""),
        data_path=ctrl.get("data_path", ""),
        description=ctrl.get("description", "") or "",
        impact=int(ctrl.get("impact", 0) or 0),
        effort=int(ctrl.get("effort", 3) or 3),
        remediation_summary=remediation_summary,
        remediation_steps=remediation_steps,
        ms_zt_tests=[str(test_id) for test_id in (ctrl.get("ms_zt_tests") or [])],
        _evaluate_code=_evaluate_code,
    )


def _parse_remediation(raw: object) -> tuple[str, list[str]]:
    """Read a ``remediation`` block written either as text or as summary/steps."""
    if isinstance(raw, str):
        return raw.strip(), []
    if not isinstance(raw, dict):
        return "", []
    summary = str(raw.get("summary", "") or "")
    steps: list[str] = []
    for step in raw.get("steps", []) or []:
        if isinstance(step, dict):
            action = str(step.get("action", "") or "")
            if action:
                steps.append(action)
        elif step:
            steps.append(str(step))
    return summary, steps


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
            eval_code = f"def evaluate(data):\n    return 'implemented' if {condition} else 'not_implemented'"

    return ControlDefinition(
        id=ctrl_id,
        title=metadata.get("name", ctrl_id),
        severity=(metadata.get("severity") or "MEDIUM").upper(),
        category=service.title(),
        service=service,
        compliance_mapping=compliance,
        description=str(metadata.get("description", "") or ""),
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
        "remediation_steps": [s.get("action", "") for s in remediation.get("steps", [])],
        "remediation_summary": remediation.get("summary", ""),
        "compliance_mapping": compliance,
        "tags": metadata.get("tags", []),
    }


@lru_cache(maxsize=1)
def all_controls() -> tuple[ControlDefinition, ...]:
    """Load the control library once per process.

    The YAML files are deployment content, not request data; reloading 190 files
    for every framework on the dashboard made a 33-framework page take seconds.
    """
    return tuple(ControlLoader().load_all())


def controls_for_framework(framework_id: str, _seen: set[str] | None = None) -> list[ControlDefinition]:
    """Every control mapped to a framework, including explicit/derived mappings.

    Framework pages, coverage maths and exports all call this, so the count a
    framework advertises is always the list it renders. YAML mappings are the
    primary source; :mod:`unimonitor.grc.framework_mappings` adds frameworks that
    are listed explicitly (CPCSC, NIS2, DORA) or derived from another framework.
    """
    from unimonitor.grc.framework_mappings import derivation
    from unimonitor.grc.frameworks import framework_keys

    seen = set(_seen or ())
    if framework_id in seen:
        return []
    seen.add(framework_id)

    controls = all_controls()
    keys = framework_keys(framework_id)
    selected: dict[str, ControlDefinition] = {control.id: control for control in controls if keys & set(control.compliance_mapping)}
    for control in explicit_controls(framework_id, controls):
        selected.setdefault(control.id, control)

    rule = derivation(framework_id)
    if rule:
        pool = derived_pool(rule, controls, seen)
        for control in _filter_pool(pool, rule):
            selected.setdefault(control.id, control)

    return list(selected.values())


def explicit_controls(framework_id: str, controls: list[ControlDefinition]) -> list[ControlDefinition]:
    """Controls this framework lists explicitly, ignoring ids that no longer exist."""
    from unimonitor.grc.framework_mappings import explicit_control_ids

    by_id = {control.id: control for control in controls}
    return [by_id[control_id] for control_id in explicit_control_ids(framework_id) if control_id in by_id]


def derived_pool(rule: dict[str, Any], controls: list[ControlDefinition], seen: set[str]) -> list[ControlDefinition]:
    """The controls a derived framework starts from: its source, or all of them."""
    if rule.get("source"):
        return controls_for_framework(rule["source"], seen)
    return list(controls)


def _filter_pool(pool: list[ControlDefinition], rule: dict[str, Any]) -> list[ControlDefinition]:
    """Apply a derived framework's pillar and service filters."""
    from unimonitor.grc.pillars import pillar_for

    if rule.get("pillars"):
        wanted = set(rule["pillars"])
        pool = [
            control
            for control in pool
            if any(pillar_for(str(mapping)) in wanted for mapping in control.compliance_mapping.get("zero_trust", []) or [])
        ]
    if rule.get("services"):
        services = set(rule["services"])
        pool = [control for control in pool if control.service in services]
    return pool
