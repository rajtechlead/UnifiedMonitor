"""
GRC Framework registry — all supported compliance frameworks with metadata,
control counts, and crosswalk mappings.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FrameworkMeta:
    id: str
    name: str
    version: str
    description: str
    category: str  # "security" | "privacy" | "ai" | "industry"
    region: str  # "global" | "us" | "eu" | ...
    control_prefix: str
    url: str
    total_controls: int = 0
    tags: list[str] = field(default_factory=list)
    # Hyphenated id used by the API/UI; FRAMEWORKS is keyed by the underscore form.
    slug: str = ""
    # How the controls were selected (explicit / derived), shown in the UI.
    mapping_note: str = ""


FRAMEWORKS: dict[str, FrameworkMeta] = {
    "iso27001_2022": FrameworkMeta(
        id="iso27001_2022",
        name="ISO 27001:2022",
        version="2022",
        description="International standard for information security management systems (ISMS).",
        category="security",
        region="global",
        control_prefix="ISO-27001",
        url="https://www.iso.org/standard/82875.html",
        total_controls=93,
        tags=["isms", "information-security", "international"],
        slug="iso27001-2022",
    ),
    "iso42001": FrameworkMeta(
        id="iso42001",
        name="ISO 42001",
        version="2023",
        description="International standard for Artificial Intelligence Management Systems (AIMS).",
        category="ai",
        region="global",
        control_prefix="ISO-42001",
        url="https://www.iso.org/standard/81230.html",
        total_controls=38,
        tags=["ai-governance", "aims", "artificial-intelligence"],
        slug="iso42001",
    ),
    "nist_csf_2": FrameworkMeta(
        id="nist_csf_2",
        name="NIST CSF 2.0",
        version="2.0",
        description="NIST Cybersecurity Framework version 2.0 — Govern, Identify, Protect, Detect, Respond, Recover.",
        category="security",
        region="us",
        control_prefix="CSF2",
        url="https://www.nist.gov/cyberframework",
        total_controls=106,
        tags=["nist", "csf", "cybersecurity-framework"],
        slug="nist-csf-2",
    ),
    "nist_800_53_r5": FrameworkMeta(
        id="nist_800_53_r5",
        name="NIST SP 800-53 Rev 5",
        version="Rev 5",
        description="Security and Privacy Controls for Information Systems and Organizations.",
        category="security",
        region="us",
        control_prefix="NIST-800-53",
        url="https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final",
        total_controls=1007,
        tags=["nist", "federal", "privacy"],
        slug="nist-800-53-r5",
    ),
    "cis_controls_v8": FrameworkMeta(
        id="cis_controls_v8",
        name="CIS Controls v8",
        version="v8",
        description="CIS Critical Security Controls — prioritized set of actions to protect organisations.",
        category="security",
        region="global",
        control_prefix="CIS",
        url="https://www.cisecurity.org/controls/v8",
        total_controls=153,
        tags=["cis", "critical-controls", "implementation-groups"],
        slug="cis-controls-v8",
    ),
    "cis_m365_benchmark": FrameworkMeta(
        id="cis_m365_benchmark",
        name="CIS Microsoft 365 Benchmark",
        version="3.0.0",
        description="CIS Benchmark for hardening Microsoft 365 tenants.",
        category="security",
        region="global",
        control_prefix="CIS-M365",
        url="https://www.cisecurity.org/benchmark/microsoft_365",
        total_controls=84,
        tags=["cis", "microsoft-365", "benchmark", "cloud"],
        slug="cis-m365",
    ),
    "zero_trust": FrameworkMeta(
        id="zero_trust",
        name="Microsoft Zero Trust",
        version="2024",
        description="Microsoft Zero Trust framework — Identity, Devices, Network, Data, Apps, Infrastructure.",
        category="security",
        region="global",
        control_prefix="ZT",
        url="https://www.microsoft.com/en-us/security/business/zero-trust",
        total_controls=140,
        tags=["zero-trust", "microsoft", "identity", "devices"],
        slug="microsoft-zero-trust",
    ),
    "soc2": FrameworkMeta(
        id="soc2",
        name="SOC 2",
        version="2017",
        description="AICPA SOC 2 — Trust Service Criteria: Security, Availability, Confidentiality, Processing Integrity, Privacy.",
        category="security",
        region="us",
        control_prefix="SOC2",
        url="https://www.aicpa.org/soc4so",
        total_controls=61,
        tags=["aicpa", "soc", "trust-services", "audit"],
        slug="soc2",
    ),
    "pci_dss_v4": FrameworkMeta(
        id="pci_dss_v4",
        name="PCI-DSS v4.0",
        version="4.0",
        description="Payment Card Industry Data Security Standard version 4.0.",
        category="industry",
        region="global",
        control_prefix="PCI",
        url="https://www.pcisecuritystandards.org",
        total_controls=249,
        tags=["pci", "payment-card", "financial"],
        slug="pci-dss-4",
    ),
    "hipaa": FrameworkMeta(
        id="hipaa",
        name="HIPAA",
        version="2013",
        description="Health Insurance Portability and Accountability Act — Security and Privacy Rules.",
        category="industry",
        region="us",
        control_prefix="HIPAA",
        url="https://www.hhs.gov/hipaa",
        total_controls=54,
        tags=["hipaa", "healthcare", "phi", "us"],
        slug="hipaa",
    ),
    "gdpr": FrameworkMeta(
        id="gdpr",
        name="GDPR",
        version="2018",
        description="EU General Data Protection Regulation — data protection and privacy law.",
        category="privacy",
        region="eu",
        control_prefix="GDPR",
        url="https://gdpr-info.eu",
        total_controls=99,
        tags=["gdpr", "eu", "privacy", "data-protection"],
        slug="gdpr",
    ),
    "cpcsc": FrameworkMeta(
        id="cpcsc",
        name="CPCSC",
        version="2024",
        description="Canada's Canadian Program for Cyber Security Certification.",
        category="security",
        region="ca",
        control_prefix="CPCSC",
        url="https://www.canada.ca/en/department-national-defence/programs/cyber-security-certification.html",
        total_controls=98,
        tags=["canada", "defense", "certification"],
        slug="cpcsc",
        mapping_note="Family-level mapping of the 98 ITSP.10.171 requirements; the 13 Level 1 requirements fall inside these families.",
    ),
    "cmmc_2": FrameworkMeta(
        id="cmmc_2",
        name="CMMC 2.0",
        version="2.0",
        description="Cybersecurity Maturity Model Certification — US DoD supply chain security.",
        category="industry",
        region="us",
        control_prefix="CMMC",
        url="https://www.acq.osd.mil/cmmc",
        total_controls=110,
        tags=["cmmc", "dod", "defense-industrial-base", "us"],
        slug="cmmc-2",
    ),
}

# Additional frameworks approved in the 2026-11 roadmap. Their controls come from
# unimonitor.grc.framework_mappings (explicit or derived), not from control YAML.
_ADDITIONAL_FRAMEWORKS: list[tuple[str, str, str, str, str, str, str, int, list[str]]] = [
    (
        "nist_800_171_r3",
        "nist-800-171-r3",
        "NIST SP 800-171 Rev 3",
        "Rev 3",
        "Protecting Controlled Unclassified Information in Nonfederal Systems and Organizations.",
        "security",
        "us",
        97,
        ["nist", "cui", "federal", "dod"],
    ),
    (
        "fedramp_low",
        "fedramp-low",
        "FedRAMP Low Baseline",
        "Rev 5",
        "FedRAMP authorization baseline for low-impact federal cloud systems.",
        "security",
        "us",
        156,
        ["fedramp", "cloud", "federal", "ato"],
    ),
    (
        "fedramp_moderate",
        "fedramp-moderate",
        "FedRAMP Moderate Baseline",
        "Rev 5",
        "FedRAMP authorization baseline for moderate-impact federal cloud systems.",
        "security",
        "us",
        323,
        ["fedramp", "cloud", "federal", "ato"],
    ),
    (
        "fedramp_high",
        "fedramp-high",
        "FedRAMP High Baseline",
        "Rev 5",
        "FedRAMP authorization baseline for high-impact federal cloud systems.",
        "security",
        "us",
        410,
        ["fedramp", "cloud", "federal", "ato"],
    ),
    (
        "nis2",
        "nis2",
        "NIS2 Directive",
        "2022/2555",
        "EU directive on measures for a high common level of cybersecurity across the Union.",
        "security",
        "eu",
        12,
        ["eu", "nis2", "critical-infrastructure", "reporting"],
    ),
    (
        "dora",
        "dora",
        "DORA",
        "2022/2554",
        "EU Digital Operational Resilience Act for the financial sector.",
        "industry",
        "eu",
        5,
        ["eu", "financial", "resilience", "ict-risk"],
    ),
    (
        "csa_ccm_v4",
        "csa-ccm-v4",
        "CSA CCM v4",
        "v4",
        "Cloud Security Alliance Cloud Controls Matrix.",
        "security",
        "global",
        197,
        ["cloud", "csa", "ccm", "supplier"],
    ),
    (
        "cisa_scuba_m365",
        "cisa-scuba-m365",
        "CISA SCuBA — Microsoft 365",
        "v1",
        "CISA Secure Cloud Business Applications baseline for Microsoft 365.",
        "security",
        "us",
        0,
        ["cisa", "scuba", "microsoft-365", "cloud"],
    ),
    (
        "cisa_scuba_workspace",
        "cisa-scuba-workspace",
        "CISA SCuBA — Google Workspace",
        "v1",
        "CISA Secure Cloud Business Applications baseline for Google Workspace.",
        "security",
        "us",
        0,
        ["cisa", "scuba", "google-workspace", "cloud"],
    ),
    (
        "iso27017",
        "iso27017",
        "ISO/IEC 27017",
        "2015",
        "Code of practice for information security controls for cloud services.",
        "security",
        "global",
        37,
        ["iso", "cloud", "extension"],
    ),
    (
        "iso27018",
        "iso27018",
        "ISO/IEC 27018",
        "2019",
        "Code of practice for protecting personal data in public clouds.",
        "privacy",
        "global",
        25,
        ["iso", "cloud", "privacy", "pii"],
    ),
    (
        "iso27701",
        "iso27701",
        "ISO/IEC 27701",
        "2019",
        "Privacy information management extension to ISO 27001 and 27002.",
        "privacy",
        "global",
        49,
        ["iso", "privacy", "pims", "gdpr"],
    ),
    (
        "nist_ai_rmf",
        "nist-ai-rmf",
        "NIST AI RMF 1.0",
        "1.0",
        "AI Risk Management Framework — Govern, Map, Measure, Manage.",
        "ai",
        "us",
        72,
        ["nist", "ai", "risk", "governance"],
    ),
    (
        "eu_ai_act",
        "eu-ai-act",
        "EU AI Act",
        "2024/1689",
        "EU regulation laying down harmonised rules on artificial intelligence.",
        "ai",
        "eu",
        0,
        ["eu", "ai", "regulation", "governance"],
    ),
    (
        "essential_eight",
        "essential-eight",
        "ACSC Essential Eight",
        "2023",
        "Australian Signals Directorate baseline mitigation strategies.",
        "security",
        "au",
        8,
        ["australia", "asd", "baseline", "mitigation"],
    ),
    (
        "cyber_essentials",
        "cyber-essentials",
        "UK Cyber Essentials",
        "2024",
        "UK NCSC baseline for cyber hygiene.",
        "security",
        "uk",
        5,
        ["uk", "ncsc", "baseline", "hygiene"],
    ),
    (
        "ccpa_cpra",
        "ccpa-cpra",
        "CCPA / CPRA",
        "2023",
        "California Consumer Privacy Act as amended by the CPRA.",
        "privacy",
        "us",
        0,
        ["california", "privacy", "consumer", "us"],
    ),
    (
        "cjis",
        "cjis",
        "FBI CJIS Security Policy",
        "v5.9.5",
        "Criminal Justice Information Services security requirements.",
        "industry",
        "us",
        0,
        ["fbi", "criminal-justice", "us", "law-enforcement"],
    ),
    (
        "swift_csp",
        "swift-csp",
        "SWIFT Customer Security Programme",
        "CSCF v2024",
        "SWIFT Customer Security Controls Framework.",
        "industry",
        "global",
        31,
        ["swift", "financial", "payments", "cscf"],
    ),
    (
        "tisax",
        "tisax",
        "TISAX",
        "ISA 6",
        "Trusted Information Security Assessment Exchange for the automotive industry.",
        "industry",
        "eu",
        0,
        ["automotive", "germany", "assessment", "supplier"],
    ),
]

for _key, _slug, _name, _version, _description, _category, _region, _total, _tags in _ADDITIONAL_FRAMEWORKS:
    FRAMEWORKS[_key] = FrameworkMeta(
        id=_key,
        name=_name,
        version=_version,
        description=_description,
        category=_category,
        region=_region,
        control_prefix=_name.split()[0].upper(),
        url="",
        total_controls=_total,
        tags=_tags,
        slug=_slug,
    )

# Attach the mapping note from the mapping layer so the UI can label derived
# frameworks honestly instead of implying a full official crosswalk.
from unimonitor.grc.framework_mappings import DERIVED, EXPLICIT  # noqa: E402

for _key, _meta in FRAMEWORKS.items():
    if _meta.slug in EXPLICIT:
        _meta.mapping_note = EXPLICIT[_meta.slug]["note"]
    elif _meta.slug in DERIVED:
        _meta.mapping_note = DERIVED[_meta.slug]["note"]


# The API and UI use hyphenated ids; control YAML uses underscored compliance keys,
# and some frameworks have legacy aliases. Every framework lookup goes through this
# map, so a framework can never silently list only a subset of its controls.
FRAMEWORK_KEYS: dict[str, tuple[str, ...]] = {
    "iso27001-2022": ("iso27001_2022", "iso_27001_2022"),
    "iso42001": ("iso42001",),
    "nist-csf-2": ("nist_csf_2", "nist_csf"),
    "nist-800-53-r5": ("nist_800_53_r5", "nist_800_53"),
    "cis-controls-v8": ("cis_controls_v8", "cis"),
    "microsoft-zero-trust": ("zero_trust", "microsoft_zero_trust"),
    "cis-m365": ("cis_m365_benchmark", "cis_m365"),
    "soc2": ("soc2",),
    "pci-dss-4": ("pci_dss_v4", "pci_dss_4", "pci_dss"),
    "hipaa": ("hipaa",),
    "gdpr": ("gdpr",),
    "cpcsc": ("cpcsc", "cpcsc_2024"),
    "cmmc-2": ("cmmc_2", "cmmc_2_0"),
    "nist-800-171-r3": ("nist_800_171_r3",),
    "fedramp-low": ("fedramp_low",),
    "fedramp-moderate": ("fedramp_moderate",),
    "fedramp-high": ("fedramp_high",),
    "nis2": ("nis2",),
    "dora": ("dora",),
    "csa-ccm-v4": ("csa_ccm_v4",),
    "cisa-scuba-m365": ("cisa_scuba_m365",),
    "cisa-scuba-workspace": ("cisa_scuba_workspace",),
    "iso27017": ("iso27017",),
    "iso27018": ("iso27018",),
    "iso27701": ("iso27701",),
    "nist-ai-rmf": ("nist_ai_rmf",),
    "eu-ai-act": ("eu_ai_act",),
    "essential-eight": ("essential_eight",),
    "cyber-essentials": ("cyber_essentials",),
    "ccpa-cpra": ("ccpa_cpra",),
    "cjis": ("cjis",),
    "swift-csp": ("swift_csp",),
    "tisax": ("tisax",),
}


def framework_keys(framework_id: str) -> set[str]:
    """Every ``compliance_mapping`` key that belongs to a framework id."""
    lowered = framework_id.strip().lower()
    normalised = lowered.replace("-", "_")
    keys = {lowered, normalised}
    # Aliases are registered under the hyphenated id.
    keys.update(FRAMEWORK_KEYS.get(lowered, ()) or FRAMEWORK_KEYS.get(normalised, ()))
    return keys


def framework_id_for_key(key: str) -> str | None:
    """The canonical framework id for a ``compliance_mapping`` key."""
    normalised = key.strip().lower().replace("-", "_")
    for framework_id, aliases in FRAMEWORK_KEYS.items():
        if normalised == framework_id.replace("-", "_") or normalised in aliases:
            return framework_id
    return None


def get_framework(framework_id: str) -> FrameworkMeta | None:
    """Look a framework up by its API slug or by its underscore key."""
    if framework_id in FRAMEWORKS:
        return FRAMEWORKS[framework_id]
    normalised = framework_id.strip().lower()
    for meta in FRAMEWORKS.values():
        if meta.slug == normalised:
            return meta
    return None


def list_frameworks() -> list[FrameworkMeta]:
    return list(FRAMEWORKS.values())
