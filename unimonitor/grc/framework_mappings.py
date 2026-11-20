"""Framework mappings that are not expressed in the control YAML.

Each framework below is either:

* **explicit** — the framework has no machine-readable crosswalk in the control
  files, so the relevant UniMonitor controls are listed here (CPCSC, NIS2, DORA);
* **derived** — the framework is a subset, alias or thematic cut of a framework
  already mapped in the control YAML (FedRAMP baselines from NIST 800-53,
  ISO 27017/27018/27701 extensions, AI frameworks from the AI pillar, and so on).

Mappings are *indicative*: they select the controls whose evidence answers a
framework requirement, and are the starting point for a compliance review — not a
certification crosswalk. `controls_for_framework()` unions these with the direct
`compliance_mapping` entries, so no control mapped in YAML is ever lost.
"""

from __future__ import annotations

from typing import Any

# CPCSC / ITSP.10.171 (Canadian version of NIST SP 800-171 Rev 3, 98 requirements
# in 17 families). The official requirement text is not redistributable, so the
# mapping is by family; the 13 Level 1 requirements are covered by these families.
CPCSC_FAMILIES: dict[str, tuple[str, ...]] = {
    "03.01 Access control": (
        "CTRL-ENT-001",
        "CTRL-ENT-002",
        "CTRL-ENT-003",
        "CTRL-ENT-004",
        "CTRL-ENT-005",
        "CTRL-ENT-010",
        "CTRL-ENT-011",
        "CTRL-ENT-012",
        "CTRL-ENT-013",
        "CTRL-AZR-012",
        "CTRL-AZR-013",
        "CTRL-AWS-012",
        "CTRL-AWS-014",
        "CTRL-GWS-002",
        "CTRL-GWS-003",
        "CTRL-INT-018",
    ),
    "03.02 Awareness and training": ("CTRL-DEF-011", "CTRL-DEF-012", "CTRL-COP-008"),
    "03.03 Audit and accountability": (
        "CTRL-EXO-009",
        "CTRL-PUR-004",
        "CTRL-AZR-008",
        "CTRL-AZR-009",
        "CTRL-AWS-005",
        "CTRL-AWS-007",
        "CTRL-GCP-004",
        "CTRL-COP-003",
    ),
    "03.04 Configuration management": (
        "CTRL-INT-001",
        "CTRL-INT-002",
        "CTRL-INT-011",
        "CTRL-INT-012",
        "CTRL-INT-013",
        "CTRL-INT-014",
        "CTRL-INT-016",
        "CTRL-AWS-007",
        "CTRL-GCP-007",
        "CTRL-DEF-002",
        "CTRL-DEF-006",
        "CTRL-SPO-005",
    ),
    "03.05 Identification and authentication": (
        "CTRL-ENT-001",
        "CTRL-ENT-002",
        "CTRL-ENT-005",
        "CTRL-ENT-020",
        "CTRL-ENT-021",
        "CTRL-AWS-001",
        "CTRL-AWS-002",
        "CTRL-AWS-003",
        "CTRL-GWS-001",
        "CTRL-INT-002",
        "CTRL-INT-007",
        "CTRL-INT-017",
        "CTRL-AZR-014",
    ),
    "03.06 Incident response": (
        "CTRL-DEF-004",
        "CTRL-DEF-016",
        "CTRL-DEF-018",
        "CTRL-DEF-022",
        "CTRL-DEF-023",
        "CTRL-AZR-015",
        "CTRL-COP-007",
        "CTRL-AWS-006",
        "CTRL-AWS-008",
        "CTRL-GCP-012",
    ),
    "03.07 Maintenance": ("CTRL-AWS-013", "CTRL-INT-010", "CTRL-DEF-008", "CTRL-AZR-016", "CTRL-AZR-023"),
    "03.08 Media protection": (
        "CTRL-AWS-004",
        "CTRL-AWS-011",
        "CTRL-AZR-003",
        "CTRL-AZR-005",
        "CTRL-AZR-006",
        "CTRL-AZR-007",
        "CTRL-GCP-005",
        "CTRL-GCP-006",
        "CTRL-INT-001",
        "CTRL-INT-005",
        "CTRL-SPO-004",
        "CTRL-PUR-002",
        "CTRL-PUR-005",
    ),
    "03.09 Personnel security": (
        "CTRL-ENT-010",
        "CTRL-ENT-012",
        "CTRL-GWS-002",
        "CTRL-PUR-006",
        "CTRL-PUR-008",
        "CTRL-PUR-010",
    ),
    "03.10 Physical protection": ("CTRL-AZR-010", "CTRL-AWS-009", "CTRL-GCP-003", "CTRL-INT-004", "CTRL-INT-006"),
    "03.11 Risk assessment": (
        "CTRL-DEF-008",
        "CTRL-AZR-023",
        "CTRL-AWS-014",
        "CTRL-GCP-012",
        "CTRL-INT-003",
        "CTRL-INT-009",
        "CTRL-ENT-020",
        "CTRL-ENT-021",
    ),
    "03.12 Security assessment and monitoring": (
        "CTRL-AWS-007",
        "CTRL-AWS-008",
        "CTRL-AZR-002",
        "CTRL-AZR-024",
        "CTRL-GCP-007",
        "CTRL-GCP-012",
        "CTRL-DEF-003",
        "CTRL-INT-015",
        "CTRL-INT-016",
    ),
    "03.13 System and communications protection": (
        "CTRL-ENT-002",
        "CTRL-ENT-003",
        "CTRL-AWS-009",
        "CTRL-AWS-010",
        "CTRL-GCP-003",
        "CTRL-GCP-008",
        "CTRL-GCP-009",
        "CTRL-GCP-010",
        "CTRL-GCP-011",
        "CTRL-AZR-004",
        "CTRL-AZR-010",
        "CTRL-AZR-011",
        "CTRL-AZR-019",
        "CTRL-AZR-020",
        "CTRL-AZR-021",
        "CTRL-AZR-022",
        "CTRL-SPO-001",
        "CTRL-SPO-003",
        "CTRL-SPO-004",
        "CTRL-EXO-001",
        "CTRL-EXO-002",
        "CTRL-EXO-008",
        "CTRL-TEA-001",
        "CTRL-TEA-002",
        "CTRL-TEA-003",
        "CTRL-TEA-004",
        "CTRL-TEA-005",
    ),
    "03.14 System and information integrity": (
        "CTRL-DEF-001",
        "CTRL-DEF-002",
        "CTRL-DEF-003",
        "CTRL-DEF-006",
        "CTRL-DEF-007",
        "CTRL-DEF-009",
        "CTRL-DEF-010",
        "CTRL-DEF-013",
        "CTRL-DEF-014",
        "CTRL-DEF-016",
        "CTRL-INT-010",
        "CTRL-INT-011",
        "CTRL-INT-012",
        "CTRL-INT-016",
        "CTRL-AWS-005",
        "CTRL-AWS-006",
        "CTRL-AWS-013",
        "CTRL-GCP-012",
        "CTRL-COP-005",
        "CTRL-SPO-005",
    ),
    "03.15 Planning": ("CTRL-AZR-024", "CTRL-COP-008", "CTRL-DEF-008", "CTRL-PUR-004"),
    "03.16 System and services acquisition": (
        "CTRL-AWS-014",
        "CTRL-AZR-023",
        "CTRL-COP-004",
        "CTRL-COP-009",
        "CTRL-COP-011",
        "CTRL-COP-016",
        "CTRL-DEF-029",
    ),
    "03.17 Supply chain risk management": (
        "CTRL-COP-009",
        "CTRL-COP-011",
        "CTRL-COP-016",
        "CTRL-DEF-028",
        "CTRL-DEF-029",
        "CTRL-AZR-024",
        "CTRL-AWS-014",
    ),
}

