"""Zero Trust pillars.

The Microsoft Zero Trust Assessment scores a tenant on seven pillars. UniMonitor's
controls already carry a ``zero_trust`` compliance mapping (for example
``identity.verify_explicitly``), so the pillar view is a grouping of existing data
rather than a second control library. Pillars with no mapped control are reported
as uncovered instead of silently passing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pillar:
    id: str
    name: str
    description: str


PILLARS: tuple[Pillar, ...] = (
    Pillar("identity", "Identity", "Verify explicitly, least privilege, and assume breach for users and workloads."),
    Pillar("devices", "Devices", "Device health, compliance and configuration management."),
    Pillar("network", "Network", "Segmentation, traffic inspection and network-level verification."),
    Pillar("data", "Data", "Sensitivity labelling, DLP and data-centric protection."),
    Pillar("infrastructure", "Infrastructure", "Cloud and platform configuration, patching and vulnerability management."),
    Pillar("secops", "SecOps", "Detection, response, and security operations visibility."),
    Pillar("ai", "AI", "Governance and protection of AI services and Copilot."),
)

PILLAR_IDS = frozenset(p.id for p in PILLARS)

# Control mappings use both Zero Trust vocabulary and service-prefixed keys; these
# aliases fold the legacy spellings into a pillar.
_ALIASES: dict[str, str] = {
    "endpoints": "devices",
    "apps": "data",
    "monitoring": "secops",
    "operations": "secops",
}


def pillar_for(mapping_value: str) -> str | None:
    """Return the pillar id for a ``zero_trust`` mapping value, or None."""
    prefix = mapping_value.split(".", 1)[0].strip().lower()
    prefix = _ALIASES.get(prefix, prefix)
    return prefix if prefix in PILLAR_IDS else None
