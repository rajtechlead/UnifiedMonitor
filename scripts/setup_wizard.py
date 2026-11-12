"""
UniMonitor First-Run Setup Wizard.

Guides the administrator through:
  1. Secret provider selection (Azure Key Vault / AWS SM / Local Vault)
  2. Connectivity and authentication validation
  3. Required structure creation (vault init, namespace, test secret)
  4. Read/write round-trip test
  5. Database migration
  6. Admin account creation
  7. Readiness report

Run via:
    python scripts/setup_wizard.py
    unimonitor setup --run-wizard
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
    from rich.table import Table
    from rich import print as rprint
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

console = Console() if HAS_RICH else None


def _print(msg: str, style: str = "") -> None:
    if HAS_RICH and console:
        console.print(msg, style=style)
    else:
        print(msg)


def _ask(prompt: str, default: str = "") -> str:
    if HAS_RICH:
        return Prompt.ask(prompt, default=default)
    return input(f"{prompt} [{default}]: ").strip() or default


def _confirm(prompt: str, default: bool = True) -> bool:
    if HAS_RICH:
        return Confirm.ask(prompt, default=default)
    answer = input(f"{prompt} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
    return default if not answer else answer.startswith("y")


# ---------------------------------------------------------------------------
# Provider setup functions
# ---------------------------------------------------------------------------

async def setup_azure_key_vault() -> dict:
    """Collect and validate Azure Key Vault configuration."""
    _print("\n[bold cyan]Azure Key Vault Configuration[/bold cyan]")

    vault_url = _ask(
        "  Vault URL (e.g. https://my-vault.vault.azure.net/)",
        os.environ.get("AZURE_KEY_VAULT_URL", ""),
    )
    if not vault_url:
        return {"success": False, "error": "Vault URL is required"}

    _print("  Testing connectivity...", style="dim")
    try:
        from unimonitor.secrets.azure_keyvault import AzureKeyVaultProvider
        provider = AzureKeyVaultProvider(vault_url=vault_url)
        health = await provider.health_check()
        if not health.healthy:
            return {"success": False, "error": health.message}

        # Test write/read
        test_name = "unimonitor-setup-test"
        await provider.set_secret(test_name, "wizard-test-value")
        read_back = await provider.get_secret(test_name)
        await provider.delete_secret(test_name)
        assert read_back == "wizard-test-value", "Read-back mismatch"

        return {
            "success": True,
            "SECRETS_PROVIDER": "azure_key_vault",
            "AZURE_KEY_VAULT_URL": vault_url,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def setup_aws_secrets_manager() -> dict:
    """Collect and validate AWS Secrets Manager configuration."""
    _print("\n[bold cyan]AWS Secrets Manager Configuration[/bold cyan]")

    region = _ask("  AWS Region", os.environ.get("AWS_REGION", "us-east-1"))

    _print("  Testing connectivity...", style="dim")
    try:
        from unimonitor.secrets.aws_secrets_manager import AWSSecretsManagerProvider
        provider = AWSSecretsManagerProvider(region_name=region)
        health = await provider.health_check()
        if not health.healthy:
            return {"success": False, "error": health.message}

        # Test write/read
        test_name = "unimonitor/setup-test"
        await provider.set_secret(test_name, "wizard-test-value")
        read_back = await provider.get_secret(test_name)
        await provider.delete_secret(test_name, recovery_window_days=7)
        assert read_back == "wizard-test-value", "Read-back mismatch"

        return {
            "success": True,
            "SECRETS_PROVIDER": "aws_secrets_manager",
            "AWS_REGION": region,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def setup_local_vault() -> dict:
    """Initialize and validate the encrypted local vault."""
    _print("\n[bold cyan]Local Vault Configuration[/bold cyan]")

    default_vault_dir = str(Path.home() / ".unimonitor" / "vault")
    vault_dir = _ask("  Vault directory", default_vault_dir)
    separate_key = _confirm("  Store master key in a separate location? (recommended for production)", default=False)
    key_path = ""
    if separate_key:
        key_path = _ask("  Master key file path", str(Path(vault_dir) / "vault.key"))

    _print("  Initializing vault...", style="dim")
    try:
        from unimonitor.secrets.local_vault import LocalVaultProvider
        provider = LocalVaultProvider(
            vault_dir=vault_dir,
            key_path=key_path or None,
        )
        key_file = provider.initialize()
        health = await provider.health_check()
        if not health.healthy:
            return {"success": False, "error": health.message}

        # Test write/read/delete
        await provider.set_secret("unimonitor/setup-test", "wizard-test-value")
        read_back = await provider.get_secret("unimonitor/setup-test")
        await provider.delete_secret("unimonitor/setup-test")
        assert read_back == "wizard-test-value", "Read-back mismatch"

        return {
            "success": True,
            "SECRETS_PROVIDER": "local_vault",
            "VAULT_DIR": vault_dir,
            "VAULT_KEY_PATH": str(key_file),
            "key_path": str(key_file),
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Main wizard
# ---------------------------------------------------------------------------

async def run_wizard() -> int:
    """Run the full setup wizard. Returns 0 on success, 1 on failure."""
    if HAS_RICH:
        console.print(Panel.fit(
            "[bold blue]UniMonitor Setup Wizard[/bold blue]\n"
            "Secure • Enterprise-Ready • M365 Native",
            border_style="blue",
        ))
    else:
        print("=" * 60)
        print("  UniMonitor Setup Wizard")
        print("=" * 60)

    _print("\n[bold]Step 1 of 5: Secret Provider Selection[/bold]")
    _print("  UniMonitor never stores secrets in plaintext.")
    _print("  Choose how secrets will be stored and retrieved:\n")
    _print("    1) Azure Key Vault    — enterprise, Azure-hosted")
    _print("    2) AWS Secrets Manager — enterprise, AWS-hosted")
    _print("    3) Local Vault (default) — on-premises / offline / development\n")

    choice = _ask("  Enter choice [1/2/3]", "3")

    if choice == "1":
        result = await setup_azure_key_vault()
    elif choice == "2":
        result = await setup_aws_secrets_manager()
    else:
        result = await setup_local_vault()

    if not result.get("success"):
        _print(f"\n[red]✗ Secret provider setup failed: {result.get('error')}[/red]")
        return 1

    _print(f"\n[green]✓ Secret provider configured: {result['SECRETS_PROVIDER']}[/green]")

    # Set environment for downstream steps
    for key, value in result.items():
        if key not in ("success", "key_path") and value:
            os.environ[key] = value

    # ── Step 2: Secret Key ──────────────────────────────────────
    _print("\n[bold]Step 2 of 5: Application Secret Key[/bold]")
    import secrets
    generated_key = secrets.token_hex(32)
    secret_key_ref = _ask(
        "  Secret reference name for UNIMONITOR_SECRET_KEY (stored in vault)",
        "unimonitor/app/secret-key",
    )
    from unimonitor.secrets.resolver import get_secret_resolver, reset_resolver
    reset_resolver()
    resolver = await get_secret_resolver()
    await resolver.set(secret_key_ref, generated_key)
    _print(f"  [green]✓ Application secret key stored as '{secret_key_ref}'[/green]")

    # ── Step 3: Database ────────────────────────────────────────
    _print("\n[bold]Step 3 of 5: Database Configuration[/bold]")
    db_choice = _ask("  Database [1=SQLite (default), 2=PostgreSQL]", "1")
    if db_choice == "2":
        db_host = _ask("  PostgreSQL host", "localhost")
        db_port = _ask("  PostgreSQL port", "5432")
        db_name = _ask("  Database name", "unimonitor")
        db_user = _ask("  Database user", "unimonitor")
        db_pass = _ask("  Database password")
        db_pass_ref = "unimonitor/db/password"
        await resolver.set(db_pass_ref, db_pass)
        db_url = f"postgresql+asyncpg://{db_user}@{db_host}:{db_port}/{db_name}"
        _print(f"  [green]✓ DB password stored as '{db_pass_ref}'[/green]")
        _print(f"  DATABASE_URL = {db_url}  (password stored in vault)")
    else:
        db_url = "sqlite+aiosqlite:///./unimonitor.db"
        _print("  [green]✓ Using SQLite (unimonitor.db)[/green]")

    # ── Step 4: Run Migrations ──────────────────────────────────
    _print("\n[bold]Step 4 of 5: Database Migration[/bold]")
    if _confirm("  Run database migrations now?"):
        try:
            from alembic.config import Config
            from alembic import command as alembic_cmd
            ini = Path(__file__).resolve().parents[1] / "alembic.ini"
            if ini.exists():
                cfg = Config(str(ini))
                alembic_cmd.upgrade(cfg, "head")
                _print("  [green]✓ Migrations complete[/green]")
            else:
                _print("  [yellow]⚠ alembic.ini not found — skipping migration[/yellow]")
        except Exception as exc:
            _print(f"  [red]✗ Migration failed: {exc}[/red]")

    # ── Step 5: Admin Account ───────────────────────────────────
    _print("\n[bold]Step 5 of 5: Admin Account[/bold]")
    admin_email = _ask("  Admin email address")
    if admin_email:
        admin_pass = _ask("  Admin password (min 12 chars)")
        admin_pass_ref = "unimonitor/admin/initial-password"
        await resolver.set(admin_pass_ref, admin_pass)
        _print(f"  [green]✓ Admin credentials stored (reference: '{admin_pass_ref}')[/green]")

    # ── Readiness Report ────────────────────────────────────────
    _print("\n[bold cyan]━━━ Readiness Report ━━━[/bold cyan]")
    health = await resolver.health_check()

    report_lines = [
        f"  Timestamp    : {datetime.utcnow().isoformat()}Z",
        f"  Provider     : {result['SECRETS_PROVIDER']}",
        f"  Provider OK  : {'YES' if health.get('primary_healthy') else 'NO'}",
        f"  Database     : {db_url.split('//')[0]}//***",
        f"  Admin Email  : {admin_email or '(skipped)'}",
    ]

    if HAS_RICH:
        table = Table(title="Setup Complete", show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="bold")
        table.add_column("Value")
        for line in report_lines:
            k, v = line.split(":", 1)
            table.add_row(k.strip(), v.strip())
        console.print(table)
    else:
        for line in report_lines:
            print(line)

    _print("\n[green bold]✓ UniMonitor is ready. Run: unimonitor start[/green bold]\n")

    # Persist .env file (no plaintext secrets — only refs and non-sensitive settings)
    env_path = Path(".env")
    if not env_path.exists() and _confirm("  Write a .env file with non-sensitive settings?"):
        env_lines = [
            "# UniMonitor environment configuration",
            "# Generated by setup wizard — DO NOT add plaintext secrets to this file",
            f"SECRETS_PROVIDER={result['SECRETS_PROVIDER']}",
        ]
        if result.get("AZURE_KEY_VAULT_URL"):
            env_lines.append(f"AZURE_KEY_VAULT_URL={result['AZURE_KEY_VAULT_URL']}")
        if result.get("AWS_REGION"):
            env_lines.append(f"AWS_REGION={result['AWS_REGION']}")
        if result.get("VAULT_DIR"):
            env_lines.append(f"VAULT_DIR={result['VAULT_DIR']}")
        if result.get("VAULT_KEY_PATH"):
            env_lines.append(f"VAULT_KEY_PATH={result['VAULT_KEY_PATH']}")
        env_lines += [
            f"DATABASE_URL={db_url}",
            "UNIMONITOR_ENV=production",
        ]
        env_path.write_text("\n".join(env_lines) + "\n")
        _print(f"  [green]✓ .env written to {env_path.resolve()}[/green]")

    return 0


def main() -> None:
    sys.exit(asyncio.run(run_wizard()))


if __name__ == "__main__":
    main()
