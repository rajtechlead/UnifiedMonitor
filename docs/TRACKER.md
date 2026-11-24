# UniMonitor tracker

Project: UnifiedMonitor · Repository: https://github.com/rajtechlead/UnifiedMonitor
Last updated: 2026-11-24

This is the only work tracker. It replaces
`docs/OBSERVATIONS_2026-11-23.md`, `docs/OBSERVATIONS_2026-11-24.md`,
`docs/PLATFORM_OBSERVATIONS_2026-11-22.md`, `docs/PROJECT_GAP_ANALYSIS.md`,
`NEXT_ACTIONS.md` and `GAP_REGISTER.md`.

Legend: ✅ done and covered by automated checks · 🟡 done, needs a live tenant/host to
confirm · ⬜ open · ℹ️ decision recorded, no code change.

## Round 4 — owner review, 2026-11-24

| # | Item | Status | What changed |
|---|------|--------|--------------|
| 1 | Microsoft sign-in still fails with “Microsoft sign-in is not configured” | 🟡 | The authorization URL is now built directly from the connected app (`client_id`, directory, redirect URI, `openid profile email offline_access User.Read`), so a local MSAL/authority problem can no longer masquerade as “not configured”. A missing app redirects with a readable `reason` that the login page shows, and a failed token exchange returns to the login page instead of a JSON error. The setup wizard registers the callback of the origin it runs on (`callback_url(request)`), not just `http://localhost:8000/...`. Login page shows the exact redirect URI to add. |
| 2 | ZT Assessment: all ~450 Microsoft tests stay “not run” | 🟡 | The Microsoft run now prefers Microsoft's own module on any Windows host with a certificate (no checkbox needed), reads its `ZeroTrustAssessmentReport.json` and stores one row per executed test with its real status (Passed→pass, Failed→fail, Investigate→warn, Skipped→not applicable, Planned→not run). The script runs with `-NoBrowser -DisableTelemetry`, copies the JSON next to the report, and installs the module with `Install-PSResource` when available. Python remains the fallback. |
| 3 | Reports → Control scorecard → PDF: “Could not generate the scorecard” | ✅ | `to_pdf` falls back to the valid minimal PDF generator when ReportLab is missing or fails, so the button always returns a PDF. The page now shows the API's error detail instead of a generic line. Covered by a test that forces the ReportLab path to fail. |
| 4 | Audit → Cloud activity: “microsoft could not be read: .” despite `AuditLog.Read.All` | ✅ | Graph's 403 body is now surfaced (which permission/consent is missing) instead of a blank reason, and the Graph client drops a cached token and retries once when a permission was granted after the token was minted. Queries `directoryAudits` with an explicit order. Cloud activity already groups by platform and has a platform filter. |
| 5 | Group audit logs by platforms | ✅ | Cloud Activity renders one section per platform (Microsoft 365, AWS, GCP, Google Workspace) with counts, plus a platform filter, and lists platforms that could not be read separately. |
| 6 | Remove version tags completely | ✅ | The About page no longer requests or displays a version tag; no user-facing page shows one. Build/installer metadata keeps its version because Windows and the package metadata require it. |

## Round 3 — 2026-11-24 (previous)

Closed: local login returns the account profile (admin no longer reloads as a viewer);
SSO fragment hand-off; ZT report downloads use the bearer token; Zero Trust PowerShell
certificate app auth; Graph mail via `Mail.Send`; heatmap finding ids; SOC finding
trend; reports limited to connected providers with tenant/assessment/requester columns;
valid minimal PDF fallback and PyInstaller ReportLab/openpyxl collection; per-service
service-health coverage and advisories; per-tenant external links; connector URL
validation (loopback/private/metadata blocked) and Okta removed from the platform
picker because no collector exists.

## Open items

| ID | Item | Owner action / reason |
|----|------|-----------------------|
| O-01 | Live confirmation of Microsoft sign-in, Graph mail, cloud audit and the ZT module | Needs a real Entra tenant, a Windows host with PowerShell 7.6 and a certificate connection. All paths are covered by fakes only. |
| O-02 | ZT AWS/GCP/Workspace execution | Those catalogues score the platform's own controls from collected evidence. Microsoft is the only vendor with a 450-test executable module; the other three stay evidence-driven until per-test live API evaluators exist. |
| O-03 | Sonar cognitive-complexity refactors (`dashboard.py`, `monitoring.py`, `cloud_audit.py`, `tenants.py`, `onboarding/service.py`, `reports.py`) | Cosmetic; each needs behaviour-preserving extraction with tests. Tracked so they are not forgotten. |
| O-04 | `HTTPException` 403/503 `responses` docs on `monitoring._graph_json` | The helper is not a route; documenting it there would be noise. Revisit if the OpenAPI contract matters. |
| O-05 | Provider audit ingestion for AWS/GCP/Workspace beyond recent events | Current pages read recent events only; long-term retention is a separate design. |
| O-06 | Rebuild and reinstall the Windows package after this round | The tracked frontend sources changed; `unimonitor/static` is a build artifact (git-ignored) and is regenerated by `scripts/build-windows-installer.ps1`. |

## Sonar report attached to this review

Fixed: exception tests with one invocation (`tests/unit/test_connector_credentials.py`),
the malformed suppression comments in `zerotrust/runner.py`, the unused `session`
parameter in `onboarding/service.py`, and the duplicated save-button block between
`BrandingPanel` and `TenantSettingsPage` (now `components/SaveButton.tsx`).

Still open: the cognitive-complexity items in `dashboard.py` (SOC view),
`monitoring.py` (service health), `cloud_audit.py` (Microsoft reader), `tenants.py`
(test connection), `onboarding/service.py` (`connect_platform`) and `reports.py`
(run list), plus the `responses=` documentation on the non-route helper
`monitoring._graph_json`. These are structural clean-ups with real regression risk;
they are listed rather than silently half-done.

## Checks for this round

- Backend: **971 passed**; `ruff check` clean, `ruff format --check` 236 files,
  `mypy unimonitor` clean.
- Frontend: `tsc --noEmit`, `eslint --max-warnings 0`, `npm run build` clean; the build
  is staged into `unimonitor/static` and `scripts/verify_bundled_ui.py` passes.
- Packaging: PyInstaller spec still collects ReportLab/openpyxl; the runner script is
  parsed by the installer workflow tests.
