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
# The setup wizard writes these from the connection you make in the browser.
# Certificate authentication is the default; a secret is used only if you chose one.
# ENTRA_CLIENT_ID=
# ENTRA_TENANT_ID=
# ENTRA_CLIENT_CERTIFICATE=   (stored in the secret provider — never in .env)
# ENTRA_CLIENT_PRIVATE_KEY=   (stored in the secret provider — never in .env)
# ENTRA_CLIENT_SECRET=        (only for client-secret authentication)
# ENTRA_SIGNIN_CLIENT_ID=     (optional: your own app for the wizard's sign-in, see §6)

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

### Step 1 — Run the setup wizard

Open <http://localhost:8000/setup> (the Windows installer opens it for you). The wizard:

1. creates the administrator account and the database,
2. asks **which platforms to monitor** — Microsoft 365, AWS, Google Cloud and/or Google Workspace; at least one is required,
3. connects the platforms you picked.

For Microsoft 365, sign in as a Global Administrator and UniMonitor creates the Entra app
registration, adds the read-only Graph permissions below, grants admin consent, generates a
client certificate and uploads it to the app. The private key is kept in the encrypted secret
vault; no client secret is created unless you choose that method.

AWS, Google Cloud and Google Workspace ask only for the credentials that cannot be created for
you, and each one is validated against the live API before it is saved.

#### Certificate authentication (default)

The wizard offers two credentials for the Entra app registration:

| Method | How it works | When to choose it |
|--------|--------------|-------------------|
| **Certificate** (default) | UniMonitor generates a self-signed certificate with the validity you pick (365 days by default, 1–1095 allowed), uploads the public part to the app registration and keeps the private key in the vault. | Almost always — nothing guessable is stored and rotation is explicit. |
| **Client secret** | Entra mints a secret string, stored in the vault. | Tenant policy blocks certificate credentials. |

If Graph refuses the certificate upload (tenant policy, or a consent that only covers app
creation) the wizard does **not** fail. It offers the certificate files for download —
`.key.pem`, `.crt.pem` and the `.cer` Entra accepts — and lists the portal steps:

1. **Entra admin centre → Identity → Applications → App registrations → UniMonitor →
   Certificates & secrets → Certificates → Upload certificate**
2. Choose the downloaded `.cer` file, then **Add**.
3. Return to the wizard and press **Check certificate connectivity**.

Only after that check succeeds does the connection count as configured and the wizard allow
you to continue to the next window.

The certificate's thumbprint and expiry are shown in **Settings → Platform connections**.
Within 30 days of expiry the row warns you, and **Rotate certificate** adds a new key to the
app registration, proves it works and retires the old one — no portal visit needed. The wizard
makes this possible by granting the app `Application.ReadWrite.OwnedBy` and adding it as an
**owner of its own registration**: that permission only reaches applications the app owns, so
its scope is exactly "rotate my own certificate". An app registered by hand needs both before
the button will work; otherwise the row explains what to grant and you can upload the new
certificate in the portal instead.

#### If the sign-in itself is refused (`AADSTS65002`)

The wizard signs in with Microsoft Graph PowerShell's own public client, which Entra
preauthorizes for app-registration work. Some tenants still block Microsoft's first-party
clients from requesting these permissions and answer:

> AADSTS65002: Consent between first party application … must be configured via
> preauthorization

Nothing is broken on your side; use one of these:

1. **Your own sign-in app** — register an app, add the *delegated* permission
   `Application.ReadWrite.All` and `AppRoleAssignment.ReadWrite.All` for Microsoft Graph,
   grant admin consent, then set `ENTRA_SIGNIN_CLIENT_ID` to that app's client ID in `.env`
   and restart. The wizard uses it for the device-code sign-in.
2. **Register by hand** — see *Step 2 (alternative)* below, then choose
   **I already have an app registration — enter credentials manually** in the wizard.
   Everything after the credential is unchanged.

#### One service account for every platform (SSO)

An administrator who would rather not hand out long-lived keys can connect the clouds with a
single identity per platform:

| Platform | SSO / shared identity |
|----------|-----------------------|
| **AWS** | Create one IAM role with the read-only policy and a trust policy for the account UniMonitor runs in. In the wizard choose **IAM role / SSO (assume role)** and paste the role ARN (plus an external ID if the trust policy requires one). UniMonitor assumes the role and refreshes temporary credentials — no access keys are stored. |
| **Google Cloud + Google Workspace** | Create **one** service account, grant it read access to the project and domain-wide delegation for the Workspace admin scopes, then paste its JSON key once. In the wizard, with both Google platforms selected, use **Google Cloud + Google Workspace → Connect both with one service account** — one key, one thing to rotate. |
| **Google Cloud or Workspace alone** | Use the platform's own **Service-account key** method. |

Platforms can be added or removed later from **Settings → Platform connections**, so a business
that starts with Microsoft 365 alone can connect AWS or Google Cloud when it needs them. The
Settings picker offers the same **Google Cloud + Workspace — one service account** connector as
the wizard, and shows each Microsoft connection's certificate thumbprint and expiry.

