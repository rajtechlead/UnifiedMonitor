# UniMonitor — Installation Guide

> **Author:** rajtechlead · **Contact:** rajrsngroup@gmail.com
> **GitHub:** https://github.com/rajtechlead/UniMonitor

---

## Table of Contents

1. [Requirements](#1-requirements)
2. [Option A — Windows Installer (recommended)](#2-option-a--windows-installer-exe)
3. [Option B — Install from Source (Windows/Linux/macOS)](#3-option-b--install-from-source)
4. [Option C — Docker Compose](#4-option-c--docker-compose)
5. [First-Run Configuration](#5-first-run-configuration)
6. [Microsoft 365 App Registration](#6-microsoft-365-app-registration)
7. [Starting & Stopping UniMonitor](#7-starting--stopping-unimonitor)
8. [Uninstalling](#8-uninstalling)
9. [Building the Windows Installer from Source Code](#9-building-the-windows-installer-from-source-code)

---

## 1. Requirements

### For the Windows Installer (Option A)
| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Windows OS | Windows 10 / Windows Server 2019 | 64-bit only |
| RAM | 4 GB | 8 GB recommended for production |
| Disk | 2 GB free | Excluding database growth |
| Network | Outbound HTTPS (443) | To Microsoft Graph API |
| Privileges | Local Administrator | Required for installer & service setup |

> Python is **not** required — the installer bundles its own Python runtime.

### For Source / Docker Installs (Options B & C)
| Requirement | Minimum |
|-------------|---------|
| Python | 3.11 or later |
| Node.js | 20 LTS (frontend build only) |
| PostgreSQL | 14+ (or use bundled SQLite for single-node) |
| Redis | 6+ |
| Docker | 24+ (Option C only) |

---

## 2. Option A — Windows Installer (.exe)

### Step 1 — Download

Go to the [Releases page](https://github.com/rajtechlead/UniMonitor/releases) and download:

```
UniMonitor-Setup-<version>-x64.exe
```

### Step 2 — Run the Setup Wizard

1. Right-click `UniMonitor-Setup-<version>-x64.exe` → **Run as Administrator**
2. Click **Next** on the Welcome screen
3. Accept the licence agreement
4. Choose components:
   - ✅ **UniMonitor Application** — required
   - ✅ **Windows Service (auto-start)** — recommended for servers
   - ✅ **Start Menu Shortcuts**
5. Choose the install folder (default: `C:\Program Files\UniMonitor`)
6. Click **Install** — takes 1–3 minutes
7. On the Finish screen you can optionally open the browser or view this guide

### Step 3 — Edit the Configuration File

The installer creates `C:\Program Files\UniMonitor\.env`. Open it in Notepad and set:

```ini
# Required — generate with: UniMonitor.exe genkey
UNIMONITOR_SECRET_KEY=<paste generated key here>

# Database (SQLite default — change to PostgreSQL for production)
DATABASE_URL=sqlite+aiosqlite:///C:/ProgramData/UniMonitor/unimonitor.db

# Redis (required for background tasks)
REDIS_URL=redis://localhost:6379/0

# Secret provider: local | azure_key_vault | aws_secrets_manager
SECRETS_PROVIDER=local
```

> See [Section 5](#5-first-run-configuration) and [Section 6](#6-microsoft-365-app-registration) for all options.

### Step 4 — Initialise the Database

Open **Command Prompt as Administrator**, then:

```cmd
cd "C:\Program Files\UniMonitor"
UniMonitor.exe db upgrade
UniMonitor.exe admin create --email admin@yourcompany.com --password ChangeMe123!
```

### Step 5 — Start UniMonitor

If you installed the **Windows Service**:
```cmd
sc start UniMonitor
```

Or start manually:
```cmd
UniMonitor.exe start
```

Open your browser at **http://localhost:8000** and log in with the admin account you created.

---

## 3. Option B — Install from Source

> ⚠️ `pip install unimonitor` will **not** work — UniMonitor is not published to PyPI.
> Install from the GitHub source repository as shown below.

### Step 1 — Clone the repository

```powershell
git clone https://github.com/rajtechlead/UniMonitor.git
cd UniMonitor
```

### Step 2 — Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # Windows PowerShell
# or
source .venv/bin/activate          # Linux/macOS
```

### Step 3 — Install Python dependencies

```powershell
pip install -e .
```

Install optional secret providers if needed:

```powershell
pip install -e ".[azure-secrets]"   # Azure Key Vault
pip install -e ".[aws-secrets]"     # AWS Secrets Manager
pip install -e ".[all-secrets]"     # Both providers
```

### Step 4 — Build the frontend

```powershell
cd frontend
npm install
npm run build
cd ..
```

### Step 5 — Configure

Copy the example environment file and edit it:

```powershell
copy deploy\docker\.env.example .env   # Windows
# or
cp deploy/docker/.env.example .env     # Linux/macOS
```

Then edit `.env` — see [Section 5](#5-first-run-configuration).

### Step 6 — Initialise the database

```powershell
unimonitor db upgrade
unimonitor admin create --email admin@yourcompany.com --password ChangeMe123!
```

### Step 7 — Start

```powershell
unimonitor start
```

Open **http://localhost:8000**.

---

## 4. Option C — Docker Compose

### Step 1 — Clone

```bash
git clone https://github.com/rajtechlead/UniMonitor.git
cd UniMonitor
```

### Step 2 — Configure

```bash
cp deploy/docker/.env.example deploy/docker/.env
nano deploy/docker/.env     # or use your preferred editor
```

Minimum required values:

```ini
UNIMONITOR_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
POSTGRES_PASSWORD=choose-a-strong-password
```

### Step 3 — Start

```bash
docker compose -f deploy/docker/docker-compose.yml up -d
```

The stack starts:
- `unimonitor` — FastAPI application (port 8000)
- `worker` — Celery background worker
- `db` — PostgreSQL 16
- `redis` — Redis 7

### Step 4 — Initialise

```bash
docker compose -f deploy/docker/docker-compose.yml \
  exec unimonitor unimonitor db upgrade

docker compose -f deploy/docker/docker-compose.yml \
  exec unimonitor unimonitor admin create \
  --email admin@yourcompany.com --password ChangeMe123!
```

Open **http://localhost:8000**.

---

## 5. First-Run Configuration

### Full `.env` reference

```ini
# ── Environment ───────────────────────────────────────────────────────────────
UNIMONITOR_ENV=production          # development | production
LOG_LEVEL=INFO

# ── Security (required) ───────────────────────────────────────────────────────
# Generate: python -c "import secrets; print(secrets.token_hex(32))"
UNIMONITOR_SECRET_KEY=

# ── Database ──────────────────────────────────────────────────────────────────
# SQLite (single-node, default)
DATABASE_URL=sqlite+aiosqlite:///C:/ProgramData/UniMonitor/unimonitor.db

# PostgreSQL (recommended for production)
# DATABASE_URL=postgresql+asyncpg://unimonitor:password@localhost:5432/unimonitor

# ── Redis ─────────────────────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── Secret Provider ───────────────────────────────────────────────────────────
SECRETS_PROVIDER=local             # local | azure_key_vault | aws_secrets_manager

# Azure Key Vault (if SECRETS_PROVIDER=azure_key_vault)
# AZURE_KEY_VAULT_URL=https://my-vault.vault.azure.net/

# AWS Secrets Manager (if SECRETS_PROVIDER=aws_secrets_manager)
# AWS_REGION=us-east-1

# ── Microsoft Graph API ───────────────────────────────────────────────────────
# Set per-tenant via UI or unimonitor tenant add command
# AZURE_CLIENT_ID=
# AZURE_CLIENT_SECRET=   (stored in secret provider — never in .env)
# AZURE_TENANT_ID=

# ── AI Remediation (optional) ─────────────────────────────────────────────────
# AZURE_OPENAI_ENDPOINT=https://my-openai.openai.azure.com/
# AZURE_OPENAI_DEPLOYMENT=gpt-4o

# ── Telemetry (optional) ──────────────────────────────────────────────────────
# OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

### Generate a secret key

```powershell
# Windows (PowerShell)
UniMonitor.exe genkey

# Or with Python directly
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 6. Microsoft 365 App Registration

UniMonitor reads security data from Microsoft 365 via the Graph API. You need a registered application in Entra ID.

### Step 1 — Create an App Registration

1. Sign in to [Entra admin centre](https://entra.microsoft.com) as a Global Administrator
2. Go to **Identity → Applications → App registrations** → **New registration**
3. Name: `UniMonitor`
4. Supported account type: **Accounts in this organisational directory only**
5. Click **Register**
6. Note the **Application (client) ID** and **Directory (tenant) ID**

### Step 2 — Create a Client Secret

1. Go to **Certificates & secrets** → **New client secret**
2. Description: `UniMonitor production`
3. Expiry: 24 months (or per your policy)
4. Copy the **Value** immediately — you won't see it again

### Step 3 — Grant API Permissions

Go to **API permissions** → **Add a permission** → **Microsoft Graph** → **Application permissions**:

| Permission | Reason |
|------------|--------|
| `DeviceManagementConfiguration.Read.All` | Intune policies |
| `DeviceManagementManagedDevices.Read.All` | Intune device compliance |
| `Directory.Read.All` | Entra ID users, groups, roles |
| `Policy.Read.All` | Conditional Access, auth policies |
| `SecurityEvents.Read.All` | Defender alerts |
| `InformationProtectionPolicy.Read.All` | Purview labels |
| `Sites.Read.All` | SharePoint settings |
| `Exchange.ManageAsApp` | Exchange Online settings |
| `Teams.ReadBasic.All` | Teams settings |
| `AuditLog.Read.All` | Sign-in & audit logs |
| `Reports.Read.All` | Usage and security reports |

Click **Grant admin consent** for your tenant.

### Step 4 — Add the Tenant to UniMonitor

```powershell
unimonitor tenant add \
  --name "My Company" \
  --tenant-id <Directory-tenant-ID> \
  --client-id <Application-client-ID> \
  --client-secret <Client-secret-value>
```

Or use the **Tenants** page in the web UI.

---

## 7. Starting & Stopping UniMonitor

### Windows Service

```cmd
sc start UniMonitor      # start
sc stop UniMonitor       # stop
sc query UniMonitor      # check status
```

### Manual (command line)

```powershell
unimonitor start                          # foreground (Ctrl+C to stop)
unimonitor start --host 0.0.0.0           # listen on all interfaces
unimonitor start --port 9000              # custom port
unimonitor start --workers 4              # multiple workers (production)
```

### CLI reference

```
unimonitor --help

Commands:
  start          Start the UniMonitor server
  setup          Run the interactive setup wizard
  db upgrade     Apply database migrations
  db downgrade   Roll back migrations
  admin create   Create an admin account
  tenant add     Register a Microsoft 365 tenant
  tenant list    List registered tenants
  secrets health Check secret provider connectivity
  genkey         Generate a random 32-byte secret key
  worker start   Start the Celery background worker
  version        Show version information
```

---

## 8. Uninstalling

### Windows Installer

Go to **Control Panel → Programs → Uninstall a program** → **UniMonitor** → Uninstall.

Your data at `C:\ProgramData\UniMonitor\` is **preserved** by the uninstaller. Delete it manually if you want a clean removal.

### Source Install

```powershell
pip uninstall unimonitor
# Delete the clone directory
```

### Docker

```bash
docker compose -f deploy/docker/docker-compose.yml down -v   # -v removes volumes
```

---

## 9. Building the Windows Installer from Source Code

This section explains how to reproduce the `UniMonitor-Setup-<version>-x64.exe` installer yourself.

### Requirements

| Tool | Version | Download |
|------|---------|----------|
| Python | 3.11+ | https://python.org/downloads |
| Node.js | 20 LTS | https://nodejs.org |
| Git | any | https://git-scm.com |
| PyInstaller | 6.15.0+ | `pip install "pyinstaller>=6.15.0"` |
| NSIS | 3.x | https://nsis.sourceforge.io/Download |

NSIS must be on your `PATH`. After installing, verify:

```cmd
makensis /VERSION
```

### Step-by-Step Build

#### 1. Clone the repository

```powershell
git clone https://github.com/rajtechlead/UniMonitor.git
cd UniMonitor
```

#### 2. Create a build virtual environment

```powershell
python -m venv .build-venv
.\.build-venv\Scripts\Activate.ps1
```

#### 3. Install Python dependencies

```powershell
pip install --upgrade pip
pip install "pyinstaller>=6.15.0"
pip install -e ".[all-secrets]"
```

#### 4. Build the React frontend

```powershell
cd frontend
npm ci                    # clean install from lockfile
npm run build             # outputs to frontend/dist/
cd ..

# Copy built assets to where FastAPI serves them
xcopy /E /I /Y frontend\dist unimonitor\static
```

#### 5. Run PyInstaller

```powershell
pyinstaller deploy/windows/unimonitor.spec --clean --noconfirm
```

Output: `dist/UniMonitor/` — a self-contained folder with `UniMonitor.exe`.

Verify it works:

```powershell
# Note: in PowerShell you must prefix with .\  to run a local exe
.\dist\UniMonitor\UniMonitor.exe --version
```

#### 6. Download NSSM (Windows Service helper)

NSSM is bundled so users can install UniMonitor as a Windows Service without extra tools:

```powershell
# Download NSSM 2.24 (stable)
Invoke-WebRequest https://nssm.cc/release/nssm-2.24.zip -OutFile nssm.zip
Expand-Archive nssm.zip -DestinationPath nssm_tmp
Copy-Item nssm_tmp\nssm-2.24\win64\nssm.exe dist\UniMonitor\nssm.exe
Remove-Item -Recurse nssm.zip, nssm_tmp
```

#### 7. Run NSIS to create the installer

```powershell
# Replace 1.0.0 with the actual version number
makensis /V4 /DVERSION=1.0.0 deploy\windows\install.nsi
```

Output: `dist/UniMonitor-Setup-1.0.0-x64.exe`

#### 8. Test the installer

```powershell
# Install silently to a temp directory (no service, no shortcuts)
dist\UniMonitor-Setup-1.0.0-x64.exe /S /D=C:\Temp\UniMonitorTest

# Verify
C:\Temp\UniMonitorTest\UniMonitor.exe version

# Uninstall silently
C:\Temp\UniMonitorTest\Uninstall.exe /S
```

### Automated Build via GitHub Actions

The release workflow (`.github/workflows/release.yml`) runs all the steps above automatically when you push a version tag:

```powershell
# Tag and push — triggers the workflow
git tag v1.2.3
git push origin v1.2.3
```

The workflow:
1. Builds and pushes the Docker image to GHCR
2. Builds `UniMonitor-Setup-<version>-x64.exe` on `windows-latest`
3. Creates a GitHub Release and attaches the installer as a downloadable asset

### Troubleshooting the Build

| Error | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError` during PyInstaller | Hidden import missing | Add the module to `hiddenimports` in `deploy/windows/unimonitor.spec` |
| `FileNotFoundError: branding/icon.ico` | Icon missing | Create `branding/icon.ico` or remove the `icon=` line from the `.spec` |
| NSIS `unable to open script` | Wrong working directory | Run `makensis` from the repo root |
| `UniMonitor.exe` exits immediately | Missing `.env` or bad config | Check `C:\ProgramData\UniMonitor\logs\` |
| Service won't start | Port 8000 in use | Edit `.env`: `API_PORT=8001` |

---

## Support

- **GitHub Issues:** https://github.com/rajtechlead/UniMonitor/issues
- **Email:** rajrsngroup@gmail.com
- **Author:** rajtechlead
