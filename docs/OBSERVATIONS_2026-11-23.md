# Owner observations — 2026-11-23

Working tracker for the twelve observations raised against the installed build.
Each item records the root cause found in this repository (or in the reference
projects `sameerk27/vigil365` and `microsoft/zerotrustassessment`), the change
made, and the verification that was actually possible without a live tenant.

Status keys: ✅ implemented and covered by a test · 🟡 implemented, needs a live
tenant/powerShell host to verify end to end · ⬜ not started.

## Reference material

- `sameerk27/vigil365` — sign-in, Graph service-health/licence endpoints and the
  `graph-permissions.json` list.
- `microsoft/zerotrustassessment` — the PowerShell Zero Trust assessment module
  and its HTML report output.

## 1. "Microsoft sign-in is not configured" 🟡

**Root cause.** The setup wizard stores the Entra app in `cloud_connections` and
the vault, not in `.env`. `/auth/sso` correctly reports the button as enabled
from the database, but `/auth/login` built its MSAL app from
`settings.ENTRA_CLIENT_ID`, which is only hydrated at startup. On a fresh
install the button therefore redirects with `error=sso_unavailable`.

**Change.** Sign-in resolves the app id, directory and credential from the saved
Microsoft connection (certificate or secret) through one helper shared with the
Graph client; `connect_microsoft` hydrates the settings singleton immediately.
The local administrator stays as the break-glass account and the setup step is
untouched.

## 2. Service health unavailable (502) ⬜

## 3. Licence posture unavailable (502) ⬜

## 4. Plug-n-play onboarding for every platform under Managed tenants ⬜

## 5. Per-tenant settings pages for the primary administrator ⬜

## 6. Plug-n-play platform connections in Settings ⬜

## 7. Plug-n-play SIEM and ticketing connectors ⬜

## 8. AI provider connection and auto-switchover sequence ⬜

## 9. Zero Trust assessment execution and HTML report ⬜

## 10. Audit page pulls platform audit logs, grouped by platform ⬜

## 11. Reports page run drop-down is empty after a successful run ⬜

## 12. Framework control/level coverage research ⬜
