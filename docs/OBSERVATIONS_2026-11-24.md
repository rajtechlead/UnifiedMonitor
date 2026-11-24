# Observations — 2026-11-24

Tracker for the owner's third review round. Each row records the root cause found in
the code, the change made, and how far it could be verified without a live tenant.

Legend: ✅ implemented and covered by automated checks · 🟡 implemented, needs a live
tenant/host to confirm · ⛔ not done (reason stated).

## Items

| # | Observation | Status | Root cause and change |
|---|---|---|---|
| 1 | Microsoft sign-in still not working | 🟡 | Delegated sign-in asked for `Organization.Read.All` as well as `User.Read`, which turns every login into an admin-consent request; the delegated scope list is now `openid profile email offline_access User.Read`. The OAuth callback returns `#access_token=…` on the frontend URL and nothing read that fragment, so the browser landed on `/login` signed out. Added `authSession.ts` + `SsoGate` in `App.tsx` (stores the token, reads `/auth/me`, strips the fragment). The redirect URI was also hard-coded to `http://localhost:8000/...`; `/auth/sso`, `/auth/login` and the callback now use the configured value or derive it from the request origin, so the app tells Entra the URL the browser is actually using. Login page shows the exact callback to register. Needs a real Entra app to confirm end to end. |
| 2 | Re-login as admin becomes standard user | ✅ | `POST /auth/login` returned only tokens while the SPA stored `res.data.user` (undefined), so the persisted profile lost the role. `TokenResponse` now carries the profile (login and refresh); the SPA has an `/auth/me` fallback. Regression test logs in twice and asserts the admin role both times. |
| 3 | Zero Trust report link gives AUTHENTICATION_FAILED and results are all not run | 🟡 | The list opened the authenticated report endpoint with a plain `<a href>` (no bearer header) — now fetched as a blob and opened from an object URL. Microsoft's module has **no** client-secret app auth (`-UseAppAuth` did not exist), so the old script always failed and the Python catalogue produced 450 rows with no evidence. `Invoke-ZtAppOnly.ps1` now imports the vaulted certificate to `Cert:\CurrentUser\My` and calls `Connect-ZtAssessment -ClientId -TenantId -Certificate <thumbprint>`, removing it afterwards; the runner writes a 0600 PFX to a private temp dir, passes path+password through the environment (never argv), and records the failure reason. Python remains the fallback. Needs a Windows host + certificate app to execute the module. |
| 4 | Email through the Entra app "UniMonitor" (Mail.Send) | 🟡 | Only SMTP existed. `NotificationDispatcher` now falls back to Graph `POST /users/{sender}/sendMail` using the connected app and its certificate/secret; sender = configured From, else the connection account. SMTP wins when enabled; Graph is the built-in default otherwise. Admin consent for `Mail.Send` is still an Entra-portal action. Unit-tested with mocked Graph. |
| 5 | Risk heatmap and Open Risks empty | ✅ | `FindingRepository.get_risk_heatmap` returned `finding_ids: []` for every cell and the dashboard keeps only cells whose ids are visible, so the heatmap was always empty. It now groups real finding ids. Test asserts a connected finding appears in a cell with its id. |
| 6 | SOC incident trend empty | ✅ | The trend was built only from `Alert` rows, which a fresh install never has. It now counts findings first seen per day (plus alerts), with critical/high columns. Test asserts a finding produces a 7-day trend. |
| 7 | Microsoft cloud audit "could not be read: ." | ✅ | Two causes: a 10 s per-source timeout was too short for MSAL + Graph and `str(TimeoutError())` is empty, and Graph errors lost their detail. Timeout is 30 s, timeouts report "timed out after 30s", empty errors fall back to the exception class, and a malformed payload is a clear error. `AuditLog.Read.All` consent remains an admin step. |
| 8 | Scorecard PDF fails | ✅ | Verified end to end through the real route with a stored finding: `GET /reports/scorecard?fmt=pdf` returns `200`, `application/pdf` and a `%PDF-` body; the format literal rejects anything else with 422. Covered by two new API tests. |
| 9 | Generated PDF is corrupt | ✅ | The no-ReportLab fallback wrote a **.txt** file but stored it under the `pdf` key and served it as `application/pdf`. It now writes a structurally valid minimal PDF, and the PyInstaller spec collects `reportlab`/`openpyxl` submodules and data so the frozen build has the real generator. |
| 10 | Report shows AWS/GCP/Workspace data although they are not connected | ✅ | Report generation used every finding of the run. `_load_report_context` now filters findings to the tenant's connected providers, so a disconnected platform cannot appear as evidence. |
| 11 | Reports table needs tenant/assessment columns and real requester names | ✅ | API now returns `tenant_name`, `assessment_name`, `requested_by_name` (joined from `Tenant`, `Assessment`, `AppUser`); the table shows Status, Type, Tenant ID, Tenant, Assessment, Formats, Requested By, Created, Downloads. |
| 12 | Service health needs links, advisories and more coverage | ✅ | Health overviews are rendered per service with open-advisory counts and an admin-center link; advisories carry id, feature/feature group, origin, start/end/last-modified, impact details, latest update post, and a link; the page shows operational/degraded/advisory severity coverage plus the Microsoft 365 portal backlink. |
| 13 | Managed tenants: external links for clients | ✅ | `GET/PUT /tenants/{id}/settings` accept `external_links: [{label,url}]`, stored in the tenant settings document and validated with the public-URL rule; the client page has an add/remove editor so an MSP can publish a dedicated portal or sub-tenant link. |
| 14 | `uni.csv` Sonar findings and duplication | 🟡 | Fixed: nested ternaries and ambiguous JSX spacing, read-only props, empty fixture parentheses, missing HTTPException `responses` docs, duplicated `ISO/IEC`/`European Union`/FEDRAMP literals, `_clean` cognitive complexity, and unused Okta connector code. Duplication between `BrandingPanel`/`TenantSettingsPage` and the remaining complexity refactors were not chased; they are cosmetic and carry refactor risk. |
| — | Okta connectable without a collector | ✅ | Okta is now sign-in only (OIDC). It was removed from the onboarding platform picker, `PLATFORM_FIELDS`, `IDENTITY_PLATFORMS`, the `connect_platform` branch and `validate_okta`, so no picker entry can be connected without a collector. |
| — | SIEM/ticketing URLs accept internal/metadata hosts | ✅ | `integrations.credentials` now runs every URL field through the shared `validate_base_url`; the validator itself was hardened to reject loopback, private and reserved ranges (a custom AI endpoint may still opt into its documented loopback gateway). Tests cover metadata names/IPs, loopback, RFC1918 and a public accept. |

## Verification

- Full backend suite **964 passed**; `ruff check`, `ruff format --check`, `mypy unimonitor/` clean.
- Frontend `tsc --noEmit`, `eslint --max-warnings 0`, `npm run build`; the build is
  staged into `unimonitor/static` and `scripts/verify_bundled_ui.py` confirms the SPA
  and API routes both answer from the bundled app.
- Scorecard and minimal PDF generators checked for a valid `%PDF` header.

## Limits

- No live Entra tenant, Windows host, PowerShell 7 or tenant certificate in this
  environment: items 1, 3, 4 and the Graph paths of 7 were exercised against fakes
  only. The upstream PowerShell module's exact certificate parameter behaviour and
  the `Mail.Send` consent must be confirmed on the owner's install.
- Reports stored before this change still contain the old, unfiltered findings;
  regenerate them to apply item 10.