#### Web single sign-on ("Sign in with Microsoft")

The login page offers **Sign in with Microsoft**; the button is enabled only when
`ENTRA_CLIENT_ID` and `ENTRA_REDIRECT_URI` are set, so a fresh install shows a hint instead of
sending the browser to Microsoft with an empty client id.

What the installer and the wizard take care of:

1. The generated app registration includes the web redirect URI `ENTRA_REDIRECT_URI`
   (`http://localhost:8000/api/v1/auth/callback` by default).
2. On the app's **Authentication** page, *ID tokens* are not required — the callback uses the
   authorization-code flow with a certificate or secret held by the server.
3. The callback returns the session in the URL fragment and the web UI consumes it, so the user
   lands signed in on the dashboard.

One tenant-side step remains: grant **admin consent** for the delegated permissions
`User.Read` and `Organization.Read.All` the first time an administrator signs in (Entra prompts
for it, or use **API permissions → Grant admin consent**). If your web UI runs on a different
origin during development, set `UNIMONITOR_FRONTEND_URL` (for example `http://localhost:5173`)
so the callback returns there.

If the button is disabled, the app registration has not been connected yet: finish
**Microsoft 365** in the setup wizard or in **Settings → Platform connections**.

### Step 2 (alternative) — Register the app by hand

Only needed when the wizard's automated registration is blocked by tenant policy.

