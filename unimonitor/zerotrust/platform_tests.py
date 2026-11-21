"""Zero Trust architecture catalogues for AWS, Google Cloud and Google Workspace.

Microsoft publishes 364 PowerShell tests, ported in :mod:`unimonitor.zerotrust.microsoft`.
The other three platforms have no equivalent single assessment, so their catalogue is
derived from published Zero Trust guidance and scored from UniMonitor's own evidence:

* AWS — *Zero trust on AWS*, AWS Prescriptive Guidance "Strategy for zero trust
  architecture", and the Well-Architected security pillar.
* Google Cloud — the Cloud Architecture Center's "Implement zero trust" and the
  BeyondCorp/Context-Aware Access model (IAP, VPC Service Controls, workload identity).
* Google Workspace — the Workspace security checklist and CISA ZTMM guidance for
  collaboration suites (2-Step Verification, context-aware access, DLP, app control).

Each test names the UniMonitor controls (:class:`ControlDefinition`) whose collected
evidence answers it. A test with no control is a real architecture gap and is reported
as ``not_run`` with a remediation plan, rather than being silently dropped or passed.
"""

from __future__ import annotations

from dataclasses import dataclass

CISA_ZTMM = "https://www.cisa.gov/resources-tools/resources/zero-trust-maturity-model"

AWS_IAM = "AWS IAM"
GOOGLE_WORKSPACE = "Google Workspace"


@dataclass(frozen=True, slots=True)
class PlatformTest:
    """One Zero Trust test in a platform catalogue."""

    id: str
    title: str
    pillar: str
    category: str
    severity: str
    control_ids: tuple[str, ...]
    remediation: tuple[str, ...]
    reference: str


AWS_REF = "https://docs.aws.amazon.com/prescriptive-guidance/latest/strategy-zero-trust-architecture/"
GCP_REF = "https://cloud.google.com/architecture/framework/security/implement-zero-trust"
GWS_REF = "https://support.google.com/a/answer/7587183"

