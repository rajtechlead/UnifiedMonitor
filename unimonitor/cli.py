"""
UniMonitor CLI entry point.

Commands::

    unimonitor start        — Start the FastAPI server
    unimonitor setup        — Run database migrations and seed admin user
    unimonitor migrate      — Run Alembic migrations only
    unimonitor smoke-test   — Run smoke tests against a running instance
    unimonitor secrets      — Secret management utilities
"""
from __future__ import annotations

import sys

import click


@click.group()
@click.version_option(package_name="unimonitor", prog_name="unimonitor")
def main() -> None:
    """UniMonitor — Unified M365 Security & GRC Platform."""


@main.command()
@click.option("--host", default="0.0.0.0", show_default=True, help="Bind host")
@click.option("--port", default=8000, show_default=True, type=int, help="Bind port")
@click.option("--workers", default=1, show_default=True, type=int, help="Uvicorn worker count")
@click.option("--reload", is_flag=True, default=False, help="Auto-reload on code changes (dev only)")
def start(host: str, port: int, workers: int, reload: bool) -> None:
    """Start the UniMonitor API server."""
    try:
        import uvicorn
    except ImportError:
        click.echo("uvicorn is required: pip install uvicorn[standard]", err=True)
        sys.exit(1)

    click.echo(f"Starting UniMonitor on {host}:{port} (workers={workers})")
    uvicorn.run(
        "unimonitor.main:app",
        host=host,
        port=port,
        workers=workers if not reload else 1,
        reload=reload,
        log_level="info",
    )


@main.command()
@click.option("--run-wizard", is_flag=True, default=False, help="Run the interactive setup wizard")
def setup(run_wizard: bool) -> None:
    """Run database migrations and optionally the full setup wizard."""
    if run_wizard:
        try:
            from scripts.setup_wizard import main as wizard_main
            wizard_main()
        except ImportError:
            click.echo("Setup wizard not found. Run migrations only.", err=True)
        return

    import asyncio
    from scripts.setup import run_setup
    asyncio.run(run_setup())


@main.command()
def migrate() -> None:
    """Apply Alembic database migrations."""
    from alembic.config import Config
    from alembic import command
    import os

    ini_path = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    alembic_cfg = Config(ini_path)
    click.echo("Running Alembic migrations...")
    command.upgrade(alembic_cfg, "head")
    click.echo("Migrations complete.")


@main.command(name="smoke-test")
@click.option("--url", default="http://localhost:8000", show_default=True, help="Base URL to test")
def smoke_test(url: str) -> None:
    """Run smoke tests against a running UniMonitor instance."""
    import asyncio
    try:
        from scripts.smoke_test import run_smoke_tests
        success = asyncio.run(run_smoke_tests(base_url=url))
        sys.exit(0 if success else 1)
    except ImportError:
        click.echo("Smoke test script not found.", err=True)
        sys.exit(1)


@main.group()
def secrets() -> None:
    """Secret management utilities."""


@secrets.command(name="health")
def secrets_health() -> None:
    """Check health of configured secret provider."""
    import asyncio
    from unimonitor.secrets.resolver import get_secret_resolver

    async def _check():
        resolver = await get_secret_resolver()
        report = await resolver.health_check()
        for p in report.get("providers", []):
            status = "✅" if p["healthy"] else "❌"
            latency = f" ({p['latency_ms']:.0f}ms)" if p.get("latency_ms") else ""
            click.echo(f"  {status} {p['provider']}{latency}: {p['message']}")

    click.echo("Checking secret provider health...")
    asyncio.run(_check())


@secrets.command(name="set")
@click.argument("name")
@click.argument("value")
def secrets_set(name: str, value: str) -> None:
    """Set a secret value (use with caution — value visible in shell history)."""
    import asyncio
    from unimonitor.secrets.resolver import get_secret_resolver

    async def _set():
        resolver = await get_secret_resolver()
        metadata = await resolver.set(name, value)
        click.echo(f"✅ Secret '{name}' stored via {metadata.provider.value}")

    asyncio.run(_set())


@secrets.command(name="get")
@click.argument("name")
def secrets_get(name: str) -> None:
    """Retrieve a secret value (outputs to stdout — use in scripts only)."""
    import asyncio
    from unimonitor.secrets.resolver import get_secret_resolver

    async def _get():
        resolver = await get_secret_resolver()
        value = await resolver.get(name)
        click.echo(value)

    asyncio.run(_get())


@secrets.command(name="rotate")
@click.argument("name")
@click.argument("new_value")
def secrets_rotate(name: str, new_value: str) -> None:
    """Rotate a secret to a new value."""
    import asyncio
    from unimonitor.secrets.resolver import get_secret_resolver

    async def _rotate():
        resolver = await get_secret_resolver()
        metadata = await resolver.rotate(name, new_value)
        click.echo(f"✅ Secret '{name}' rotated (version: {metadata.version or 'N/A'})")

    asyncio.run(_rotate())


if __name__ == "__main__":
    main()
