## 2026-11-22 — owner observations, atomic vault writes, case-insensitive severity

Full register: [`docs/PLATFORM_OBSERVATIONS_2026-11-22.md`](docs/PLATFORM_OBSERVATIONS_2026-11-22.md).

- ✅ Local vault writes are atomic: the ciphertext, the metadata and a new master
  key are staged in a sibling file, flushed, then renamed over the destination, so
  a crash mid-write leaves the previous vault readable and no partial file behind.
  Tests prove both failure points (`fsync`, `os.replace`) leave the old vault intact.
- ✅ `GET /dashboard/ciso` returns `strongest_frameworks` next to the weakest; the
  CISO footer counts link into the findings list (OBS-02).
- ✅ Risk dashboard hides findings from providers that are not connected, and
  rebuilds the heatmap from the same filtered ids (OBS-06).
- ✅ Findings severity filtering is case-insensitive, so SOC tiles open the rows
  they count; the SIEM export severity filter no longer uppercases (OBS-07).
- ✅ New assessments list every registry framework instead of ten hard-coded ids
  (OBS-10); users can be created with a local password (OBS-16).
- ✅ The Settings notification section talks to a real endpoint: flat preferences
  in `Tenant.settings_json`, SMTP password stored, masked on read, preserved when
  the mask is echoed, and the form seeds from the server (OBS-18 first half).
- ✅ Delegated tenant access populates: `/tenants` is capped at `page_size=100` and
  `/users` returns a bare array, both now normalised (OBS-19).
- ✅ Sonar `typescript:S6582` in `ZeroTrustPlatformPage.tsx` fixed with an optional
  chain.
- Checks: `pytest -q` 725 passed (was 714), `ruff check`/`ruff format --check`,
  `mypy unimonitor/`, `eslint --max-warnings 0`, `tsc --noEmit`, `npm run build`.

Still open from the register: OBS-03 (per-platform framework coverage), OBS-04
(automatic posture inventory), OBS-05 (Zero Trust run/score disagreement), OBS-08
(per-provider audit), OBS-11 (manual assessment failure — needs the failed run's
`error_message`), OBS-12 (requirement catalogue and level selection for every
framework), OBS-13 (tenant add/suspend/delete UI), OBS-14/15 (Graph 502 handling),
OBS-17 (connector credentials in the vault) and OBS-18 second half (send mail with
the registered Entra app).

## 2026-11-21 — posture engines, control trends, scorecard, branding

- ✅ Posture analysis is now a real package (`unimonitor/posture/`): CIS packs for
  AWS/Azure/GCP/M365/Google Workspace, plus DSPM, CIEM, AI-SPM, Kubernetes and
  identity attack-path engines over one normalised inventory. Every engine is a
  pure function; a resource missing from the snapshot is `not_applicable`, never a
  pass. `GET /api/v1/posture/analysis` reads `UNIMONITOR_POSTURE_SNAPSHOT`,
  `POST /api/v1/posture/analyze` analyses a posted inventory (8 MiB cap, analyst
  role), and `/posture` shows the results.
- ✅ Control-level trends: every assessment run appends immutable
  `control_snapshots` rows (migration 007); `GET /api/v1/grc/controls/trend` and
  `/controls/{id}/trend` return the series, transitions and improvement flag.
  One data point is reported as `insufficient_history`, never as a trend.
  Rows are pruned in the same transaction every run
  (`CONTROL_SNAPSHOT_RETENTION_DAYS`, default 90, `0` keeps history), scoped to
  the running tenant so one policy cannot delete another tenant's series.
- ✅ Scorecard export: `/api/v1/reports/scorecard?fmt=csv|xlsx|pdf` builds the file
  synchronously from stored findings and framework coverage; the Reports page
  exposes the three formats.
- ✅ Per-tenant branding (portal name, accent colour, logo, support address in
  `Tenant.settings_json`, validated to https/relative URLs) applied by the Layout,
  and delegated tenant access (`tenant_access`, migration 008) with grant/revoke
  endpoints and an admin panel. `GET /tenants/{id}/summary` is the guarded consumer.
- ✅ Tests: posture engines, exporters, posture API, control trends and branding
  (26 new tests).
