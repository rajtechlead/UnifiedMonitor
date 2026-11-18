"""Insert remediation blocks into the AWS, GCP and Workspace control YAML files.

Run once; kept in the repo so the wording is reviewable in the diff and can be
re-applied if a control file is regenerated. Text is plain YAML with no inner
double quotes so the edit stays readable.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REMEDIATION: dict[str, tuple[str, list[str]]] = {
    # ── AWS ──────────────────────────────────────────────────────────────
    "CTRL-AWS-001": (
        "Enable MFA on the root user and stop using it for day-to-day work.",
        [
            "Sign in as the root user, open IAM > Security credentials, and assign a hardware or virtual MFA device.",
            "Create an IAM Identity Center or IAM role for administrative work and delete root access keys.",
            "Enable an AWS Config rule or Security Hub control to alert if root MFA is removed.",
        ],
    ),
    "CTRL-AWS-002": (
        "Raise the account password policy to the baseline in the control description.",
        [
            "IAM > Account settings > Password policy: 14+ characters, upper/lower/numbers/symbols, reuse prevention 24.",
            "Apply with: aws iam update-account-password-policy --minimum-password-length 14 --require-symbols "
            "--require-numbers --require-uppercase-characters --require-lowercase-characters --password-reuse-prevention 24.",
            "Prefer federation (IAM Identity Center) so humans never hold IAM passwords.",
        ],
    ),
    "CTRL-AWS-003": (
        "Rotate or remove long-lived IAM access keys.",
        [
            "List keys with age: aws iam list-users, then aws iam list-access-keys for each user.",
            "Create a replacement key, deploy it, then deactivate and delete the old key.",
            "Move workloads to IAM roles or OIDC federation so keys are not needed at all.",
        ],
    ),
    "CTRL-AWS-004": (
        "Block public S3 access and turn on default encryption for every bucket.",
        [
            "Enable Block Public Access at the account level: aws s3control put-public-access-block --account-id <id> "
            "--public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true.",
            "Turn on default encryption (SSE-S3 or SSE-KMS) per bucket and in the account-level default.",
            "Re-check bucket policies and ACLs that were granting public read before the block.",
        ],
    ),
    "CTRL-AWS-005": (
        "Run a multi-region CloudTrail trail with log-file validation.",
        [
            "Create or update a trail with IsMultiRegionTrail and EnableLogFileValidation set to true.",
            "Deliver logs to a dedicated, restricted S3 bucket with object lock and lifecycle retention.",
            "Turn on CloudTrail insights and alarms for StopLogging and DeleteTrail events.",
        ],
    ),
    "CTRL-AWS-006": (
        "Enable GuardDuty in every region and route findings to a responder.",
        [
            "Enable GuardDuty per region (Organizations can auto-enable for new accounts).",
            "Export findings to Security Hub or EventBridge and page on High/Critical.",
            "Add S3, EKS and malware protection plans where the account uses those services.",
        ],
    ),
    "CTRL-AWS-007": (
        "Enable AWS Config recording with the conformance packs that matter.",
        [
            "Create a configuration recorder and delivery channel in each region.",
            "Apply the CIS or FSBP conformance pack, and remediate non-compliant resources.",
            "Aggregate to an organisation aggregator so multi-account posture is visible.",
        ],
    ),
    "CTRL-AWS-008": (
        "Turn on Security Hub and adopt a standard.",
        [
            "Enable Security Hub in the home region and the AWS Foundational Security Best Practices standard.",
            "Enable cross-region and cross-account aggregation.",
            "Route critical findings to the ticket queue used by the operations team.",
        ],
    ),
    # ── GCP ──────────────────────────────────────────────────────────────
    "CTRL-GCP-001": (
        "Remove primitive Owner and Editor bindings from project IAM.",
        [
            "List bindings: gcloud projects get-iam-policy <project> --format=json.",
            "Replace roles/owner and roles/editor with predefined roles scoped to the task.",
            "Enforce with the constraint iam.allowedPolicyMemberDomains and org policy iam.disableServiceAccountKeyCreation where possible.",
        ],
    ),
    "CTRL-GCP-002": (
        "Stop issuing user-managed service account keys.",
        [
            "List keys: gcloud iam service-accounts keys list --iam-account=<sa> --managed-by=user.",
            "Migrate workloads to Workload Identity Federation or attached service accounts.",
            "Delete unused keys and set an organisation policy to block new ones.",
        ],
    ),
    "CTRL-GCP-003": (
        "Restrict firewall rules that expose management ports to the internet.",
        [
            "List rules: gcloud compute firewall-rules list --format=json.",
            "Remove 0.0.0.0/0 sources on 22, 3389, 5432, 3306 and 1433, or scope them to Identity-Aware Proxy ranges.",
            "Prefer IAP TCP forwarding or a bastion over public management ports.",
        ],
    ),
    "CTRL-GCP-004": (
        "Export audit logs to a central, retained destination.",
        [
            "Create an aggregated sink at the organisation level with includeChildren.",
            "Send to a log bucket with retention and to the SIEM; restrict who can modify the sink.",
            "Enable Data Access audit logs for the services that hold sensitive data.",
        ],
    ),
    "CTRL-GCP-005": (
        "Apply uniform bucket-level access and customer-managed encryption.",
        [
            "Enable uniform bucket-level access on every bucket and remove legacy ACLs.",
            "Set a Cloud KMS key as the default encryption key for sensitive buckets.",
            "Review public IAM bindings (allUsers, allAuthenticatedUsers) and remove them.",
        ],
    ),
    "CTRL-GCP-006": (
        "Rotate Cloud KMS keys within 90 days.",
        [
            "Set a rotation schedule: gcloud kms keys update <key> --rotation-period=90d --next-rotation-time=<date>.",
            "Grant only roles/cloudkms.cryptoKeyEncrypterDecrypter to workloads.",
            "Alert on key version destruction and on rotation failures.",
        ],
    ),
    "CTRL-GCP-007": (
        "Enforce the organisation policies that back this baseline.",
        [
            "Apply constraints such as compute.vmExternalIpAccess, storage.publicAccessPrevention and iam.disableServiceAccountKeyCreation.",
            "Apply at the organisation or folder so new projects inherit them.",
            "Track exceptions explicitly rather than by leaving policies unenforced.",
        ],
    ),
    "CTRL-GCP-008": (
        "Enable VPC flow logs on every subnetwork.",
        [
            "Update each subnetwork: gcloud compute networks subnets update <subnet> --enable-flow-logs.",
            "Set a sampling rate and aggregation interval that match the retention budget.",
            "Export flow logs to the central logging project.",
        ],
    ),
    # ── Google Workspace ─────────────────────────────────────────────────
    "CTRL-GWS-001": (
        "Enforce two-step verification for the whole organisation.",
        [
            "Admin console > Security > Authentication > 2-step verification: turn on enforcement for all users.",
            "Allow only phishing-resistant methods for admins (security keys or passkeys).",
            "Track enrolment and generate a report for users who have not enrolled.",
        ],
    ),
    "CTRL-GWS-002": (
        "Reduce the number of super admins to four or fewer.",
        [
            "Review Admin console > Account > Admin roles > Super Admin members.",
            "Give day-to-day administrators delegated roles instead of Super Admin.",
            "Require security keys and alert on Super Admin sign-ins.",
        ],
    ),
    "CTRL-GWS-003": (
        "Scope custom admin roles to the privileges they actually need.",
        [
            "Review custom roles and remove privileges not used in the last 90 days.",
            "Prefer predefined roles over broad custom roles with org-wide scope.",
            "Re-certify role assignments quarterly with the role holders' managers.",
        ],
    ),
    "CTRL-GWS-004": (
        "Review and revoke unnecessary third-party OAuth grants.",
        [
            "Admin console > Security > API controls > App access control: review granted apps.",
            "Block apps that are not approved; revoke tokens for leavers.",
            "Set app access control to trust only verified internal apps by default.",
        ],
    ),
    "CTRL-GWS-005": (
        "Restrict external sharing in Drive and Docs.",
        [
            "Admin console > Apps > Google Workspace > Drive and Docs > Sharing settings: limit external sharing by domain.",
            "Disable public link sharing or restrict it to approved organisational units.",
            "Alert on high-volume external sharing via the Drive audit log.",
        ],
    ),
    "CTRL-GWS-006": (
        "Limit mobile access to approved, managed devices.",
        [
            "Admin console > Devices > Mobile and endpoints: require approval and basic or advanced management.",
            "Block access from devices that fail the management policy.",
            "Review the mobile device inventory for unmanaged or stale devices.",
        ],
    ),
}


def yaml_block(summary: str, steps: list[str]) -> str:
    lines = ["    remediation:", f'      summary: "{summary}"', "      steps:"]
    lines += [f'        - action: "{step}"' for step in steps]
    return "\n".join(lines) + "\n"


def main() -> None:
    for name in ("aws", "gcp", "google_workspace"):
        path = ROOT / "controls" / name / "security_controls.yaml"
        text = path.read_text(encoding="utf-8")
        if "    remediation:" in text:
            print(f"{path}: already has remediation, skipping")
            continue
        for control_id, (summary, steps) in REMEDIATION.items():
            marker = f"  - id: {control_id}"
            start = text.find(marker)
            if start == -1:
                continue
            # Insert before the next control block, or at the end of the file.
            next_start = text.find("\n  - id: ", start + len(marker))
            insert_at = next_start + 1 if next_start != -1 else len(text)
            block = yaml_block(summary, steps)
            text = text[:insert_at].rstrip("\n") + "\n" + block + "\n" + text[insert_at:]
        path.write_text(text, encoding="utf-8")
        print(f"{path}: remediation added")


if __name__ == "__main__":
    main()
