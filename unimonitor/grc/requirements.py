"""Requirement and level catalogue for every framework.

CPCSC was the only framework with a requirement-level catalogue, so the auditor
portal said "no requirement catalogue" for the rest and a FedRAMP or Essential
Eight reviewer was pushed back to a flat control list. This module gives every
framework a requirement model without inventing official text:

* an **official** catalogue (CPCSC) keeps its published identifiers and levels;
* an **explicit mapping** (NIS2, DORA) becomes one requirement per named measure;
* any other framework derives one requirement per reference its controls already
  carry in ``compliance_mapping`` — the same evidence, grouped the way the auditor
  asked for.

``levels`` describes the levels a framework publishes (CPCSC Level 1/2, FedRAMP
Low/Moderate/High, Essential Eight ML1–3, CMMC 1–3). A framework without published
levels reports a single level, so a filter never hides requirements.
"""

from __future__ import annotations

import re
from typing import Any

from unimonitor.grc.framework_reference import FRAMEWORK_REFERENCES, reference_for

# Derived from the reference catalogue so every framework publishes the levels its
# owner actually defines (IG1-3, ML1-3, AL1-3, FedRAMP baselines, ...), not a
# hand-maintained subset. Kept as a name for callers that imported it.
FRAMEWORK_LEVELS: dict[str, dict[int, str]] = {
    framework_id: {level.id: level.name for level in reference.levels} for framework_id, reference in FRAMEWORK_REFERENCES.items()
}

_SLUG = re.compile(r"[^a-z0-9]+")


def levels_for(framework_id: str) -> list[dict[str, Any]]:
    """The published levels of a framework, with what each level means."""
    reference = reference_for(framework_id)
    return [{"level": level.id, "name": level.name, "description": level.description} for level in sorted(reference.levels, key=lambda item: item.id)]


def _expand_levels(rows: list[dict[str, Any]], framework_id: str) -> list[dict[str, Any]]:
    """Repeat cumulative requirements at every level, so a level filter is complete.

    Only frameworks whose publisher says each requirement applies at every level
    (IG1 -> IG3, ML1 -> ML3, AL1 -> AL3) are expanded. Separate baselines and
    applicability classes keep one row, because duplicating them would claim a
    requirement applies where it does not.
    """
    reference = reference_for(framework_id)
    if reference.level_scope != "cumulative" or len(reference.levels) < 2:
        return rows
    expanded: list[dict[str, Any]] = []
    for row in rows:
        for level in reference.levels:
            expanded.append(
                {
                    **row,
                    "id": row["id"] if level.id == 1 else f"{row['id']}@L{level.id}",
                    "level": level.id,
                    "level_name": level.name,
                }
            )
    return expanded


def _catalogue_source(framework_id: str) -> str:
    from unimonitor.grc.framework_mappings import EXPLICIT

    if framework_id == "cpcsc":
        return "official"
    if framework_id in EXPLICIT:
        return "mapping"
    return "derived"


def _explicit_rows(framework_id: str) -> list[dict[str, Any]]:
    from unimonitor.grc.framework_mappings import EXPLICIT

    requirements = EXPLICIT[framework_id]["requirements"]
    rows: list[dict[str, Any]] = []
    for index, (title, controls) in enumerate(requirements.items(), start=1):
        slug = _SLUG.sub("-", title.lower()).strip("-")[:48] or f"{index:02d}"
        rows.append(
            {
                "id": f"{framework_id}-{slug}",
                "title": title,
                "family": title.split()[0] if title else "",
                "family_code": str(index),
                "level": 1,
                "level_name": levels_for(framework_id)[0]["name"],
                "controls": list(controls),
                "source": "mapping",
            }
        )
    return rows


def _normalise_key(key: str) -> str:
    return str(key).lower().replace("-", "_")


def _derived_row(requirement_id: str, control: Any, key: str, framework_id: str) -> dict[str, Any]:
    return {
        "id": requirement_id,
        "title": control.title,
        "family": str(key).replace("_", " ").title(),
        "family_code": str(key),
        "level": 1,
        "level_name": levels_for(framework_id)[0]["name"],
        "controls": [],
        "source": "derived",
    }