# NIS2 (EU 2022/2555) Article 21 risk-management measures plus the reporting duty.
NIS2_MEASURES: dict[str, tuple[str, ...]] = {
    "Art.21(2)(a) risk analysis and information system security policies": ("CTRL-AZR-024", "CTRL-INT-003", "CTRL-AWS-007"),
    "Art.21(2)(b) incident handling": ("CTRL-DEF-004", "CTRL-DEF-016", "CTRL-AZR-015", "CTRL-COP-007"),
    "Art.21(2)(c) business continuity, backup and crisis management": ("CTRL-AZR-003", "CTRL-AZR-005", "CTRL-PUR-017"),
    "Art.21(2)(d) supply chain security": ("CTRL-AWS-014", "CTRL-DEF-028", "CTRL-DEF-029", "CTRL-COP-009", "CTRL-COP-011"),
    "Art.21(2)(e) acquisition, development and maintenance security": ("CTRL-INT-003", "CTRL-INT-011", "CTRL-COP-016"),
    "Art.21(2)(f) effectiveness assessment": ("CTRL-AZR-002", "CTRL-AZR-023", "CTRL-DEF-008"),
    "Art.21(2)(g) cyber hygiene and training": ("CTRL-DEF-011", "CTRL-DEF-012", "CTRL-COP-008"),
    "Art.21(2)(h) cryptography and encryption": (
        "CTRL-AWS-004",
        "CTRL-AWS-011",
        "CTRL-GCP-005",
        "CTRL-GCP-006",
        "CTRL-AZR-003",
        "CTRL-AZR-005",
        "CTRL-AZR-006",
        "CTRL-AZR-007",
        "CTRL-INT-001",
        "CTRL-INT-005",
    ),
    "Art.21(2)(i) access control and identity management": (
        "CTRL-ENT-001",
        "CTRL-ENT-002",
        "CTRL-ENT-003",
        "CTRL-ENT-010",
        "CTRL-ENT-011",
        "CTRL-ENT-013",
        "CTRL-AWS-001",
        "CTRL-GWS-001",
        "CTRL-GWS-002",
        "CTRL-GWS-003",
    ),
    "Art.21(2)(j) multi-factor authentication": ("CTRL-ENT-001", "CTRL-ENT-005", "CTRL-AWS-001", "CTRL-GWS-001", "CTRL-AZR-014"),
    "Art.23 reporting obligations": ("CTRL-AZR-015", "CTRL-DEF-018", "CTRL-COP-007"),
}