- ✅ Sonar backlog: `S8410` Annotated dependency style and `S8415` documented
  responses are cleared across `unimonitor/api`; `S107` on `list_findings` uses a
  Pydantic filter model; the test-only `S5778`/`S9073` findings are fixed; the
  nested JSX ternaries on the findings/framework/users/reports/assessments pages
  are flat conditional blocks; and the `S3776` complexity findings are refactored
  for the posture analysers, GRC engine and trends, auditor portal, control
  loader, tenant rollup, zero-trust coverage, ticketing and the SPA middleware.
- Remaining Sonar items: the complexity of `graph/collectors/cloud_providers.py`
  (AWS and GCP snapshots), the PDF and DOCX generators, `onboarding/service.py`,
  the two largest page components (`AuditPage`, `SetupPage`), and the deprecated
  recharts `Cell`. `extended.py` is refactored (Intune baselines, detected apps and
  the Secure Score sections each have their own helper).

## 2026-11-21 — installer build + SonarQube cleanup

- ✅ Installer build is now one command: `scripts/build-windows-installer.cmd`
  (PowerShell script beside it) creates the venv, installs PyInstaller and the
  production extras, builds the frontend, regenerates the icon, freezes the app,
  fetches NSSM with a printed SHA-256, installs NSIS via winget/choco when missing,
  runs `makensis`, smoke-tests `UniMonitor.exe --help` and writes the portable zip.
  INSTALL.md §9 now leads with the zero-setup GitHub Actions path and this command;
  the manual steps are kept as debugging reference.
- ✅ SonarQube pass: removed 85 redundant `response_model=` parameters, split the SIEM
  transport chain into per-provider request builders (one JSON content-type constant),
  removed duplicated literals (frameworks, platform tests, users, alembic), fixed the
  `async`/unused-param pair in `collect_copilot_studio`, and cleared the frontend
  floating promises, nested ternaries, sort comparators, read-only props and
  `[object Object]` stringification reported in the CSV.
- Remaining Sonar items are the large refactors (`S8410` Annotated dependencies,
  `S8415` documented `responses=`, remaining `S3776` cognitive-complexity functions
  and the remaining nested ternaries in ZeroTrust/Settings pages). They are cosmetic
  or structural, not defects.

# NEXT_ACTIONS.md

Project: UnifiedMonitor
Repository: https://github.com/rajtechlead/UnifiedMonitor
Last Updated: 2026-11-20 UTC

## Suggested roadmap — frameworks and features (2026-11-20)

Derived from what comparable CSPM/GRC products support and from gaps visible in
UniMonitor's own evidence-coverage report. Ordered by leverage, not effort.

### Frameworks added (2026-11-20)

All of the frameworks below are registered and mapped. Frameworks marked
*derived* reuse an existing mapping until an official crosswalk is imported;
their page and API carry that note. CPCSC is mapped at family level (17 families,
98 ITSP.10.171 requirements, 13 Level 1 criteria) because the official requirement
text is not redistributable.

| Framework | Why | Note |
|---|---|---|
| NIS2 (EU 2022/2555) | Mandatory for EU essential/important entities; 24h/72h reporting clock | No controls yet; 10 Article 21 measures map well to existing policies |
| DORA (EU 2025) | Financial entities and their ICT providers; third-party risk | Needs vendor/ICT register plus resilience testing evidence |
| FedRAMP Low/Moderate/High | US federal baseline, built on NIST 800-53 which is already mapped | Mostly a crosswalk once 800-53 references are validated |
| NIST 800-171 r3 | DoD supply chain; CMMC Level 2 basis | CMMC 2.0 is present; 800-171 adds the parent requirement set |
| CSA CCM v4 + STAR | Cloud-specific control matrix used in vendor questionnaires | Crosswalk source for most other frameworks |
| CISA SCuBA (M365 + Workspace) | Free, prescriptive cloud baselines auditors increasingly request | Fits the existing Microsoft/Workspace collectors almost directly |
| CIS Foundations Benchmarks (AWS/Azure/GCP) | The de-facto CSPM rule library; far deeper than current cloud controls | Needs benchmark-rule evaluation, not just the CIS Controls framework |
| ISO 27017 / 27018 / 27701 | Cloud security, cloud privacy, privacy extension | Extends the existing ISO 27001 mapping cheaply |
| NIST AI RMF / ISO 42001 / EU AI Act | AI governance demand; ISO 42001 has 8 controls today | Copilot controls already exist as a starting point |
| TISAX, Essential Eight, Cyber Essentials, CCPA/CPRA, CJIS, SWIFT CSP | Regional/sector requirement sets | Add when a target customer needs them |

