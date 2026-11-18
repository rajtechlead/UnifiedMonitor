# NEXT_ACTIONS.md

Project: UnifiedMonitor
Repository: https://github.com/rajtechlead/UnifiedMonitor
Last Updated: 2026-11-17 UTC

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
