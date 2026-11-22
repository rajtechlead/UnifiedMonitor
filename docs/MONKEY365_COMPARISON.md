# Monkey365 comparison and multi-cloud plan

Analysis of [silverhack/monkey365](https://github.com/silverhack/monkey365) against
UnifiedMonitor, and the plan for AWS, GCP and Google Workspace. **This document is an
analysis and a plan; the multi-cloud collectors described at the end are not
implemented.** Nothing here should be read as delivered functionality.

## What Monkey365 is good at

| Area | Monkey365 | UnifiedMonitor today |
|---|---|---|
| Workloads | Entra ID, Exchange Online, SharePoint/OneDrive, Teams, Purview, Defender, Power Platform, Azure subscriptions, Intune | Entra ID and Microsoft 365 security controls through a Graph collector registry; Intune/Defender control families read as catalogue metadata |
| Depth | ~100 focused collectors, each returning raw configuration evidence | Control-driven: collectors feed a control catalogue, so depth is bounded by the controls defined |
| Output | HTML report with rich per-collector evidence, JSON/CSV export, per-finding remediation text | Compliance/GRC surfaces: frameworks, controls, findings, evidence chain, auditor portal, SOC metrics, reports (PDF/JSON) |
| Execution | Parallel per-workload runs, throttling-aware Graph client | Celery/Redis with an in-process fallback, rate-limited Graph client, per-run snapshots and trends |
| Auth | Device code / interactive MSAL, app-only with certificate or secret | App-only certificate/secret per tenant, plus SSO for the web UI |
| Extensibility | PowerShell collector modules | Python collectors registered in `unimonitor/graph/collector_registry.py` |
| Multi-cloud | Azure subscriptions alongside M365 | Microsoft-centric; no AWS, GCP or Google Workspace collectors |

## Concrete gaps worth closing

1. **Workload coverage.** Exchange Online (transport rules, DKIM, anti-phish), SharePoint
   sharing policy, Teams external access and Purview retention/labels are the highest
   value additions; today only what the control catalogue references is collected.
2. **Evidence fidelity.** Monkey365 keeps the raw collector output beside each finding.
   UnifiedMonitor stores findings and control states; the "show me the raw response"
   step of an audit is missing.
3. **Permission documentation.** Monkey365 publishes the exact Graph permission per
   collector. We document scopes at a workload level, which makes least-privilege
   review harder than it should be.
4. **Report parity.** Its HTML report is self-contained and browsable offline; our
   reports are generated server-side (PDF/JSON) and need the app to view.
5. **Test-mode controls.** Monkey365 can exercise individual collectors against a
   captured tenant; we have no per-collector fixture harness.

## What UnifiedMonitor has that Monkey365 does not

A control catalogue mapped to frameworks (ISO 27001, NIST CSF, CIS, SOC 2, Essential
Eight and others), multi-tenant/MSP operation with delegated access, tenant scoping on
every read, an evidence and auditor workflow, alerting with lifecycle metrics, scheduled
assessments with trend history, and a vault-backed secret store. Those are the reasons
not to copy Monkey365's architecture wholesale.

## Multi-cloud plan (not implemented)

The collector registry is already the seam. A cloud collector needs to satisfy the same
contract as the Graph collectors — return `dict[str, Any]` keyed by control input — so
the assessment engine, findings and framework mapping are reused unchanged.

| Platform | Library | Collectors (first slice) | Credential |
|---|---|---|---|
| AWS | `boto3` | IAM (root keys, MFA, password policy), S3 (public access block, encryption), CloudTrail (multi-region, validation), GuardDuty, Config | Cross-account role assumed with an external id; credentials in the vault |
| GCP | `google-cloud-asset`, `google-cloud-iam` | IAM primitive roles, service-account key age, org policy (uniform bucket access, public access prevention), audit log sinks | Workload identity / service-account JSON in the vault |
| Google Workspace | `google-api-python-client` (Admin SDK) | 2SV enforcement, admin role count, OAuth app allowlist, mail routing/DKIM, drive sharing | Domain-wide delegation with a service account |

Sequenced delivery, smallest useful increments:

1. Credential model and vault entries per cloud provider (no collectors).
2. One collector per cloud with a control subset mapped to the existing catalogue.
3. Findings emitted through the existing engine, so all dashboards and reports apply.
4. Framework coverage expanded once controls exist, not before.

Each slice needs a live account to verify; none of it can be honestly tested against
mocks alone, so verification is an explicit gate before release.