Shipped: CPCSC, NIST 800-171 r3, FedRAMP Low/Moderate/High, NIS2, DORA,
CSA CCM v4, CISA SCuBA M365 + Workspace, ISO 27017/27018/27701, NIST AI RMF,
EU AI Act, Essential Eight, Cyber Essentials, CCPA/CPRA, CJIS, SWIFT CSP, TISAX.
The framework registry is now the single source of truth (`SUPPORTED_FRAMEWORKS`
is generated from `FRAMEWORKS`), and a regression test asserts every framework
resolves to at least one control.

CPCSC is now mapped at **requirement level**: all 98 ITSP.10.171 identifiers and
titles live in `grc/framework_mappings.py` (`CPCSC_REQUIREMENTS`, 13 marked
Level 1), each exposing the evidence controls of its family through
`GET /grc/frameworks/cpcsc/requirements`. Official requirement text is not
redistributed, so controls are selected at family level.

Still pending for a later round: CIS Foundations benchmark *rule packs* (the
framework exists; the per-rule evaluators do not).

### Features — status 2026-11-20

Shipped this round:

- **Exception lifecycle** — time-boxed risk acceptances (`expires_in_days`), an
  expiry timestamp on the finding, and automatic release on read; migration `005`.
- **Posture snapshot editor API** — admin `GET/PUT /settings/posture-snapshot`
  writes the configured `UNIMONITOR_POSTURE_SNAPSHOT` atomically (UI editor still
  to be added on the Settings page).
- **SIEM export** — `GET /findings/export/siem` in CEF or JSON-lines, open
  findings only, tenant/severity filters.
- **Read-only auditor role** — already enforced by `require_compliance_access`;
  the dedicated evidence portal is still pending.

Still to build:

1. **CIS benchmark rule packs** per platform (AWS/Azure/GCP/M365/Workspace) with
   pass/fail per rule and per-benchmark scores — the largest gap versus commercial CSPM.
2. **DSPM / data classification**: discover sensitive data stores (S3/GCS/Drive/SharePoint),
   label coverage, public-exposure paths; ties directly to the Data pillar already scored.
3. **CIEM**: effective-permissions analysis (AWS IAM Access Analyzer findings, GCP IAM
   recommender, Entra role assignments) with unused-permission and privilege-escalation paths.
4. **AI-SPM**: inventory Copilot/Vertex/Azure OpenAI deployments, prompt/data exposure and
   agent permissions; extends the existing `copilot_*` services.
5. **Kubernetes and container posture**: CIS EKS/AKS/GKE benchmarks, admission control,
   image signing/attestation — the catalogues already flag Binary Authorization as a gap.
6. **Identity risk and attack paths**: join findings into graph paths (public SG → instance role →
   sensitive bucket) instead of flat per-control lists.
7. ~~Continuous evidence and auditor portal~~ — done: `GET /grc/frameworks/{id}/evidence-package`
   returns a hashed, self-contained package (control state, findings, evidence) and the
   Auditor Portal page renders CPCSC requirement status for auditor/compliance roles.
8. ~~Exception workflow~~ — done (expiry + auto-release). Owner/justification fields exist
   as reason; a dedicated owner field is still a nice-to-have.
9. ~~Posture snapshot editor~~ — done: the Settings page edits the snapshot with JSON
   validation and only offers saving when a path is configured.
10. ~~Ticketing and SIEM integrations~~ — done: idempotent Jira/ServiceNow/generic-webhook
    ticket sync (migration `006`) and push connectors for Datadog, Splunk HEC, Elastic,
    Microsoft Sentinel, Sumo Logic, Chronicle, Wazuh, a generic webhook and CEF syslog,
    each testable and triggerable from the Settings page.
11. ~~CIS/benchmark trend and SLA reporting~~ — remediation half done: `/dashboard/trends`
    returns mean/median/p90 time to remediate per severity and open SLA breaches, shown on
    the CISO board. Control-level trend series and a scorecard export file remain open.
12. ~~MSP multi-tenant rollup~~ — done: `/tenants/rollup` returns one comparable row per
    active tenant (latest scores, open exposure, weakest framework) plus managed totals, and
    the Managed Tenants page renders it. Per-tenant branding and delegated access remain open.

## Phase 10 — Repository merge (2026-11-18)