AWS_TESTS: tuple[PlatformTest, ...] = (
    PlatformTest(
        "AWS-ZT-001",
        "Root account has MFA enabled",
        "identity",
        AWS_IAM,
        "critical",
        ("CTRL-AWS-001",),
        ("Enable a hardware or virtual MFA device on the root user.", "Stop using root for daily work; use IAM Identity Center or roles."),
        AWS_REF,
    ),
    PlatformTest(
        "AWS-ZT-002",
        "IAM password policy enforces length, complexity and reuse limits",
        "identity",
        AWS_IAM,
        "high",
        ("CTRL-AWS-002",),
        ("Set a 14+ character policy with upper/lower/numbers/symbols and reuse prevention of 24.",),
        AWS_REF,
    ),
    PlatformTest(
        "AWS-ZT-003",
        "IAM access keys are rotated within 90 days",
        "identity",
        AWS_IAM,
        "high",
        ("CTRL-AWS-003",),
        ("Rotate long-lived access keys and move workloads to IAM roles or federation.",),
        AWS_REF,
    ),
    PlatformTest(
        "AWS-ZT-004",
        "No IAM policy grants wildcard actions on wildcard resources",
        "identity",
        AWS_IAM,
        "critical",
        (),
        (
            "Replace `Action: *`/`Resource: *` with least-privilege statements.",
            "Use IAM Access Analyzer policy validation and unused-permission findings.",
        ),
        "https://docs.aws.amazon.com/IAM/latest/UserGuide/access-analyzer-best-practices.html",
    ),
    PlatformTest(
        "AWS-ZT-005",
        "Workforce access is federated through a central identity provider",
        "identity",
        "AWS IAM Identity Center",
        "high",
        (),
        ("Connect IAM Identity Center to the corporate IdP and assign permission sets instead of IAM users.",),
        "https://docs.aws.amazon.com/singlesignon/latest/userguide/what-is.html",
    ),
    PlatformTest(
        "AWS-ZT-006",
        "Organizations apply service control policies as guardrails",
        "identity",
        "AWS Organizations",
        "high",
        ("CTRL-AWS-012",),
        ("Enable SCPs that deny disabling of CloudTrail/GuardDuty and restrict Regions and root access.",),
        "https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html",
    ),
    PlatformTest(
        "AWS-ZT-010",
        "S3 buckets block public access and encrypt at rest",
        "data",
        "Amazon S3",
        "critical",
        ("CTRL-AWS-004",),
        ("Enable Block Public Access at account level and default SSE-KMS encryption on every bucket.",),
        "https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html",
    ),
    PlatformTest(
        "AWS-ZT-011",
        "Customer-managed KMS keys rotate automatically",
        "data",
        "AWS KMS",
        "medium",
        ("CTRL-AWS-011",),
        ("Enable annual rotation on customer-managed keys and remove unused keys.",),
        "https://docs.aws.amazon.com/kms/latest/developerguide/rotate-keys.html",
    ),
    PlatformTest(
        "AWS-ZT-012",
        "Sensitive data stores are classified and monitored for exposure",
        "data",
        "Amazon Macie",
        "high",
        (),
        ("Enable Macie on accounts holding sensitive data and act on its exposure findings.",),
        "https://docs.aws.amazon.com/macie/latest/user/what-is-macie.html",
    ),
    PlatformTest(
        "AWS-ZT-020",
        "Security groups do not expose management ports to the internet",
        "network",
        "Amazon VPC",
        "critical",
        ("CTRL-AWS-009",),
        ("Remove 0.0.0.0/0 ingress on 22/3389/5432/3306; use SSM Session Manager or a bastion in a private subnet.",),
        "https://docs.aws.amazon.com/vpc/latest/userguide/security-group-rules.html",
    ),
    PlatformTest(
        "AWS-ZT-021",
        "VPC flow logs are enabled and retained",
        "network",
        "Amazon VPC",
        "high",
        ("CTRL-AWS-010",),
        ("Enable flow logs on every VPC to CloudWatch Logs or S3 with a retention policy.",),
        "https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs.html",
    ),
    PlatformTest(
        "AWS-ZT-022",
        "Service access uses private endpoints instead of the public internet",
        "network",
        "AWS PrivateLink",
        "medium",
        (),
        ("Create interface VPC endpoints for S3, KMS, STS and other services workloads call.",),
        "https://docs.aws.amazon.com/vpc/latest/privatelink/what-is-privatelink.html",
    ),
    PlatformTest(
        "AWS-ZT-030",
        "CloudTrail records management events in every Region",
        "infrastructure",
        "AWS CloudTrail",
        "critical",
        ("CTRL-AWS-005",),
        ("Create an organization trail with multi-Region logging and log-file validation.",),
        AWS_REF,
    ),
    PlatformTest(
        "AWS-ZT-031",
        "GuardDuty threat detection is enabled in all accounts",
        "secops",
        "Amazon GuardDuty",
        "critical",
        ("CTRL-AWS-006",),
        ("Delegate GuardDuty to the security account and auto-enable it for new accounts.",),
        AWS_REF,
    ),
    PlatformTest(
        "AWS-ZT-032",
        "AWS Config continuously records resource configuration",
        "infrastructure",
        "AWS Config",
        "high",
        ("CTRL-AWS-007",),
        ("Enable a recorder in every Region and deliver snapshots to a central bucket.",),
        AWS_REF,
    ),
    PlatformTest(
        "AWS-ZT-033",
        "Security Hub aggregates findings across accounts",
        "secops",
        "AWS Security Hub",
        "high",
        ("CTRL-AWS-008",),
        ("Enable Security Hub with the Foundational Security Best Practices standard in every account.",),
        AWS_REF,
    ),
    PlatformTest(
        "AWS-ZT-034",
        "Audit logs are archived centrally with defined retention",
        "secops",
        "AWS CloudTrail / S3",
        "high",
        (),
        ("Deliver CloudTrail and Config to a log-archive account with Object Lock and 1+ year retention.",),
        "https://docs.aws.amazon.com/whitepapers/latest/logical-separation/centralized-logging.html",
    ),
    PlatformTest(
        "AWS-ZT-040",
        "Instances are managed, patched and inventoried",
        "devices",
        "AWS Systems Manager",
        "high",
        ("CTRL-AWS-013",),
        ("Onboard instances to SSM, enforce patch baselines and alert on non-compliant managed nodes.",),
        "https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-patch.html",
    ),
    PlatformTest(
        "AWS-ZT-050",
        "IAM Access Analyzer reports external and unused access",
        "identity",
        "IAM Access Analyzer",
        "medium",
        ("CTRL-AWS-014",),
        ("Enable Access Analyzer at the organization level and review external-access findings.",),
        "https://docs.aws.amazon.com/IAM/latest/UserGuide/what-is-access-analyzer.html",
    ),
)

