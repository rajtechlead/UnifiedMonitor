# UniMonitor

**Unified Multi-Cloud Security Monitoring, GRC & Compliance Platform**

> Developed by [rajtechlead](https://github.com/rajtechlead) · Contact: [rajrsngroup@gmail.com](mailto:rajrsngroup@gmail.com)

UniMonitor consolidates security posture management, GRC framework assessments,
AI-powered remediation, and compliance reporting for Microsoft 365, Amazon Web
Services, Google Cloud Platform and Google Workspace — one deployable platform
with a per-cloud view and an aggregate view across all of them.

---

## Key Features

| Capability | Details |
|---|---|
| **Multi-Cloud Monitoring** | Real-time posture across Microsoft 365, AWS, Google Cloud and Google Workspace |
| **GRC Assessments** | 13 frameworks: NIST CSF, ISO 27001, CIS Benchmarks, SOC 2, HIPAA, PCI-DSS, and more |
| **180 Security Controls** | Pre-built controls mapped to each provider's native services — no manual configuration needed |
| **AI Remediation** | Azure OpenAI GPT-4o powered remediation plans with rule-based fallback |
| **Secret Management** | Azure Key Vault / AWS Secrets Manager / encrypted local vault — no plaintext secrets |
| **Multi-tenant** | Isolate assessments per tenant/cloud account (MSP-ready) |
| **Reporting** | PDF, DOCX, Excel, HTML, JSON, CSV — aggregate summary plus colour-coded per-cloud sections |
| **Dashboards** | Executive, CISO, Zero Trust, Multi-Cloud aggregate, per-provider cloud views, Security, Compliance, Risk, SOC, Audit, Findings, Alerts, Assessments, Reports, Licences, Service Health, Data Collection |
| **Zero Trust view** | Coverage per Microsoft Zero Trust pillar, grouped from each control's `zero_trust` mapping |
| **Triage & ROI queue** | Acknowledge, snooze, assign and resolve findings; the highest impact-per-effort fixes are ranked first |
| **Investigation timeline** | Per-finding history and collected evidence in one ordered list |
| **Alert Center** | Metric, activity and anomaly policies over findings and score history, with acknowledge / snooze / assign / resolve; Teams, Slack, SMTP and webhook delivery |
| **Licence posture** | Seats purchased, assigned and idle per SKU, read live from Microsoft Graph |
| **Service health** | Microsoft 365 service status and unresolved advisories |
| **Global search** | Ctrl+K across pages, findings, alerts and the control library |
| **Tamper-evident audit** | SHA-256 hash-chained audit trail with a verified-chain badge |
| **Scheduled collection** | Every tenant is collected automatically on a configurable interval, with per-collector manual runs |

---

## Monitored Cloud Providers

Each provider has its own collector set, control file under `controls/<provider>/`,
and dashboard. The aggregate view rolls them up side by side.

| Provider | Collector | Controls | Credentials |
|---|---|---|---|
| Microsoft 365 | Entra ID, Intune, Defender, Purview, Exchange, SharePoint, Teams, Copilot | 158 | Entra app registration (`TENANT_CLIENT_ID` / `TENANT_CLIENT_SECRET`) |
| Amazon Web Services | `aws` (boto3) | 8 | `AWS_REGION` + standard AWS credential chain |
| Google Cloud Platform | `gcp` (REST) | 8 | `GCP_PROJECT_ID`, `GCP_ACCESS_TOKEN` |
| Google Workspace | `google_workspace` (Admin SDK REST) | 6 | `GOOGLE_WORKSPACE_CUSTOMER_ID`, `GOOGLE_ACCESS_TOKEN` |

Provider dashboards live at `/clouds` (aggregate) and `/clouds/<provider>` in the
web UI, backed by `GET /api/v1/dashboard/clouds` and
`GET /api/v1/dashboard/clouds/{provider}`. A provider with no credentials returns
no findings, so its controls report *not implemented* rather than passing.

---

## Quick Start

### Option 1 — Windows Installer (easiest, no Python needed)

1. Download **`UniMonitor-Setup-<version>-x64.exe`** from the [Releases page](https://github.com/rajtechlead/UniMonitor/releases)
2. Run as Administrator — setup wizard installs and optionally registers a Windows Service
3. Finish in the browser wizard at **http://localhost:8000/setup**: create the administrator, pick the platforms and connect them
4. Open **http://localhost:8000**

Microsoft 365 registers its own Entra app after a Global Administrator sign-in, using a generated
**certificate** by default (client secret optional). AWS can attach through an assumed IAM role,
and Google Cloud and Workspace can share a single service account. **Settings → Platform
connections** adds platforms later, shows the certificate's thumbprint and expiry (warning 30 days
out) with one-click rotation, and offers the same shared-Google connector — see
[INSTALL.md §6](INSTALL.md#6-microsoft-365-app-registration). Tenants that block Microsoft's own
sign-in clients (`AADSTS65002`) set `ENTRA_SIGNIN_CLIENT_ID` to their own app.

See **[INSTALL.md](INSTALL.md)** for the full step-by-step guide.

---

### Option 2 — From Source (Windows / Linux / macOS)

> **Note:** UniMonitor is not published to PyPI — `pip install unimonitor` will not work.
> Install directly from GitHub as shown below.

```powershell
# 1. Clone
git clone https://github.com/rajtechlead/UniMonitor.git
cd UniMonitor

# 2. Install (Python 3.11+ required)
pip install -e .

# 3. Configure
copy deploy\docker\.env.example .env
# Edit .env — set UNIMONITOR_SECRET_KEY and database URL

# 4. Initialise database
unimonitor db upgrade
unimonitor admin create --email admin@yourcompany.com --password ChangeMe123!

# 5. Start
unimonitor start
```

Open **http://localhost:8000**

---

### Option 3 — Docker Compose

```bash
git clone https://github.com/rajtechlead/UniMonitor.git
cd UniMonitor
cp deploy/docker/.env.example deploy/docker/.env
# Edit .env — set UNIMONITOR_SECRET_KEY and POSTGRES_PASSWORD
docker compose -f deploy/docker/docker-compose.yml up -d
```

---

## Secret Management

UniMonitor never stores plaintext secrets in source code, configuration
files, the database, Docker manifests, or installer assets.

| Provider | Variable | Use Case |
|---|---|---|
| Azure Key Vault | `AZURE_KEY_VAULT_URL` | Azure-hosted, enterprise |
| AWS Secrets Manager | `AWS_REGION` | AWS-hosted, enterprise |
| Local Vault (default) | `VAULT_DIR`, `VAULT_KEY_PATH` | On-premises, offline, dev |

---

## Architecture

```
┌────────────────────────────────────────────────────┐
│                   React 18 Frontend                │
│         (Vite · TypeScript · TanStack Query)       │
└────────────────┬───────────────────────────────────┘
                 │  REST API
┌────────────────▼───────────────────────────────────┐
│                FastAPI + Python 3.11               │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Auth/JWT │  │ Graph API│  │   GRC Engine     │  │
│  │  (MSAL) │  │  Client  │  │ (67 controls)    │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
│  ┌──────────────────────────────────────────────┐  │
│  │          Secret Provider Abstraction         │  │
│  │  Azure KV  │  AWS SM  │  Local Vault (enc)   │  │
│  └──────────────────────────────────────────────┘  │
└──────────┬────────────────┬───────────────────────┘
           │                │
   ┌───────▼──────┐  ┌──────▼──────┐
   │  PostgreSQL  │  │    Redis    │
   │  (asyncpg)  │  │   Celery    │
   └─────────────┘  └─────────────┘
```

---

## Documentation

| Document | Description |
|---|---|
| [INSTALL.md](INSTALL.md) | Full installation guide — Windows installer, source, Docker, build steps |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design and component overview |
| [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) | Kubernetes, Azure, AWS deployment |
| [docs/SECRET_MANAGEMENT.md](docs/SECRET_MANAGEMENT.md) | Secret provider setup and rotation |
| [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md) | Pre-production checklist |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | Release history |
| [Comparison.MD](Comparison.MD) | Capability comparison with M365 Sheppard, Vigil365 and the Microsoft Zero Trust Assessment |
| [gap_analysis.md](gap_analysis.md) | Gap register, what was merged, and what was deliberately deferred |

---

## Development

```bash
git clone https://github.com/rajtechlead/UniMonitor.git
cd UniMonitor
pip install -e ".[dev]"
pytest                                           # run the test suite
UNIMONITOR_ENV=development unimonitor start --reload
```

---

## Building the Windows Installer

See **[INSTALL.md § 9](INSTALL.md#9-building-the-windows-installer-from-source-code)** for the full step-by-step build guide.

**Short version:**

```powershell
pip install "pyinstaller>=6.15.0,<7"   # 6.15+ is required for Python 3.12/3.13/3.14
pip install -e ".[all-secrets]"
cd frontend && npm ci && npm run build && cd ..
xcopy /E /I /Y frontend\dist unimonitor\static
pyinstaller deploy/windows/unimonitor.spec --clean
# Then run NSIS:
makensis /DVERSION=1.0.0 deploy\windows\install.nsi
# Output: dist/UniMonitor-Setup-1.0.0-x64.exe
```

You don't need a Windows machine. **Actions → Windows Installer → Run workflow**
([windows-installer.yml](.github/workflows/windows-installer.yml)) builds
`UniMonitor-Setup-<version>-x64.exe` plus a portable zip on `windows-latest` and
attaches them to the run. The [release workflow](.github/workflows/release.yml)
does the same automatically on a `v*.*.*` tag, alongside the Docker image. The
NSIS wizard needs `branding/icon.ico`, which is checked in and regenerable with
`python scripts/make_icon.py`.

---

## License

Proprietary © 2024 rajtechlead. All rights reserved.

**Author:** rajtechlead · **Contact:** [rajrsngroup@gmail.com](mailto:rajrsngroup@gmail.com)