| Task | Status | Notes |
|---|---|---|
| P10-001 Comparison document | ✅ Done | `Comparison.MD` (reference repos vs UniMonitor capability matrix) |
| P10-002 Gap analysis | ✅ Done | `gap_analysis.md` (GAP-01…GAP-20, dispositions, residual risks) |
| P10-003 Microsoft sign-in on login page | ✅ Done | wrong route, unread token fragment, missing redirect URI; `/auth/sso` gate |
| P10-004 HTML report | ✅ Done | `reporting/html_generator.py`; worker no longer awaits a sync generator |
| P10-005 Zero Trust pillar view | ✅ Done | `grc/pillars.py`, `GET /dashboard/zero-trust`, `ZeroTrustPage` |
| P10-006 Finding triage workflow | ✅ Done | ack/snooze/assign/resolve, migration `002`, audit entry |
| P10-007 ROI priority queue | ✅ Done | `GET /findings/priority`, `impact`/`effort` control keys |
| P10-008 Findings page contract fix | ✅ Done | real params/fields, pagination, triage column |
| P10-009 Entity timeline | ✅ Done | `GET /findings/{id}/timeline` |
| P10-010 Alert policy engine | ✅ Done | `AlertPolicy`/`Alert`, six metrics, five templates, beat evaluation, Alert Center page |
| P10-011 Licence posture / service health | ✅ Done | `/monitoring/licensing`, `/monitoring/service-health`, two pages; `ServiceHealth.Read.All` optional |
| P10-012 Hash-chained audit | ✅ Done | migration 003, `core/audit.py`, verify endpoint + Audit page badge |
| P10-013 Global search (Ctrl+K) | ✅ Done | `/search`, pages/findings/alerts/controls palette |
| P10-014 Scheduled collection | ✅ Done | `collect_all_tenants` beat task, interval config, default assessment |
| P10-015 Manual collection UI | ✅ Done | Data Collection page: Collect now + per-collector Run |
| P10-016 Saved filter presets | ⬜ Deferred | UI sugar; global search covers lookup |
| P10-017 Zero Trust Assessment page | ✅ Done | Import Microsoft report, pillar scores, filters, remediation; `/zero-trust/assessment` |
| P10-018 Multi-cloud ZT coverage | ✅ Done | `/zerotrust/run` scores AWS/GCP/Workspace controls with remediation |
| P10-019 Cloud remediation text | ✅ Done | `remediation` blocks on all 22 cloud controls, parsed by the loader |
| P10-020 PowerShell runner | ✅ Done | `scripts/zerotrust/Invoke-UniMonitorZeroTrust.ps1`, bundled, parsed in CI |
| P10-021 Certificate rotation duration | ✅ Done | Rotate dialog takes 1–1095 days, default 365 |
| P10-022 Zero Trust run retention | ✅ Done | `store_run` prunes to the newest 5 runs per tenant/platform (checks deleted too) |
| P10-023 Executive ZT scores | ✅ Done | `/dashboard/executive` returns `zero_trust`; board shows the latest score per platform |
| P10-024 Installer bundle check | ✅ Done | CI checks `_internal/scripts/…` (PyInstaller 6 puts datas there) |
| P10-025 In-process collection | ✅ Done | No Celery/Redis: API runs the task, scheduler replaces beat |
| P10-026 Security dashboard demo data | ✅ Done | Real severity counts; collector list reads the API shape |
| P10-027 Entra certificate on create | ✅ Done | `keyCredentials` at creation avoids the 403 `addKey` |
| P10-028 SonarQube review pass | ✅ Done | Bugs, criticals and complexity/duplication; style rules deferred |

## Priority Execution Queue

Phase 1–4 ✅ COMPLETE
Phase 5 — Packaging ✅ (Linux) / ⬜ (Windows)
Phase 6 — Production Release 🟡
Phase 7 — Requirement Completion 🟡 (opened 2026-11-16)

## Phase 7 — Requirement Completion

| Task | Status | Notes |
|---|---|---|
| P7-001 Risk dashboard view | ✅ Done | `frontend/src/pages/RiskDashboard.tsx`, heatmap + critical risks |
| P7-002 SOC dashboard view | ✅ Done | `frontend/src/pages/SocDashboard.tsx` |
| P7-003 Audit dashboard view | ✅ Done | `frontend/src/pages/AuditPage.tsx` + `GET /dashboard/audit` |
| P7-004 Executive/Compliance contract fix | ✅ Done | pages were showing demo values instead of API data |
| P7-005 Control library depth | ✅ Done | 158 controls added; extended collectors now feed them (snapshot path for non-Graph areas) |

