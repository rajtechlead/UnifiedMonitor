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
        total_controls=58,
        tags=["canada", "defense", "certification"],
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
    ),
}


def get_framework(framework_id: str) -> FrameworkMeta | None:
    return FRAMEWORKS.get(framework_id)


def list_frameworks() -> list[FrameworkMeta]:
    return list(FRAMEWORKS.values())
