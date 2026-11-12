# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x (latest) | ✅ Active security updates |
| < 1.0 | ❌ Not supported |

---

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Report security vulnerabilities privately by emailing **security@unimonitor.example.com** (replace with your actual security contact) or by using [GitHub's private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability).

Include:

- A description of the vulnerability
- Steps to reproduce
- Affected component(s) and version(s)
- Potential impact
- Any proposed fix (optional)

You will receive an acknowledgement within **48 hours** and a detailed response within **5 business days** indicating the next steps. We follow responsible disclosure — we will credit researchers who report valid vulnerabilities (unless they prefer to remain anonymous).

---

## Security Architecture

### Secret Management

UniMonitor enforces a zero-plaintext-secrets policy:

| Storage location | Allowed content |
|-----------------|-----------------|
| Source code | Secret _references_ only (e.g. `settings.ENTRA_CLIENT_SECRET`) |
| Configuration files | Key names; values come from secret provider at runtime |
| Database | Hashed passwords (`bcrypt`); never raw passwords or API keys |
| Docker manifests | Environment variable _names_; values injected at runtime |
| Kubernetes | `SecretProviderClass` references; values from Azure KV / AWS SM |
| Azure deployment | Azure Key Vault references via managed identity |
| AWS deployment | AWS Secrets Manager ARN references; no inline values |

**Secret providers** (configured via `SECRET_PROVIDER` env var):

- `azure_key_vault` — Azure Key Vault (production on Azure)
- `aws_secrets_manager` — AWS Secrets Manager (production on AWS)  
- `local_vault` — AES-256-GCM encrypted local file (development / Windows installer)
- `environment` — raw environment variables (CI / test environments only)

### Authentication & Authorisation

- **JWT** (python-jose, RS256 or HS256) with configurable expiry (default 60 min access, 7 day refresh)
- **JWT blacklist**: revoked tokens stored in Redis with TTL = remaining token lifetime
- **Entra ID SSO** (MSAL / OAuth 2.0 auth-code flow) for enterprise users
- **Local login** (bcrypt, minimum cost factor 12) for installer / dev environments
- **Role-based access control**: `admin > analyst > auditor > viewer`; enforced via `require_role()` FastAPI dependency

### Transport Security

- HTTPS enforced in production (Azure Container Apps / AWS ALB terminate TLS)
- HSTS header set by the application (`Strict-Transport-Security: max-age=63072000; includeSubDomains`)
- CORS restricted to configured origins (`UNIMONITOR_CORS_ORIGINS`)
- All database connections require TLS in production (`sslmode=require`)

### Input Validation

- All API inputs validated with Pydantic v2 (strict types, max lengths)
- SQL injection prevented by SQLAlchemy ORM — no raw SQL queries
- YAML control `evaluate:` blocks run in a restricted exec scope (no builtins, no imports)

### Dependency Management

- Python dependencies pinned in `requirements.txt` with hashes
- Frontend dependencies managed via `package-lock.json` / `pnpm-lock.yaml`
- Automated dependency updates via Dependabot (configured in `.github/dependabot.yml`)
- Run `make audit-python` and `make audit-frontend` to check for CVEs before deploying

---

## Threat Model

### In scope

- API authentication bypass
- Privilege escalation between roles
- Tenant data leakage (multi-tenant isolation)
- Secret exfiltration via API responses
- YAML control code injection
- SQL injection / ORM bypass
- JWT forgery or token reuse after logout
- SSRF via Microsoft Graph API client

### Out of scope

- Vulnerabilities in upstream libraries (report to the library maintainer)
- Attacks requiring physical access to the host
- Social engineering of administrators
- Denial-of-service attacks (rate limiting is a best-effort control)

---

## Security Hardening Checklist (Pre-Production)

Before going live, verify every item:

- [ ] `UNIMONITOR_ENV=production` set in all runtime environments
- [ ] `SECRET_PROVIDER` set to `azure_key_vault` or `aws_secrets_manager`
- [ ] `SECRET_KEY` is at least 64 random bytes (not the default)
- [ ] Database password ≥ 32 random characters, stored only in secret provider
- [ ] Entra ID client secret stored only in secret provider
- [ ] HTTPS enforced; HTTP redirects to HTTPS
- [ ] `UNIMONITOR_CORS_ORIGINS` lists only your actual frontend origin(s)
- [ ] `DEBUG=false` / `UNIMONITOR_ENV != development`
- [ ] Database accessible only from application subnet (not public)
- [ ] Redis accessible only from application subnet (not public)
- [ ] Container images scanned for CVEs (`docker scout cves` or Trivy)
- [ ] `make secrets-check` passes on the deployment branch
- [ ] Alembic migrations reviewed for data exposure risks
- [ ] Admin account created with a strong password and MFA enabled in Entra ID
- [ ] Log retention configured (minimum 90 days for compliance)
- [ ] Backup and recovery tested

---

## Security Contact

If you need to reach the security team urgently, email the address above with the subject line `[URGENT] UniMonitor Security`.