1. Sign in to [Entra admin centre](https://entra.microsoft.com) as a Global Administrator
2. Go to **Identity → Applications → App registrations** → **New registration**
3. Name: `UniMonitor`, account type **Accounts in this organisational directory only**, then **Register**
4. **Certificates & secrets → Certificates → Upload certificate** and upload a `.cer` file, or
   **Certificates & secrets → New client secret** if you prefer a secret; copy the value immediately
5. **API permissions → Add a permission → Microsoft Graph → Application permissions**, select the
   read-only roles below, then **Grant admin consent**

| Permission | Reason |
|------------|--------|
| `DeviceManagementConfiguration.Read.All` | Intune policies |
| `DeviceManagementManagedDevices.Read.All` | Intune device compliance |
| `Directory.Read.All` | Entra ID users, groups, roles |
| `Policy.Read.All` | Conditional Access, auth policies |
| `SecurityEvents.Read.All` | Defender alerts and Secure Score |
| `InformationProtectionPolicy.Read.All` | Purview labels |
| `Sites.Read.All` | SharePoint settings |
| `Teams.ReadBasic.All` | Teams settings |
| `AuditLog.Read.All` | Sign-in & audit logs |
| `Reports.Read.All` | Usage and security reports |
| `User.Read.All` | User profile and authentication methods |
| `Application.ReadWrite.OwnedBy` | Optional: lets Settings rotate the app's own certificate. It only reaches applications this app owns, so add the app as an **owner of its own registration** (Owners → Add) as well; without both, rotate in the portal. |
| `ServiceHealth.Read.All` | Optional: the **Service Health** page (`/admin/serviceAnnouncement/*`). Without it that page reports that the permission is missing; nothing else is affected. |

`Exchange.ManageAsApp` is an Exchange Online role, not a Graph permission: assign it in the
Exchange admin center only if you collect Exchange settings.

Then choose **Microsoft 365 → I already have an app registration — enter credentials manually** in
the setup wizard, pick **Certificate** (paste the certificate and its private key) or **Client
secret**, and continue. The wizard validates the credential against Entra before saving, so a typo
surfaces immediately.

---

### Automatic and manual data collection

Collection runs on **Celery beat**: every active tenant's assessment is queued every
`COLLECTION_INTERVAL_MINUTES` (default 15). A tenant without an explicit assessment gets a
"Continuous monitoring" one, so automatic collection never silently does nothing.

```bash
AUTO_COLLECTION=true          # false = only on demand
COLLECTION_INTERVAL_MINUTES=15
```

Start a beat process alongside the worker (`celery -A unimonitor.worker.celery_app beat`; the Docker
Compose file already runs one). Manual runs do not need beat:

- **Data Collection** page → **Collect now** (all collectors), or **Run** on a single collector
- `POST /api/v1/monitoring/collect` and `POST /api/v1/monitoring/collectors/{name}/run`

Alert policies are evaluated by the same beat schedule, so the Alert Center fills without opening
the page; **Evaluate now** runs them immediately.

### Zero Trust Assessment

Microsoft's Zero Trust Assessment is a PowerShell module that signs in to a tenant and runs 364
checks. It needs an interactive Windows session and a Global Reader (Global Administrator for the
first consent), so it runs on an administrator's workstation and UniMonitor imports the report:

```powershell
# PowerShell 7, as an administrator
.\scripts\zerotrust\Invoke-UniMonitorZeroTrust.ps1 -Tenant contoso.onmicrosoft.com `
    -UniMonitorUrl https://unimonitor.contoso.com
```

The script installs `ZeroTrustAssessment` if needed, runs `Invoke-ZtAssessment`, and posts
`ZeroTrustAssessmentReport.json` to `/api/v1/zerotrust/import`. Without `-UniMonitorUrl` it only
writes the report, which you can upload with **Import ZeroTrustAssessmentReport.json** on the
**ZT Assessment** page. The same page can be downloaded from that page and ships inside the
Windows installer.

AWS, Google Cloud and Google Workspace appear on the same page; **Evaluate now** scores their
controls from the latest collected evidence and shows the remediation text from each control's
YAML.

### Certificate authentication

Microsoft connections default to certificate authentication: the setup wizard generates a
self-signed certificate, uploads it to the app registration and keeps the private key in the
vault. The lifetime is selectable at setup and on rotation, 1–1095 days, default 365. Rotate from
**Settings → Microsoft connection → Rotate certificate**; the new certificate is added to the app
registration before the old one is removed, so collection keeps running. The app registration must
list itself as an owner for that to work (`Application.ReadWrite.OwnedBy` + Owners → Add), and
the certificate is then the only thing that has to be protected.

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

Pick the path that matches how much you want to do by hand.

### Option 1 — Let GitHub build it (no local setup)

1. Open **Actions → Windows Installer** on the repository.
2. Press **Run workflow**, type the version (for example `1.2.0`), press **Run**.
3. When the run finishes, download `windows-installer-<version>` from the run's
   **Artifacts** section. It contains the `.exe` and the portable zip.

Pushing a `v*.*.*` tag does the same thing automatically through the release
workflow and attaches the installer to the GitHub Release.

### Option 2 — One command on Windows

Requirements: Windows 10/11 or Server 2019+, Python 3.12+, Node.js 20 LTS, and
administrator rights once so NSIS can be installed if it is missing.

```powershell
git clone https://github.com/rajtechlead/UniMonitor.git
cd UniMonitor
.\scripts\build-windows-installer.cmd
```

(Or `powershell -ExecutionPolicy Bypass -File scripts\build-windows-installer.ps1`.)

That single command does every step below: build venv, dependencies, frontend,
icon, PyInstaller bundle, NSSM, NSIS (installing it via winget or chocolatey when
missing), `makensis`, a `UniMonitor.exe --help` smoke test, and the portable zip.
It stops with a non-zero exit code and a specific message if anything is missing.

Outputs:

| File | What it is |
|------|------------|
| `dist\UniMonitor-Setup-<version>-x64.exe` | The installer |
| `dist\UniMonitor-<version>-x64-portable.zip` | Zip you can unpack and run |

Options:

```powershell
.\scripts\build-windows-installer.ps1 -Version 1.2.0      # override the version
.\scripts\build-windows-installer.ps1 -SkipFrontend      # reuse unimonitor/static
.\scripts\build-windows-installer.ps1 -SkipSmokeTest     # skip the exe smoke test
```

The version defaults to the one in `pyproject.toml`.

### Option 3 — Step by step by hand

Only needed when you are debugging the pipeline. These are the steps the script
runs, in order.

1. `python -m venv .build-venv`, then `.\.build-venv\Scripts\Activate.ps1`.
2. `pip install --upgrade pip` and
   `pip install "pyinstaller>=6.16.0,<7" -e ".[production]"`.
3. In `frontend`: `npm ci`, then `npm run build`.
4. Copy `frontend\dist\*` into `unimonitor\static\`. NSIS also needs
   `branding\icon.ico`; regenerate it with `python scripts/make_icon.py` if missing.
5. `pyinstaller deploy/windows/unimonitor.spec --clean --noconfirm`
   → `dist\UniMonitor\UniMonitor.exe`.
6. Download NSSM 2.24, verify its hash, and copy `nssm-2.24\win64\nssm.exe`
   into `dist\UniMonitor\`.
7. Install NSIS 3.x and run
   `makensis /V4 /DVERSION=1.2.0 deploy\windows\install.nsi`.
8. Test: `dist\UniMonitor\UniMonitor.exe --help`, then
   `dist\UniMonitor-Setup-1.2.0-x64.exe /S /D=C:\Temp\UniMonitorTest`.

### Troubleshooting the build

| Error | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError` during PyInstaller | Hidden import missing | Add the module to `hiddenimports` in `deploy/windows/unimonitor.spec` |
| `FileNotFoundError: branding/icon.ico` | Icon missing | `python scripts/make_icon.py` |
| `makensis` not recognized | NSIS missing or not on PATH | Re-run the script (it installs NSIS) or install NSIS 3.x |
| NSIS `unable to open script` | Wrong working directory | Run `makensis` from the repo root |
| `UniMonitor.exe` exits immediately | Missing `.env` or bad config | Check `C:\ProgramData\UniMonitor\logs\` |
| Service won't start | Port 8000 in use | Edit `.env`: `API_PORT=8001` |

---

## Support

- **GitHub Issues:** https://github.com/rajtechlead/UniMonitor/issues
- **Email:** rajrsngroup@gmail.com
- **Author:** rajtechlead
