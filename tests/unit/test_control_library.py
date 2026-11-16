"""Library-wide invariants for the YAML control set under controls/."""

import pytest

from unimonitor.grc.control_loader import ControlLoader
from unimonitor.grc.frameworks import FRAMEWORKS

VALID_STATES = {"implemented", "partially_implemented", "not_implemented", "not_applicable"}
VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"}

# Requirement areas that must have controls, by service name.
REQUIRED_SERVICES = {
    "intune",
    "defender",
    "defender_office",
    "defender_identity",
    "defender_cloud_apps",
    "purview",
    "purview_insider_risk",
    "purview_ediscovery",
    "copilot_m365",
    "copilot_studio",
}


@pytest.fixture(scope="module")
def controls():
    return ControlLoader().load_all()


def test_library_loads(controls):
    assert len(controls) >= 150


def test_control_ids_are_unique(controls):
    ids = [c.id for c in controls]
    duplicates = {i for i in ids if ids.count(i) > 1}
    assert not duplicates, f"duplicate control ids: {sorted(duplicates)}"


def test_severities_are_valid(controls):
    invalid = {c.id: c.severity for c in controls if c.severity not in VALID_SEVERITIES}
    assert not invalid, f"invalid severities: {invalid}"


def test_framework_keys_are_registered(controls):
    unknown = {c.id: sorted(set(c.compliance_mapping) - set(FRAMEWORKS)) for c in controls if set(c.compliance_mapping) - set(FRAMEWORKS)}
    assert not unknown, f"unregistered framework keys: {unknown}"


def test_required_areas_have_controls(controls):
    services = {c.service for c in controls}
    assert REQUIRED_SERVICES <= services, f"missing areas: {sorted(REQUIRED_SERVICES - services)}"


@pytest.mark.parametrize("empty", [{}])
def test_every_control_evaluates(controls, empty):
    """No control may crash the evaluator; it must return a canonical state."""
    broken = {}
    for ctrl in controls:
        result = ctrl.run_evaluate(empty)
        if result not in VALID_STATES:
            broken[ctrl.id] = result
    assert not broken, f"controls returned a non-canonical state on empty data: {broken}"
