"""The framework ids the UI offers and the catalogue must agree.

A framework id in `SUPPORTED_FRAMEWORKS` that the catalogue cannot resolve renders an
empty page; a catalogue framework that is not listed is unreachable. Both were possible
because nothing compared the two.
"""

from __future__ import annotations

import pytest

from unimonitor.api.v1.controls import SUPPORTED_FRAMEWORKS
from unimonitor.grc.control_loader import controls_for_framework

IDS = [framework["id"] for framework in SUPPORTED_FRAMEWORKS]


class TestFrameworkRegistry:
    def test_identifiers_are_unique(self):
        assert len(IDS) == len(set(IDS))

    def test_every_framework_has_a_name_and_an_id(self):
        for framework in SUPPORTED_FRAMEWORKS:
            assert framework["id"]
            assert framework.get("name")

    @pytest.mark.parametrize("framework_id", IDS)
    def test_every_listed_framework_resolves_controls(self, framework_id):
        controls = controls_for_framework(framework_id)
        assert controls, f"{framework_id} is offered but has no controls"

    @pytest.mark.parametrize("framework_id", IDS)
    def test_controls_declare_the_framework_they_were_loaded_for(self, framework_id):
        for control in controls_for_framework(framework_id):
            declared = getattr(control, "frameworks", None)
            if declared:
                assert framework_id in declared, f"{control.id} does not list {framework_id}"

    def test_the_ids_are_url_safe_slugs(self):
        for framework_id in IDS:
            assert framework_id == framework_id.lower()
            assert framework_id.replace("_", "").replace("-", "").isalnum()