# DORA (EU 2022/2554) — ICT risk, incident reporting, resilience testing,
# third-party risk and information sharing.
DORA_PILLARS: dict[str, tuple[str, ...]] = {
    "ICT risk management": ("CTRL-AZR-024", "CTRL-AWS-007", "CTRL-INT-003", "CTRL-AZR-002"),
    "ICT incident reporting": ("CTRL-DEF-004", "CTRL-DEF-016", "CTRL-AZR-015", "CTRL-COP-007"),
    "Digital operational resilience testing": ("CTRL-DEF-011", "CTRL-AZR-023", "CTRL-DEF-008"),
    "ICT third-party risk": ("CTRL-AWS-014", "CTRL-DEF-028", "CTRL-DEF-029", "CTRL-COP-009", "CTRL-COP-011", "CTRL-COP-016"),
    "Information sharing and monitoring": ("CTRL-AWS-005", "CTRL-GCP-004", "CTRL-AZR-008", "CTRL-AZR-009", "CTRL-AZR-025"),
}

EXPLICIT: dict[str, dict[str, Any]] = {
    "cpcsc": {
        "requirements": CPCSC_FAMILIES,
        "note": "Family-level mapping of the 98 ITSP.10.171 requirements; the 13 Level 1 requirements fall inside these families.",
    },
    "nis2": {"requirements": NIS2_MEASURES, "note": "Article 21 measures and Article 23 reporting mapped to controls that carry the evidence."},
    "dora": {"requirements": DORA_PILLARS, "note": "The five DORA pillars mapped to controls that carry the evidence."},
}

# Derived frameworks reuse the controls of a source framework, optionally filtered
# to the Zero Trust pillars or services that the framework is about.
DERIVED: dict[str, dict[str, Any]] = {
    "nist-800-171-r3": {"source": "cpcsc", "note": "NIST SP 800-171 Rev 3 (97 requirements); CPCSC adds 03.14.09."},
    "fedramp-low": {
        "source": "nist-800-53-r5",
        "note": "Derived from the NIST 800-53 mapping; the FedRAMP Low baseline is a subset of those controls.",
    },
    "fedramp-moderate": {
        "source": "nist-800-53-r5",
        "note": "Derived from the NIST 800-53 mapping; the FedRAMP Moderate baseline is a subset of those controls.",
    },
    "fedramp-high": {
        "source": "nist-800-53-r5",
        "note": "Derived from the NIST 800-53 mapping; the FedRAMP High baseline is a subset of those controls.",
    },
    "csa-ccm-v4": {"source": "iso27001-2022", "note": "Derived from ISO 27001 until a CCM v4 crosswalk is imported."},
    "cisa-scuba-m365": {"source": "cis-m365", "note": "Derived from the CIS Microsoft 365 benchmark controls."},
    "cisa-scuba-workspace": {"services": ("google_workspace",), "note": "Mapped to the Google Workspace controls."},
    "iso27017": {"source": "iso27001-2022", "pillars": ("network", "data", "infrastructure"), "note": "Cloud security extension of ISO 27001."},
    "iso27018": {"source": "iso27001-2022", "pillars": ("data",), "note": "Cloud privacy extension of ISO 27001."},
    "iso27701": {"source": "gdpr", "note": "Privacy extension; derived from the GDPR-mapped controls."},
    "nist-ai-rmf": {"services": ("copilot_m365", "copilot_studio"), "note": "AI governance controls (Copilot and agent controls)."},
    "eu-ai-act": {"services": ("copilot_m365", "copilot_studio"), "note": "AI governance controls (Copilot and agent controls)."},
    "essential-eight": {"source": "cis-controls-v8", "note": "Derived from the CIS Controls v8 mapping until an ASD mapping is imported."},
    "cyber-essentials": {"source": "cis-controls-v8", "note": "Derived from the CIS Controls v8 mapping until a UK NCSC mapping is imported."},
    "ccpa-cpra": {"source": "gdpr", "note": "Derived from the GDPR-mapped privacy controls."},
    "cjis": {"source": "nist-800-53-r5", "note": "Derived from the NIST 800-53 mapping."},
    "swift-csp": {"source": "nist-800-53-r5", "note": "Derived from the NIST 800-53 mapping."},
    "tisax": {"source": "iso27001-2022", "note": "Derived from the ISO 27001 mapping."},
    "pci-3ds": {"source": "pci-dss-4", "note": "Derived from the PCI DSS mapping."},
}


def explicit_control_ids(framework_id: str) -> list[str]:
    """Controls selected for a framework with an explicit mapping."""
    entry = EXPLICIT.get(framework_id)
    if not entry:
        return []
    seen: dict[str, None] = {}
    for controls in entry["requirements"].values():
        for control_id in controls:
            seen.setdefault(control_id, None)
    return list(seen)


def derivation(framework_id: str) -> dict[str, Any] | None:
    return DERIVED.get(framework_id)
