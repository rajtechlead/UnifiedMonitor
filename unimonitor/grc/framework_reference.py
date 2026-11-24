"""Official shape of every framework this platform reports on.

The auditor portal used to show a framework's requirement list without saying how
large the framework actually is or which levels it publishes, so "derived" rows could
be mistaken for the official crosswalk. This module records, per framework, the
publisher, version, published control/requirement counts, the levels that exist and
whether those levels are cumulative.

Values come from the publisher's own documentation (links in ``source_url``); where a
publisher does not publish a total, the count is the number of requirements this
platform models and ``modelled`` is true, so a derived number is never presented as
official.
"""

from __future__ import annotations

from dataclasses import dataclass, field

ISO_IEC = "ISO/IEC"
EUROPEAN_UNION = "European Union"
FEDRAMP_BASELINES = "Rev. 5 baselines"
FEDRAMP_BASELINES_URL = "https://www.fedramp.gov/rev5/baselines/"


@dataclass(frozen=True)
class Level:
    """One level, tier, baseline or applicability class of a framework."""

    id: int
    name: str
    description: str = ""


@dataclass(frozen=True)
class FrameworkReference:
    """What the publisher says the framework contains."""

    name: str
    version: str
    publisher: str
    control_count: int
    requirement_count: int = 0
    levels: tuple[Level, ...] = (Level(1, "Baseline"),)
    # cumulative: every requirement applies at every level (IG1 -> IG3, ML1 -> ML3).
    # separate: levels are distinct baselines reported as their own framework.
    # maturity: tiers describe programme rigour, not a scope of requirements.
    # applicability: classes decide which requirements apply (entity type, merchant level).
    # report_type: report type, not a requirement scope.
    # none: no published levels.
    level_scope: str = "none"
    source_url: str = ""
    notes: str = ""
    # True when the count is this platform's modelled rows, not a published total.
    modelled: bool = False
    extra: dict[str, int] = field(default_factory=dict)


def _l(identifier: int, name: str, description: str = "") -> Level:
    return Level(identifier, name, description)


