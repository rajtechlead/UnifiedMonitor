"""Framework reference shape and cumulative-level expansion."""

from __future__ import annotations

import pytest

from unimonitor.api.v1.controls import SUPPORTED_FRAMEWORKS
from unimonitor.grc.framework_reference import FRAMEWORK_REFERENCES, reference_for
from unimonitor.grc.requirements import FRAMEWORK_LEVELS, catalogue, levels_for, requirements_for


def test_every_registered_framework_has_a_reference():
    missing = [framework["id"] for framework in SUPPORTED_FRAMEWORKS if framework["id"] not in FRAMEWORK_REFERENCES]
    assert missing == []


def test_reference_counts_and_levels_are_sane():
    for framework_id, reference in FRAMEWORK_REFERENCES.items():
        assert reference.name, framework_id
        assert reference.control_count >= 0, framework_id
        assert reference.levels, framework_id
        assert len({level.id for level in reference.levels}) == len(reference.levels), framework_id
        if reference.level_scope == "cumulative":
            assert len(reference.levels) > 1, framework_id


def test_published_levels_are_exposed_with_descriptions():
    assert [level["name"] for level in levels_for("essential-eight")] == [
        "Maturity Level 1",
        "Maturity Level 2",
        "Maturity Level 3",
    ]
    assert FRAMEWORK_LEVELS["cmmc-2"][3].startswith("Level 3")
    assert levels_for("iso27001-2022")[0]["description"]


def test_cumulative_requirements_repeat_at_every_level():
    rows = requirements_for("essential-eight")
    levels = {row["level"] for row in rows}
    assert levels == {1, 2, 3}
    assert len(rows) == 3 * len({row["id"].split("@L")[0] for row in rows})
    assert len({row["id"] for row in rows}) == len(rows)


def test_separate_baselines_are_not_duplicated_across_levels():
    rows = requirements_for("fedramp-low")
    assert {row["level"] for row in rows} == {1}


def test_catalogue_reports_the_publishers_shape():
    body = catalogue("cis-controls-v8")
    assert body["reference"]["control_count"] == 18
    assert body["reference"]["requirement_count"] == 153
    assert body["reference"]["level_count"] == 3
    assert body["reference"]["level_scope"] == "cumulative"
    assert body["requirement_count"] == len(body["rows"])


def test_unknown_framework_falls_back_conservatively():
    reference = reference_for("not-a-framework")
    assert reference.modelled is True
    assert reference.control_count == 0
    assert reference.levels[0].name == "Baseline"


def test_catalogue_matches_requirement_rows():
    for framework in ("cpcsc", "nis2", "essential-eight", "cmmc-2", "swift-csp"):
        body = catalogue(framework)
        assert body["requirement_count"] == len(body["rows"])
        assert all(row["level_name"] for row in body["rows"]), framework


@pytest.mark.parametrize("framework_id", ["essential-eight", "cis-controls-v8", "cmmc-2", "tisax"])
def test_cumulative_ids_stay_unique_after_expansion(framework_id: str):
    rows = requirements_for(framework_id)
    assert len({row["id"] for row in rows}) == len(rows)
