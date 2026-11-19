# Reference repositories

Three public projects are cloned read-only into `reference/` (git-ignored) while the
feature merge is in progress. They are inputs for porting work, not part of the build.

| Clone | Upstream | What we take from it |
|-------|----------|----------------------|
| `reference/vigil365` | https://github.com/sameerk27/vigil365 | Setup/sign-in cycle, page coverage (identity, devices, email, incidents, compliance, licence posture, Copilot, Power Platform, alert center, service health, conditional access, sign-in locations), alert policy engine, notifications, reports |
| `reference/m365_sheppard` | https://github.com/mstanton/m365_sheppard | Python collector framework, control definitions, recipes and reporting used to shape the multi-cloud collector catalogue |
| `reference/zerotrustassessment` | https://github.com/microsoft/zerotrustassessment | Microsoft's Zero Trust PowerShell test catalogue, classes and report format that the Python engine must cover |

## Refresh

```bash
scripts/update-reference-repos.sh
```

The script clones any missing repository as a shallow clone and fast-forwards the
existing ones, so a mid-merge checkout never has to be thrown away. Delete
`reference/` and rerun it for a clean copy.

## Porting rules

- Import behaviour, do not copy files: licence headers and stacks differ.
- Every Microsoft-only feature is implemented behind the platform abstraction so
  AWS, Google Cloud and Google Workspace get the same surface.
- The Python Zero Trust engine (`/api/v1/zerotrust/run`, `run-all`) is the default.
  The PowerShell runner and `/api/v1/zerotrust/import` stay available as the manual
  fallback and can run alongside it.
