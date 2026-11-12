# UniMonitor Secret Management

**Version:** 1.0  
**Updated:** 2026-11-06

---

## Overview

UniMonitor's secret management system ensures that **no plaintext secrets are
ever stored** in source code, configuration files, the database, Docker
manifests, or installer assets.

All credentials are retrieved at runtime through a unified `SecretResolver`
abstraction that supports three providers:

| Provider | Best For | Required Packages |
|---|---|---|
| **Azure Key Vault** | Azure-hosted, enterprise | `azure-keyvault-secrets`, `azure-identity` |
| **AWS Secrets Manager** | AWS-hosted, enterprise | `boto3` |
| **Local Vault** (default) | On-premises, offline, development | `cryptography` (included in core) |

---

## Security Guarantees

- Secrets are stored **by reference** in the database — a path string like
  `azure_key_vault://unimonitor/tenants/abc/client-secret`, not the secret value.
- The `SecretResolver` caches decrypted values in process memory only (not
  Redis, not disk) with a configurable TTL (default: 300 seconds).
- Every secret access (read, write, rotate, delete) is logged to the
  structured audit log.
- Failover from cloud provider to Local Vault is automatic and audit-logged.

---

## Configuration

### Environment Variables

```bash
# Provider selection
SECRETS_PROVIDER=local_vault        # azure_key_vault | aws_secrets_manager | local_vault

# Cache
SECRETS_CACHE_TTL_SECONDS=300       # 0 = disable caching

# Failover
SECRETS_FAILOVER_ENABLED=true       # fall back to Local Vault on primary failure

# Audit log file (optional)
SECRETS_AUDIT_LOG_PATH=/var/log/unimonitor/secrets-audit.jsonl
```

### Azure Key Vault

```bash
SECRETS_PROVIDER=azure_key_vault
AZURE_KEY_VAULT_URL=https://my-vault.vault.azure.net/

# Authentication — DefaultAzureCredential tries in order:
# 1. AZURE_CLIENT_ID + AZURE_CLIENT_SECRET + AZURE_TENANT_ID (env vars)
# 2. Workload Identity (AKS)
# 3. Managed Identity (VM / App Service)
# 4. Azure CLI (local dev)
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...             # only needed for service principal auth
AZURE_TENANT_ID=...
```

Install:
```bash
pip install unimonitor[azure-secrets]
```

### AWS Secrets Manager

```bash
SECRETS_PROVIDER=aws_secrets_manager
AWS_REGION=us-east-1

# Authentication — standard boto3 credential chain:
# 1. AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY (env vars)
# 2. ~/.aws/credentials
# 3. IAM Role (EC2 / ECS / Lambda)
AWS_ACCESS_KEY_ID=...               # only needed for explicit credential auth
AWS_SECRET_ACCESS_KEY=...
```

Install:
```bash
pip install unimonitor[aws-secrets]
```

### Local Vault

```bash
SECRETS_PROVIDER=local_vault
VAULT_DIR=~/.unimonitor/vault       # default
VAULT_KEY_PATH=/mnt/usb/vault.key  # optional: separate key location
```

The Local Vault uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256).
On first run, a master key is generated and stored at `VAULT_KEY_PATH`
(permissions: 600).

> **Security recommendation:** On production deployments, store `vault.key` on
> a separate physical medium (USB key, HSM, secrets management appliance).

---

## Setup Wizard

The interactive wizard configures your chosen provider and validates it before
writing any configuration:

```bash
unimonitor setup --run-wizard
# or
python scripts/setup_wizard.py
```

The wizard:
1. Prompts for provider type and connection details
2. Tests connectivity and authentication
3. Performs a read/write round-trip
4. Stores the application secret key in the vault
5. Runs database migrations
6. Creates the admin account
7. Outputs a readiness report

---

## CLI Commands

```bash
# Check provider health
unimonitor secrets health

# Store a secret
unimonitor secrets set unimonitor/smtp/password "mysecretpassword"

# Retrieve a secret (stdout — use in scripts)
unimonitor secrets get unimonitor/smtp/password

# Rotate a secret
unimonitor secrets rotate unimonitor/smtp/password "newpassword"
```

---

## Programmatic Usage

```python
from unimonitor.secrets import get_secret_resolver

async def get_smtp_password() -> str:
    resolver = await get_secret_resolver()
    # Direct name lookup
    return await resolver.get("unimonitor/smtp/password")

async def get_tenant_secret(ref: str) -> str:
    """ref stored in DB: 'azure_key_vault://unimonitor/tenants/abc/secret'"""
    resolver = await get_secret_resolver()
    return await resolver.resolve_ref(ref)
```

---

## Secret Naming Convention

```
unimonitor/                     — top-level namespace
  app/
    secret-key                  — UNIMONITOR_SECRET_KEY
  db/
    password                    — database password
  admin/
    initial-password            — bootstrap admin password (rotate after first login)
  smtp/
    password                    — SMTP password
  tenants/
    <tenant-id>/
      client-secret             — Microsoft Graph app registration client secret
  api-keys/
    azure-openai                — Azure OpenAI API key
    hibp                        — HaveIBeenPwned API key
```

---

## Rotation

Secrets can carry rotation policy via tags:

```json
{
  "rotate_after_days": "90",
  "last_rotated_at": "2026-11-06T00:00:00"
}
```

The Celery beat scheduler runs a nightly rotation check (task:
`unimonitor.tasks.secrets.check_rotation_due`). Configure rotation hooks in
`unimonitor/secrets/rotation.py` for post-rotation actions (e.g., refresh
connection pool, invalidate JWT sessions).

---

## Kubernetes: External Secrets Operator

For Kubernetes deployments, use the External Secrets Operator instead of raw
`Secret` resources. Example manifests are in
`deploy/kubernetes/external-secrets/`.

```yaml
# Azure Key Vault
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: unimonitor-akv
  namespace: unimonitor
spec:
  provider:
    azurekv:
      vaultUrl: "https://my-vault.vault.azure.net/"
      authType: ManagedIdentity
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: unimonitor-db-creds
  namespace: unimonitor
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: unimonitor-akv
    kind: SecretStore
  target:
    name: unimonitor-db-creds
    creationPolicy: Owner
  data:
    - secretKey: DATABASE_PASSWORD
      remoteRef:
        key: unimonitor/db/password
```

---

## Audit Log Format

Each entry is a JSON line:

```json
{
  "timestamp": "2026-11-06T12:00:00.000000+00:00",
  "event": "secret_access",
  "operation": "get",
  "secret_name": "unimonitor/smtp/password",
  "provider": "azure_key_vault",
  "success": true,
  "latency_ms": 42.3,
  "error": null
}
```