## Phase 9 — First-Run Onboarding

| Task | Status | Notes |
|---|---|---|
| P9-001 Setup wizard (platform selection, min 1) | ✅ Done | `/setup` + `/api/v1/onboarding`, launched by the installer |
| P9-002 Microsoft 365 app registration automation | ✅ Done | device-code sign-in → Graph creates app, roles, consent, credential |
| P9-003 Connect more platforms later | ✅ Done | Settings → Platform connections, same connector component |
| P9-004 AWS/GCP/Workspace credential validation | ✅ Done | validated against the live API before saving |
| P9-005 Automated M365 consent against a real tenant | ⬜ Open | needs a live Global Administrator; the Graph calls are covered by mocked tests only |
| P9-006 Multi-tenant (MSP) client onboarding | ⬜ Open | one connection set per install today |
| P9-007 Certificate credential as the M365 default | ✅ Done | generated certificate uploaded via `addKey`; validity 1–1095 days, 365 default |
| P9-008 Manual certificate-upload fallback | ✅ Done | files to save + portal steps + `/microsoft/verify`; pending uploads do not count as configured |
| P9-009 Certificate fallback against a real tenant | ⬜ Open | `addKey` is only exercised against mocked Graph responses |
| P9-010 AWS IAM role (SSO) connection | ✅ Done | `validate_aws_role` / `assume_role_credentials`; collector assumes the role |
| P9-011 One shared service account for the Google platforms | ✅ Done | `POST /connections/google-service-account` connects GCP + Workspace with one key |
| P9-012 Sign-in client Entra preauthorizes (`AADSTS65002`) | ✅ Done | Graph PowerShell client + `ENTRA_SIGNIN_CLIENT_ID` override, actionable error text |
| P9-013 Shared Google service account in Settings | ✅ Done | same connector offered by the Settings picker, not only the wizard |
| P9-014 Certificate thumbprint/expiry/rotation in Settings | ✅ Done | `POST /microsoft/certificate/rotate`; warns within 30 days, retires the old key; the wizard grants `Application.ReadWrite.OwnedBy` and makes the app an owner of itself so the runtime may rotate |
| P9-015 SonarQube blockers and criticals | 🟡 Partial | notification dispatcher kwargs, CLI smoke-test call, CORS order, Fernet salt, k8s hardening fixed; the large cognitive-complexity refactors (report generators, notifications API) and the FastAPI `Annotated`/`response_model` style batch remain |
| P9-016 Sign-in and rotation against a live tenant | ⬜ Open | `addKey`/`removeKey` and the device-code consent are covered by mocked Graph only |

## Phase 8 — Multi-Cloud (AWS, Google Cloud, Google Workspace)

| Task | Status | Notes |
|---|---|---|
| P8-001 AWS collector + controls | ✅ Done | 8 controls; boto3 default credential chain |
| P8-002 GCP collector + controls | ✅ Done | 8 controls; REST + `GCP_ACCESS_TOKEN` |
| P8-003 Google Workspace collector + controls | ✅ Done | 6 controls; Admin SDK REST + `GOOGLE_ACCESS_TOKEN` |
| P8-004 Live credential validation | ⬜ Open | no AWS/GCP/Workspace accounts in the agent workspace |
| P8-005 Google token refresh | ✅ Done | setup stores the service-account key; `onboarding/google_auth.py` mints tokens on demand (Workspace uses domain-wide delegation) |
| P8-006 Provider controls in the UI | ✅ Done | `/clouds` aggregate + `/clouds/:providerId` detail pages, Clouds nav entry |
| P8-007 Provider segmentation in reports | ✅ Done | aggregate summary retained + colour-coded per-cloud sections in PDF and DOCX |
| P8-008 MSI package variant | ⬜ Open | NSIS `.exe` ships today; an MSI (WiX) is optional if group policy deployment needs it |
| P8-009 CISO dashboard | ✅ Done | `/dashboard/ciso` + `/ciso` page: exposure by cloud, top risks, weakest frameworks, trend |
| P7-006 Coverage re-measure | ⬜ Open | last 62% at `79dfb98` |
| P7-007 Frontend majors remaining | ⬜ Open | `react` 18→19, `@vitejs/plugin-react` 4→6 |
| P7-008 Jose/ecdsa CVE decision | ⬜ Open | accept-and-record or migrate to `pyjwt` |

## Phase 6 — Production Release 🟡