def _add_references(
    control: Any,
    framework_keys: set[str],
    framework_id: str,
    grouped: dict[str, dict[str, Any]],
) -> None:
    for key, references in (control.compliance_mapping or {}).items():
        if _normalise_key(key) not in framework_keys:
            continue
        items = references if isinstance(references, (list, tuple)) else [references]
        for reference in items:
            requirement_id = str(reference)
            if requirement_id not in grouped:
                grouped[requirement_id] = _derived_row(requirement_id, control, key, framework_id)
            if control.id not in grouped[requirement_id]["controls"]:
                grouped[requirement_id]["controls"].append(control.id)


def _derived_rows(framework_id: str) -> list[dict[str, Any]]:
    from unimonitor.grc.control_loader import controls_for_framework
    from unimonitor.grc.frameworks import framework_keys

    keys = {_normalise_key(candidate) for candidate in framework_keys(framework_id)}
    grouped: dict[str, dict[str, Any]] = {}
    for control in controls_for_framework(framework_id):
        _add_references(control, keys, framework_id, grouped)

    return [grouped[key] for key in sorted(grouped)]


def requirements_for(framework_id: str) -> list[dict[str, Any]]:
    """Every requirement of a framework with the controls that evidence it."""
    from unimonitor.grc.framework_mappings import DERIVED, cpcsc_requirements

    if framework_id == "cpcsc":
        names = {level["level"]: level["name"] for level in levels_for("cpcsc")}
        rows = [{**row, "level_name": names.get(row["level"], ""), "source": "official"} for row in cpcsc_requirements()]
        return _expand_levels(rows, framework_id)

    from unimonitor.grc.framework_mappings import EXPLICIT

    if framework_id in EXPLICIT:
        return _expand_levels(_explicit_rows(framework_id), framework_id)

    rows = _derived_rows(framework_id)
    if rows:
        return _expand_levels(rows, framework_id)

    # A framework derived from another one has no references of its own: reuse the
    # source catalogue, relabelled with this framework's level.
    derivation = DERIVED.get(framework_id) or {}
    source = derivation.get("source")
    if source:
        level_name = levels_for(framework_id)[0]["name"]
        # The source catalogue may itself be cumulative, so collapse its level rows
        # back to one requirement before relabelling and expanding for this framework.
        base_rows: dict[str, dict[str, Any]] = {}
        for row in requirements_for(source):
            base_id = str(row["id"]).split("@L", 1)[0]
            if base_id not in base_rows:
                base_rows[base_id] = {**row, "id": base_id, "level": 1, "level_name": level_name, "source": "derived"}
        return _expand_levels(list(base_rows.values()), framework_id)

    # A service-selected framework (for example CISA SCuBA for Workspace) has no
    # published requirement identifiers here: one control is one requirement, and
    # the row says so rather than inventing a reference.
    return _control_rows(framework_id)


def _control_rows(framework_id: str) -> list[dict[str, Any]]:
    """One requirement per mapped control, for frameworks without references."""
    from unimonitor.grc.control_loader import controls_for_framework

    level_name = levels_for(framework_id)[0]["name"]
    rows = [
        {
            "id": control.id,
            "title": control.title,
            "family": control.category,
            "family_code": control.category,
            "level": 1,
            "level_name": level_name,
            "controls": [control.id],
            "source": "control",
        }
        for control in controls_for_framework(framework_id)
    ]
    return _expand_levels(rows, framework_id)


def catalogue(framework_id: str) -> dict[str, Any]:
    """Requirement rows plus the metadata the auditor portal displays.

    ``reference`` is the publisher's own shape (control and requirement totals, level
    names, source link); ``modelled`` marks a count this platform derived because the
    publisher does not state a total.
    """
    reference = reference_for(framework_id)
    rows = requirements_for(framework_id)
    return {
        "framework_id": framework_id,
        "catalogue": _catalogue_source(framework_id),
        "levels": levels_for(framework_id),
        "requirement_count": len(rows),
        "rows": rows,
        "reference": {
            "name": reference.name,
            "version": reference.version,
            "publisher": reference.publisher,
            "control_count": reference.control_count,
            "requirement_count": reference.requirement_count,
            "level_count": len(reference.levels),
            "level_scope": reference.level_scope,
            "source_url": reference.source_url,
            "notes": reference.notes,
            "modelled": reference.modelled,
            "extra": reference.extra,
        },
    }


__all__ = ["FRAMEWORK_LEVELS", "catalogue", "levels_for", "requirements_for"]
