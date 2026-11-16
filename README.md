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
| **Reporting** | PDF, DOCX, JSON, CSV compliance reports |
| **Dashboards** | Executive, Multi-Cloud aggregate, per-provider cloud views, Security, Compliance, Risk, SOC, Audit, Findings, Assessments, Reports |

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
3. Edit `C:\Program Files\UniMonitor\.env` with your credentials
4. Open **http://localhost:8000**

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

---

## Development

```bash
git clone https://github.com/rajtechlead/UniMonitor.git
cd UniMonitor
pip install -e ".[dev]"
pytest                                           # run all 105 tests
UNIMONITOR_ENV=development unimonitor start --reload
```

---

## Building the Windows Installer

See **[INSTALL.md § 9](INSTALL.md#9-building-the-windows-installer-from-source-code)** for the full step-by-step build guide.

**Short version:**

```powershell
pip install pyinstaller==6.10.0
pip install -e ".[all-secrets]"
cd frontend && npm ci && npm run build && cd ..
xcopy /E /I /Y frontend\dist unimonitor\static
pyinstaller deploy/windows/unimonitor.spec --clean
# Then run NSIS:
makensis /DVERSION=1.0.0 deploy\windows\install.nsi
# Output: dist/UniMonitor-Setup-1.0.0-x64.exe
```

Pushing a `v*.*.*` tag triggers the [release workflow](.github/workflows/release.yml)
which builds and publishes the installer automatically.

---

## License

Proprietary © 2024 rajtechlead. All rights reserved.

**Author:** rajtechlead · **Contact:** [rajrsngroup@gmail.com](mailto:rajrsngroup@gmail.com)