| Task | Status | Deliverable |
|---|---|---|
| P6-001 Installation guide | ✅ Done | `docs/INSTALLATION_GUIDE.md` |
| P6-002 Operations guide | ✅ Done | `docs/OPERATIONS_GUIDE.md` |
| P6-003 Troubleshooting guide | ✅ Done | `docs/TROUBLESHOOTING_GUIDE.md` |
| P6-004 Production readiness | ✅ Done | `docs/PRODUCTION_READINESS.md` |
| P6-005 Release Candidate | 🟡 Blocked | tag absent everywhere; needs tag-push permission |

## Phase 5 — Packaging ✅ (Linux) / ⬜ (Windows)

| Task | Status | Notes |
|---|---|---|
| P5-001 Docker build | ✅ CI green | local daemon unavailable |
| P5-002 PyInstaller build | ✅ Linux | 222 MB bundle, validated 2026-11-13 |
| P5-003 NSIS installer | ⬜ Windows only | `deploy/windows/install.nsi` |
| P5-004 Fresh Windows install | ⬜ Windows only | |
| P5-005 Upgrade validation | ⬜ Windows only | |
| P5-006 Rollback validation | ⬜ Windows only | |

## Immediate Next Steps

### Step 1 — Push the release tag

```bash
git tag -a v1.0.0-rc1 -m "UniMonitor v1.0.0-rc1"
git push origin v1.0.0-rc1
```

If 403 persists, create the release from the GitHub UI (Tags → Create release). No tag currently
exists in the repository, so it must be created, not just pushed.

### Step 2 — Windows validation block (requires Windows Server 2019+)

```powershell
.\UniMonitor-Setup.exe
Get-Service UniMonitorSvc
curl http://localhost:8000/health
.\UniMonitor-Setup-new.exe   # upgrade path
.\UniMonitor-Setup-old.exe   # rollback path
```

### Step 3 — Control library expansion ✅ completed 2026-11-16 (record of scope)

Add control YAML for the requirement areas with no coverage today. Follow the existing schema in
`controls/identity/mfa_controls.yaml` (id, title, description, severity, category, service,
compliance_mapping). Areas and indicative ids:

- `controls/intune/security_baselines.yaml` — CTRL-INT-xxx
- `controls/intune/application_inventory.yaml` — CTRL-APP-xxx
- `controls/defender/office_protection.yaml`, `identity_protection.yaml`, `cloud_apps.yaml`
- `controls/purview/insider_risk.yaml`, `ediscovery.yaml`
- `controls/copilot/studio_governance.yaml`
- extend `controls/identity/privileged_access.yaml` (PIM: eligible assignments, approval flow,
  access reviews, activation MFA)

### Step 4 — Coverage re-measurement

```bash
pytest --cov=unimonitor --cov-report=term-missing
```

Update `BUILD_STATUS.md` with the measured figure; do not carry forward 62% unverified.

### Step 5 — Remaining frontend majors (lowest risk first)

1. `@vitejs/plugin-react` 4 → 6 (`vite.config.ts`)
2. `react` + `react-dom` 18 → 19 (major — re-run build, lint, Playwright smoke)

After each: `npm run lint`, `npm run build`, then commit. Revert + log in GAP_REGISTER on failure.

## Mandatory Commit Points

- Every successful dependency migration
- Every control-library batch
- Every tracker sync
- At 95% context usage

## Stop Condition

At ~95% context: update all four trackers, commit, push, stop.

## 2026-11-19 — installer + reference merge

- P10-029 Run GitHub Actions → Windows Installer with version 1.1.0 (needs a Windows
  runner; the Linux build here validates the spec but cannot produce the NSIS exe).
- ✅ P10-030 Ported all 364 Microsoft Zero Trust PowerShell tests into the Python
  catalogue (`unimonitor/zerotrust/microsoft_tests.py`, generated by
  `scripts/import_zt_tests.py`); 72 controls now declare `ms_zt_tests` and score those
  tests from their findings, the remaining tests report `not_run` until evidence exists.
  Remaining: add `ms_zt_tests` mappings for the controls still unmapped (86); most have
  no upstream counterpart (Exchange/Teams/Copilot/Purview eDiscovery/Azure resource
  hardening), so only genuine subject matches belong there.
- P10-031 Continue the Vigil365 and m365_sheppard merge from `reference/`: entity
  investigation, activity/anomaly policies, licence posture per cloud.
- P10-032 Refresh the clones with `scripts/update-reference-repos.sh` before each batch.