GCP_TESTS: tuple[PlatformTest, ...] = (
    PlatformTest(
        "GCP-ZT-001",
        "No primitive Owner or Editor roles granted at project level",
        "identity",
        "Cloud IAM",
        "critical",
        ("CTRL-GCP-001",),
        ("Replace primitive roles with predefined or custom least-privilege roles.",),
        GCP_REF,
    ),
    PlatformTest(
        "GCP-ZT-002",
        "User-managed service account keys are avoided",
        "identity",
        "Cloud IAM",
        "high",
        ("CTRL-GCP-002",),
        ("Move workloads to Workload Identity Federation or attached service accounts and disable key creation.",),
        "https://cloud.google.com/iam/docs/workload-identity-federation",
    ),
    PlatformTest(
        "GCP-ZT-003",
        "Firewall rules do not expose management ports to the internet",
        "network",
        "VPC firewall",
        "critical",
        ("CTRL-GCP-003",),
        ("Restrict 0.0.0.0/0 ingress on 22/3389 and use IAP TCP forwarding instead.",),
        "https://cloud.google.com/iap/docs/using-tcp-forwarding",
    ),
    PlatformTest(
        "GCP-ZT-004",
        "Audit logs are exported through an organization log sink",
        "secops",
        "Cloud Logging",
        "high",
        ("CTRL-GCP-004",),
        ("Create an aggregated organization sink to a locked-down logging project or bucket.",),
        GCP_REF,
    ),
    PlatformTest(
        "GCP-ZT-005",
        "Cloud Storage buckets enforce uniform access and customer-managed keys",
        "data",
        "Cloud Storage",
        "high",
        ("CTRL-GCP-005",),
        ("Enable uniform bucket-level access and default CMEK on buckets holding sensitive data.",),
        "https://cloud.google.com/storage/docs/uniform-bucket-level-access",
    ),
    PlatformTest(
        "GCP-ZT-006",
        "KMS keys rotate within 90 days",
        "data",
        "Cloud KMS",
        "medium",
        ("CTRL-GCP-006",),
        ("Set a rotation period of 90 days or less on symmetric CMEK keys.",),
        "https://cloud.google.com/kms/docs/rotating-keys",
    ),
    PlatformTest(
        "GCP-ZT-007",
        "Organization policy constraints enforce the security baseline",
        "infrastructure",
        "Organization Policy",
        "high",
        ("CTRL-GCP-007",),
        ("Enforce constraints such as disableSerialPortAccess, disableSAKeyCreation and restrictPublicBuckets.",),
        "https://cloud.google.com/resource-manager/docs/organization-policy/overview",
    ),
    PlatformTest(
        "GCP-ZT-008",
        "VPC flow logs are enabled on every subnetwork",
        "network",
        "VPC",
        "high",
        ("CTRL-GCP-008",),
        ("Enable flow logs on all subnetworks and export them to the central logging project.",),
        "https://cloud.google.com/vpc/docs/using-flow-logs",
    ),
    PlatformTest(
        "GCP-ZT-009",
        "Internal applications are published through Identity-Aware Proxy",
        "identity",
        "Identity-Aware Proxy",
        "high",
        ("CTRL-GCP-009",),
        ("Put internal web apps and SSH/RDP behind IAP instead of exposing them on the internet.",),
        "https://cloud.google.com/iap/docs/concepts-overview",
    ),
    PlatformTest(
        "GCP-ZT-010",
        "Context-Aware Access policies gate application access",
        "identity",
        "Access Context Manager",
        "high",
        ("CTRL-GCP-010",),
        ("Create access levels from device and network attributes and bind them to IAP/Workspace apps.",),
        "https://cloud.google.com/access-context-manager/docs/overview",
    ),
    PlatformTest(
        "GCP-ZT-011",
        "VPC Service Controls isolate sensitive APIs",
        "network",
        "VPC Service Controls",
        "high",
        ("CTRL-GCP-011",),
        ("Put sensitive projects in a service perimeter and restrict data exfiltration paths.",),
        "https://cloud.google.com/vpc-service-controls/docs/overview",
    ),
    PlatformTest(
        "GCP-ZT-012",
        "Security Command Center Premium findings are triaged",
        "secops",
        "Security Command Center",
        "high",
        ("CTRL-GCP-012",),
        ("Enable SCC Premium at organization level and route high-severity findings to the SOC.",),
        "https://cloud.google.com/security-command-center/docs/overview",
    ),
    PlatformTest(
        "GCP-ZT-013",
        "Workloads federate identity instead of using exported keys",
        "identity",
        "Workload Identity Federation",
        "high",
        (),
        ("Configure Workload Identity Federation for CI/CD and on-prem workloads; delete exported keys.",),
        "https://cloud.google.com/iam/docs/workload-identity-federation",
    ),
    PlatformTest(
        "GCP-ZT-014",
        "Only signed and attested container images are deployed",
        "infrastructure",
        "Binary Authorization",
        "medium",
        (),
        ("Enforce Binary Authorization attestations on GKE clusters running production workloads.",),
        "https://cloud.google.com/binary-authorization/docs/overview",
    ),
    PlatformTest(
        "GCP-ZT-015",
        "Data Access audit logs are enabled for sensitive services",
        "secops",
        "Cloud Audit Logs",
        "high",
        (),
        ("Enable Data Access logs for Cloud Storage, BigQuery and KMS at organization level.",),
        "https://cloud.google.com/logging/docs/audit/configure-data-access",
    ),
)