FRAMEWORK_REFERENCES: dict[str, FrameworkReference] = {
    "iso27001-2022": FrameworkReference(
        name="ISO/IEC 27001:2022",
        version="2022",
        publisher=ISO_IEC,
        control_count=93,
        requirement_count=93,
        levels=(_l(1, "Annex A", "One control set; applicability is decided by the risk assessment and the Statement of Applicability."),),
        source_url="https://www.iso.org/standard/27001",
        notes="93 Annex A controls: organisational 37, people 8, physical 14, technological 34.",
        extra={"clauses": 7},
    ),
    "iso42001": FrameworkReference(
        name="ISO/IEC 42001:2023",
        version="2023",
        publisher=ISO_IEC,
        control_count=38,
        requirement_count=38,
        levels=(_l(1, "Annex A", "AI management system controls; no published levels."),),
        source_url="https://www.iso.org/standard/81230.html",
        notes="Annex A has 38 AI management controls across nine domains.",
        extra={"domains": 9},
    ),
    "nist-csf-2": FrameworkReference(
        name="NIST Cybersecurity Framework 2.0",
        version="2.0 (CSWP 29)",
        publisher="NIST",
        control_count=106,
        requirement_count=106,
        levels=(
            _l(1, "Tier 1 — Partial", "Programme rigour, not a scope of requirements."),
            _l(2, "Tier 2 — Risk Informed"),
            _l(3, "Tier 3 — Repeatable"),
            _l(4, "Tier 4 — Adaptive"),
        ),
        level_scope="maturity",
        source_url="https://www.nist.gov/cyberframework",
        notes="6 functions, 22 categories and 106 subcategories; the subcategory is the assessable unit.",
        extra={"functions": 6, "categories": 22},
    ),
    "nist-800-53-r5": FrameworkReference(
        name="NIST SP 800-53 Rev. 5",
        version="Rev. 5",
        publisher="NIST",
        control_count=1189,
        levels=(
            _l(1, "Low baseline", "Reported as its own framework (FedRAMP Low)."),
            _l(2, "Moderate baseline", "Reported as its own framework (FedRAMP Moderate)."),
            _l(3, "High baseline", "Reported as its own framework (FedRAMP High)."),
        ),
        level_scope="separate",
        source_url="https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final",
        notes="20 control families; 1,189 controls and enhancements including the privacy overlay.",
        extra={"families": 20},
    ),
    "cis-controls-v8": FrameworkReference(
        name="CIS Critical Security Controls v8.1",
        version="8.1",
        publisher="Center for Internet Security",
        control_count=18,
        requirement_count=153,
        levels=(
            _l(1, "IG1 — essential cyber hygiene", "56 safeguards; cumulative."),
            _l(2, "IG2", "74 further safeguards; cumulative (130 total)."),
            _l(3, "IG3", "Final 23 safeguards; all 153."),
        ),
        level_scope="cumulative",
        source_url="https://www.cisecurity.org/controls/implementation-groups",
        notes="18 controls containing 153 safeguards, prioritised by three cumulative implementation groups.",
    ),
    "cis-m365": FrameworkReference(
        name="CIS Microsoft 365 Foundations Benchmark",
        version="v3.1.0",
        publisher="Center for Internet Security",
        control_count=82,
        levels=(
            _l(1, "Level 1 (E3)", "Baseline profile applicable to most organisations."),
            _l(2, "Level 2 (E5)", "Defence in depth for highly sensitive data."),
        ),
        level_scope="none",
        source_url="https://www.cisecurity.org/benchmark/microsoft_365",
        notes=(
            "The benchmark publishes Level 1 and Level 2 recommendations; this build models 82 mapped "
            "controls and does not claim per-control L1/L2 classification."
        ),
        modelled=True,
    ),
    "microsoft-zero-trust": FrameworkReference(
        name="Microsoft Zero Trust Assessment",
        version="364 tests",
        publisher="Microsoft",
        control_count=364,
        requirement_count=364,
        levels=(_l(1, "Pillars", "Identity, Devices, Data, Apps, Infrastructure, Network, Visibility, Automation."),),
        source_url="https://github.com/microsoft/zerotrustassessment",
        notes="364 PowerShell tests, mapped to the six CISA ZTMM pillars plus cross-cutting automation.",
        extra={"pillars": 6},
    ),
    "soc2": FrameworkReference(
        name="SOC 2 (Trust Services Criteria)",
        version="2017 TSC (2022 points of focus)",
        publisher="AICPA",
        control_count=33,
        requirement_count=33,
        levels=(
            _l(1, "Type I", "Design of controls at a point in time."),
            _l(2, "Type II", "Operating effectiveness over a period; not a scope of requirements."),
        ),
        level_scope="report_type",
        source_url="https://www.aicpa-cima.com/topic/audit-assurance/audit-and-assurance-greater-than-soc-2",
        notes="Five trust services categories; 33 criteria. Applicability depends on the system description.",
        extra={"categories": 5},
    ),
    "pci-dss-4": FrameworkReference(
        name="PCI DSS v4.0.1",
        version="4.0.1",
        publisher="PCI Security Standards Council",
        control_count=12,
        requirement_count=64,
        levels=(
            _l(1, "Merchant level 1", ">6 million transactions; applicability, not a control scope."),
            _l(2, "Merchant level 2"),
            _l(3, "Merchant level 3"),
            _l(4, "Merchant level 4"),
        ),
        level_scope="applicability",
        source_url="https://www.pcisecuritystandards.org/document_library/",
        notes="12 principal requirements and 64 defined requirements; about 250 testable sub-requirements.",
        extra={"sub_requirements": 250},
    ),
    "hipaa": FrameworkReference(
        name="HIPAA Security Rule",
        version="45 CFR Part 164 Subpart C",
        publisher="US HHS",
        control_count=18,
        requirement_count=54,
        levels=(
            _l(1, "Required", "Required implementation specifications."),
            _l(2, "Addressable", "Addressable specifications, documented if not implemented."),
        ),
        level_scope="separate",
        source_url="https://www.hhs.gov/hipaa/for-professionals/security/index.html",
        notes="Three safeguards (administrative, physical, technical), 18 standards and 54 implementation specifications.",
        extra={"safeguards": 3},
    ),
    "gdpr": FrameworkReference(
        name="EU GDPR",
        version="Regulation (EU) 2016/679",
        publisher=EUROPEAN_UNION,
        control_count=99,
        requirement_count=99,
        levels=(_l(1, "Articles", "99 articles; seven principles in Article 5."),),
        source_url="https://eur-lex.europa.eu/eli/reg/2016/679/oj",
        notes="99 articles; obligations and fines differ by role (controller/processor), not by level.",
        extra={"principles": 7},
    ),
    "cpcsc": FrameworkReference(
        name="Canadian Program for Cyber Security Certification",
        version="ITSP.10.171",
        publisher="Canadian Centre for Cyber Security",
        control_count=98,
        requirement_count=98,
        levels=(_l(1, "Level 1", "13 Level 1 criteria."), _l(2, "Level 2", "Remaining requirements.")),
        level_scope="none",
        source_url="https://www.cyber.gc.ca/en/guidance/canadian-program-cyber-security-certification",
        notes="98 requirements across 17 families; 13 Level 1 criteria. Official requirement text is not redistributed.",
        extra={"families": 17, "level1": 13},
    ),
    "cmmc-2": FrameworkReference(
        name="CMMC 2.0",
        version="2.0",
        publisher="US Department of Defense",
        control_count=110,
        levels=(
            _l(1, "Level 1 — Foundational", "17 practices."),
            _l(2, "Level 2 — Advanced", "110 practices aligned to NIST 800-171."),
            _l(3, "Level 3 — Expert", "110+ practices with selected 800-172 requirements."),
        ),
        level_scope="cumulative",
        source_url="https://www.acq.osd.mil/cmmc/",
        notes="Levels build on each other; Level 2 is the 110 NIST 800-171 requirements.",
        extra={"level1_practices": 17},
    ),
    "nist-800-171-r3": FrameworkReference(
        name="NIST SP 800-171 Rev. 3",
        version="Rev. 3",
        publisher="NIST",
        control_count=110,
        requirement_count=110,
        levels=(_l(1, "Requirements", "17 families; CMMC Level 2 basis."),),
        source_url="https://csrc.nist.gov/pubs/sp/800/171/r3/final",
        notes="17 control families and 110 requirements.",
        extra={"families": 17},
    ),
    "fedramp-low": FrameworkReference(
        name="FedRAMP Low Baseline",
        version=FEDRAMP_BASELINES,
        publisher="FedRAMP",
        control_count=156,
        levels=(_l(1, "Low", "Low-impact baseline derived from NIST 800-53 Rev. 5."),),
        source_url=FEDRAMP_BASELINES_URL,
        notes="Reported as its own framework so a Low assessment never inherits Moderate controls.",
    ),
    "fedramp-moderate": FrameworkReference(
        name="FedRAMP Moderate Baseline",
        version=FEDRAMP_BASELINES,
        publisher="FedRAMP",
        control_count=323,
        levels=(_l(1, "Moderate", "Moderate-impact baseline derived from NIST 800-53 Rev. 5."),),
        source_url=FEDRAMP_BASELINES_URL,
    ),
    "fedramp-high": FrameworkReference(
        name="FedRAMP High Baseline",
        version=FEDRAMP_BASELINES,
        publisher="FedRAMP",
        control_count=421,
        levels=(_l(1, "High", "High-impact baseline derived from NIST 800-53 Rev. 5."),),
        source_url=FEDRAMP_BASELINES_URL,
    ),
    "nis2": FrameworkReference(
        name="NIS2 Directive",
        version="Directive (EU) 2022/2555",
        publisher=EUROPEAN_UNION,
        control_count=10,
        requirement_count=10,
        levels=(
            _l(1, "Essential entity", "Stricter oversight and ex-ante supervision."),
            _l(2, "Important entity", "Lighter regime, same Article 21 measures."),
        ),
        level_scope="applicability",
        source_url="https://eur-lex.europa.eu/eli/dir/2022/2555/oj",
        notes="10 Article 21 risk-management measures; entity class changes obligations, not the measure list.",
        extra={"sectors": 18},
    ),
    "dora": FrameworkReference(
        name="Digital Operational Resilience Act",
        version="Regulation (EU) 2022/2554",
        publisher=EUROPEAN_UNION,
        control_count=5,
        requirement_count=5,
        levels=(_l(1, "Pillar", "Five pillars: ICT risk, incident reporting, resilience testing, third-party risk, information sharing."),),
        source_url="https://eur-lex.europa.eu/eli/reg/2022/2554/oj",
        notes="Five pillars in 4 chapters, 64 articles.",
        extra={"articles": 64},
    ),
    "csa-ccm-v4": FrameworkReference(
        name="CSA Cloud Controls Matrix v4",
        version="4.0",
        publisher="Cloud Security Alliance",
        control_count=197,
        requirement_count=197,
        levels=(_l(1, "Controls", "17 domains; 197 control objectives."),),
        source_url="https://cloudsecurityalliance.org/artifacts/cloud-controls-matrix-v4",
        notes="17 domains and 197 control objectives.",
        extra={"domains": 17},
    ),
    "cisa-scuba-m365": FrameworkReference(
        name="CISA SCuBA — Microsoft 365",
        version="Baseline (E3/E5)",
        publisher="CISA",
        control_count=0,
        levels=(
            _l(1, "E3", "Baseline for Microsoft 365 E3."),
            _l(2, "E5", "Additional controls for E5 security suites."),
        ),
        level_scope="none",
        source_url="https://www.cisa.gov/resources-tools/resources/secure-cloud-business-applications-scuba",
        notes="Prescriptive configuration baseline rather than a numbered control catalogue; EDMS covers L1/L2 baselines.",
        modelled=True,
    ),
    "cisa-scuba-workspace": FrameworkReference(
        name="CISA SCuBA — Google Workspace",
        version="Baseline",
        publisher="CISA",
        control_count=0,
        levels=(_l(1, "Baseline", "Prescriptive configuration baseline."),),
        source_url="https://www.cisa.gov/resources-tools/resources/secure-cloud-business-applications-scuba",
        notes="Prescriptive baseline; this build models the controls it can evidence.",
        modelled=True,
    ),
    "iso27017": FrameworkReference(
        name="ISO/IEC 27017:2015",
        version="2015",
        publisher=ISO_IEC,
        control_count=7,
        requirement_count=7,
        levels=(_l(1, "Cloud extensions", "Seven cloud-specific controls added to ISO 27002 guidance."),),
        source_url="https://www.iso.org/standard/43757.html",
        notes="Extends ISO 27001/27002 with seven cloud-service controls plus implementation guidance.",
    ),
    "iso27018": FrameworkReference(
        name="ISO/IEC 27018:2025",
        version="2025",
        publisher=ISO_IEC,
        control_count=25,
        requirement_count=25,
        levels=(_l(1, "PII protection", "Public-cloud PII processor controls."),),
        source_url="https://www.iso.org/standard/27018",
        notes="PII protection controls for public cloud processors; this build models the mapped subset.",
        modelled=True,
    ),
    "iso27701": FrameworkReference(
        name="ISO/IEC 27701:2025",
        version="2025",
        publisher=ISO_IEC,
        control_count=49,
        requirement_count=49,
        levels=(_l(1, "Privacy extension", "PIMS requirements extending ISO 27001/27002."),),
        source_url="https://www.iso.org/standard/27701",
        notes="Privacy information management extension; this build models the mapped subset.",
        modelled=True,
    ),
    "nist-ai-rmf": FrameworkReference(
        name="NIST AI Risk Management Framework 1.0",
        version="1.0",
        publisher="NIST",
        control_count=72,
        requirement_count=72,
        levels=(_l(1, "Core", "Four functions: Govern, Map, Measure, Manage."),),
        source_url="https://www.nist.gov/itl/ai-risk-management-framework",
        notes="4 functions, 19 categories and 72 subcategories.",
        extra={"functions": 4, "categories": 19},
    ),
    "eu-ai-act": FrameworkReference(
        name="EU Artificial Intelligence Act",
        version="Regulation (EU) 2024/1689",
        publisher=EUROPEAN_UNION,
        control_count=113,
        requirement_count=113,
        levels=(
            _l(1, "Unacceptable risk", "Prohibited practices."),
            _l(2, "High risk", "Conformity assessment and technical documentation."),
            _l(3, "Limited risk", "Transparency obligations."),
            _l(4, "Minimal risk", "No additional obligations."),
        ),
        level_scope="applicability",
        source_url="https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
        notes="113 articles; risk tier decides which obligations apply.",
        extra={"articles": 113},
    ),
    "essential-eight": FrameworkReference(
        name="ACSC Essential Eight",
        version="Maturity model (2023)",
        publisher="Australian Cyber Security Centre",
        control_count=8,
        requirement_count=8,
        levels=(
            _l(1, "Maturity Level 1", "Partly aligned against the mitigate strategies."),
            _l(2, "Maturity Level 2", "Mostly aligned; cumulative."),
            _l(3, "Maturity Level 3", "Fully aligned; cumulative."),
        ),
        level_scope="cumulative",
        source_url="https://www.cyber.gov.au/resources-business-and-government/essential-cyber-security/essential-eight",
        notes="Eight mitigation strategies, each assessed at three cumulative maturity levels.",
        extra={"strategies": 8},
    ),
    "cyber-essentials": FrameworkReference(
        name="UK Cyber Essentials",
        version="v3.1 (Montpellier)",
        publisher="NCSC / IASME",
        control_count=5,
        requirement_count=5,
        levels=(_l(1, "Cyber Essentials", "Five technical controls."), _l(2, "Cyber Essentials Plus", "Adds independent verification.")),
        level_scope="report_type",
        source_url="https://www.ncsc.gov.uk/cyberessentials/overview",
        notes="Five controls: firewalls, secure configuration, access control, malware protection and patching.",
    ),
    "ccpa-cpra": FrameworkReference(
        name="CCPA / CPRA",
        version="as amended by CPRA",
        publisher="California Privacy Protection Agency",
        control_count=7,
        requirement_count=7,
        levels=(
            _l(1, "Consumer rights", "Seven consumer rights."),
            _l(2, "Business obligations", "Thresholds decide applicability."),
        ),
        level_scope="applicability",
        source_url="https://cppa.ca.gov/regulations/",
        notes="Seven consumer rights; applicability depends on revenue/data thresholds.",
        extra={"rights": 7},
    ),
    "cjis": FrameworkReference(
        name="FBI CJIS Security Policy",
        version="v6.0",
        publisher="US Federal Bureau of Investigation",
        control_count=13,
        requirement_count=13,
        levels=(_l(1, "Policy areas", "13 policy areas; provisions vary by advanced authentication tier."),),
        source_url="https://www.fbi.gov/services/cjis/cjis-security-policy-resource-center",
        notes="13 policy areas including access control, audit, incident response and personnel security.",
        extra={"policy_areas": 13},
    ),
    "swift-csp": FrameworkReference(
        name="SWIFT Customer Security Controls Framework",
        version="CSCF v2026",
        publisher="SWIFT",
        control_count=32,
        requirement_count=32,
        levels=(
            _l(1, "Mandatory controls", "26 mandatory controls."),
            _l(2, "Advisory controls", "6 advisory controls."),
        ),
        level_scope="separate",
        source_url="https://www.swift.com/myswift/customer-security-programme-csp",
        notes="32 controls across three objectives and seven principles; architecture type decides which apply.",
        extra={"objectives": 3, "principles": 7, "mandatory": 26, "advisory": 6},
    ),
    "tisax": FrameworkReference(
        name="TISAX (VDA ISA)",
        version="ISA 6",
        publisher="ENX Association",
        control_count=0,
        levels=(
            _l(1, "AL1", "Assessment level 1 — self-assessment."),
            _l(2, "AL2", "Assessment level 2 — remote verification."),
            _l(3, "AL3", "Assessment level 3 — on-site verification; cumulative."),
        ),
        level_scope="cumulative",
        source_url="https://www.enx.com/tisax/",
        notes="Assessment level depends on the protection needs of the data exchanged; AL3 includes AL1 and AL2.",
        modelled=True,
    ),
}


def reference_for(framework_id: str) -> FrameworkReference:
    """The reference entry, or a conservative default for an unregistered id."""
    return FRAMEWORK_REFERENCES.get(
        framework_id,
        FrameworkReference(
            name=framework_id,
            version="",
            publisher="",
            control_count=0,
            levels=(Level(1, "Baseline"),),
            modelled=True,
            notes="No official reference metadata is recorded for this framework.",
        ),
    )


__all__ = ["FRAMEWORK_REFERENCES", "FrameworkReference", "Level", "reference_for"]
