# AI remediation and single sign-on

## AI remediation

### What was broken

`POST /api/v1/findings/{id}/remediate` imported `generate_ai_remediation_task` from
`unimonitor.worker.tasks`, a name that did not exist, and `AIRemediationEngine` was
never called from anywhere. Every request therefore ended in `503 "Failed to dispatch
AI remediation task"`, and no guidance was ever produced by any model.

### How it works now

```
finding row ──► anonymise() ──► provider chain ──► JSON guidance ──► finding.ai_remediation
                 (6 fields)      (failover)                          (stored, shown in the UI)
```

* `unimonitor/ai/anonymize.py` builds the payload from an **allowlist**: control id,
  framework, category, severity, state, and the catalogue's title/description. The
  tenant row, finding id, evidence, policy and resource names, assignee and collector
  output are dropped by construction. Every string still passes `scrub()`, which
  replaces emails, UPNs, GUIDs, IPv4/IPv6, URLs, paths, domains and long numeric
  identifiers before anything leaves the process.
* `unimonitor/ai/providers.py` describes each provider and its model catalogue.
  Enabled providers, in order:

  | Provider | Config | Free tier |
  |---|---|---|
  | `freebuff` | `FREEBUFF_API_KEY` (falls back to `OPENAI_API_KEY`), `FREEBUFF_BASE_URL`, `FREEBUFF_MODEL` | yes |
  | `groq` | `GROQ_API_KEY`, `GROQ_MODEL` | yes |
  | `openai` | `OPENAI_API_KEY`, `OPENAI_MODEL` | no |
  | `anthropic` | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | no |
  | `azure_openai` | existing `AZURE_OPENAI_*` settings | no |

* `unimonitor/ai/service.py` tries them in the order set by `AI_PROVIDER_ORDER`
  (default `freebuff,groq,openai,anthropic,azure_openai`). A quota, rate-limit, auth or
  availability failure (402/403/404/408/409/425/429/5xx or a transport error) moves to
  the next provider; only an unparseable answer from every provider ends in the
  rule-based fallback. The provider that answered is recorded as the guidance source.
* `GET /api/v1/ai/status` reports which providers are configured (never their keys);
  `GET /api/v1/ai/models` asks each OpenAI-compatible provider for its live model list
  and falls back to the known catalogue when offline.

### Operating notes

* `AI_ENABLED=true` is still required; without it the rule-based guidance is used.
* Freebuff is OpenAI-compatible, so its whole catalogue is available through
  `GET /api/v1/ai/models`; `FREEBUFF_MODEL` pins one model, otherwise the first known
  model is used.
* The prompt is generated server-side only. The browser never talks to a provider, and
  no provider key is returned by any endpoint.
* Prompts and answers are not logged; only the provider name, model and a failure
  reason are.

## Single sign-on

### What was broken

`UserRepository.upsert_from_entra` created accounts without `tenant_id`, but
`AppUser.tenant_id` is `NOT NULL`. Any first-time Microsoft sign-in therefore failed on
insert (or, worse in a tolerant database, produced an unowned account). Existing users
were unaffected, which is why it surfaced only for new joiners.

Now a new account is attached to the tenant whose `entra_tenant_id` matches the token's
`tid`; a single-active-tenant install falls back to that tenant. With several tenants
and no match the sign-in is refused with a 403 that tells the user to ask for an
invitation — it is never guessed.

### Providers

`GET /api/v1/auth/sso/providers` lists what the login page may offer, in
`SSO_PROVIDER_ORDER` (default `microsoft,google,okta`):

| Provider | Configuration | Callback to register |
|---|---|---|
| Microsoft | the Entra app created during setup (`ENTRA_CLIENT_ID` / `ENTRA_SIGNIN_CLIENT_ID`, `ENTRA_TENANT_ID`, optional secret) | `…/api/v1/auth/callback` (unchanged) |
| Google Workspace | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | `…/api/v1/auth/oidc/google/callback` |
| Okta | `OKTA_ISSUER` (e.g. `https://contoso.okta.com`), `OKTA_CLIENT_ID`, `OKTA_CLIENT_SECRET` | `…/api/v1/auth/oidc/okta/callback` |

Microsoft also appears in the generic list and can complete through
`/auth/oidc/microsoft/login`; the setup wizard's `/auth/login` flow is unchanged.

All providers converge on one `complete_sign_in()` helper, so token issuance, the
post-login redirect (fragment tokens, same-origin only) and account provisioning are
identical.

### Not verified here

No live Entra, Google Workspace or Okta tenant was available in this environment. The
request construction, code exchange, profile normalisation, tenant assignment, state
validation and error paths are covered by tests with mocked HTTP transports; a real
sign-in still needs one run against each provider's app registration.