GOOGLE_WORKSPACE_TESTS: tuple[PlatformTest, ...] = (
    PlatformTest(
        "GWS-ZT-001",
        "Two-Step Verification is enforced for all users",
        "identity",
        GOOGLE_WORKSPACE,
        "critical",
        ("CTRL-GWS-001",),
        ("Enforce 2SV for the whole domain and allow only phishing-resistant methods for admins.",),
        "https://support.google.com/a/answer/175197",
    ),
    PlatformTest(
        "GWS-ZT-002",
        "Super admin accounts are limited and monitored",
        "identity",
        GOOGLE_WORKSPACE,
        "high",
        ("CTRL-GWS-002",),
        ("Keep at most four super admins; use delegated admin roles for daily work.",),
        "https://support.google.com/a/answer/2405986",
    ),
    PlatformTest(
        "GWS-ZT-003",
        "Custom admin roles follow least privilege",
        "identity",
        GOOGLE_WORKSPACE,
        "high",
        ("CTRL-GWS-003",),
        ("Review custom roles, remove unused privileges and prefer predefined roles.",),
        "https://support.google.com/a/answer/2405986",
    ),
    PlatformTest(
        "GWS-ZT-004",
        "Third-party OAuth access is reviewed and restricted",
        "identity",
        GOOGLE_WORKSPACE,
        "high",
        ("CTRL-GWS-004",),
        ("Review app access control, block unverified apps and revoke unused tokens.",),
        "https://support.google.com/a/answer/7281227",
    ),
    PlatformTest(
        "GWS-ZT-005",
        "External file sharing is restricted",
        "data",
        "Google Drive",
        "high",
        ("CTRL-GWS-005",),
        ("Set sharing to restricted by default and limit external sharing by organizational unit.",),
        "https://support.google.com/a/answer/60781",
    ),
    PlatformTest(
        "GWS-ZT-006",
        "Mobile access is limited to approved, managed devices",
        "devices",
        GOOGLE_WORKSPACE,
        "high",
        ("CTRL-GWS-006",),
        ("Require device approval for mobile access and enforce basic/advanced management.",),
        "https://support.google.com/a/answer/6356568",
    ),
    PlatformTest(
        "GWS-ZT-007",
        "Context-Aware Access policies protect sensitive apps",
        "identity",
        "Access Context Manager",
        "high",
        (),
        ("Create access levels (device encryption, screen lock, IP range) and bind them to apps.",),
        "https://support.google.com/a/answer/9262013",
    ),
    PlatformTest(
        "GWS-ZT-008",
        "Data Loss Prevention rules cover sensitive content",
        "data",
        GOOGLE_WORKSPACE,
        "high",
        (),
        ("Deploy DLP rules for Drive, Gmail and Chat with quarantine/block actions.",),
        "https://support.google.com/a/answer/2693011",
    ),
    PlatformTest(
        "GWS-ZT-009",
        "Admin alert rules notify on high-risk activity",
        "secops",
        GOOGLE_WORKSPACE,
        "medium",
        (),
        ("Configure alert rules for suspicious logins, OAuth grants and Drive sharing changes.",),
        "https://support.google.com/a/answer/3230421",
    ),
    PlatformTest(
        "GWS-ZT-010",
        "Password policy enforces length and reuse limits",
        "identity",
        GOOGLE_WORKSPACE,
        "medium",
        (),
        ("Set minimum length 14+, prohibit reuse and enable password strength requirements.",),
        "https://support.google.com/a/answer/139399",
    ),
    PlatformTest(
        "GWS-ZT-011",
        "Drive trust rules restrict external and risky sharing",
        "data",
        "Google Drive",
        "medium",
        (),
        ("Use trust rules to block sharing outside trusted domains or with anyone-links.",),
        "https://support.google.com/a/answer/9940760",
    ),
    PlatformTest(
        "GWS-ZT-012",
        "Endpoint verification is required for access",
        "devices",
        GOOGLE_WORKSPACE,
        "medium",
        (),
        ("Require Endpoint Verification and use its device attributes in Context-Aware Access.",),
        "https://support.google.com/a/answer/9007320",
    ),
    PlatformTest(
        "GWS-ZT-013",
        "Only approved applications can access Workspace data",
        "identity",
        GOOGLE_WORKSPACE,
        "high",
        (),
        ("Enable app access control with an allowlist of trusted apps and block the rest.",),
        "https://support.google.com/a/answer/7281227",
    ),
    PlatformTest(
        "GWS-ZT-014",
        "Email authentication (SPF, DKIM, DMARC) is enforced",
        "data",
        "Gmail",
        "high",
        (),
        ("Publish SPF and DKIM for every domain and move DMARC to p=reject.",),
        "https://support.google.com/a/answer/2466580",
    ),
)

PLATFORM_TESTS: dict[str, tuple[PlatformTest, ...]] = {
    "aws": AWS_TESTS,
    "gcp": GCP_TESTS,
    "google_workspace": GOOGLE_WORKSPACE_TESTS,
}

PLATFORM_CATALOGUE_NAMES: dict[str, str] = {
    "aws": "AWS Zero Trust (UniMonitor Python catalogue)",
    "gcp": "Google Cloud Zero Trust (UniMonitor Python catalogue)",
    "google_workspace": "Google Workspace Zero Trust (UniMonitor Python catalogue)",
}


def tests_for(platform: str) -> tuple[PlatformTest, ...]:
    """The platform's tests, empty for platforms without a native catalogue."""
    return PLATFORM_TESTS.get(platform, ())
