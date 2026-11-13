#!/usr/bin/env python3
"""
UniMonitor post-install setup script.
Runs DB migrations, creates default admin user, seeds baseline config.
"""
import asyncio
import os
import sys
import secrets
import string

# Ensure app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def run_migrations() -> None:
    """Run Alembic migrations."""
    import subprocess
    print("[setup] Running database migrations…")
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    if result.returncode != 0:
        print(f"[setup] Migration failed:\n{result.stderr}")
        sys.exit(1)
    print("[setup] Migrations complete.")


def generate_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()"
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def create_default_admin() -> None:
    """Create default admin user and tenant if none exist."""
    from unimonitor.db.session import AsyncSessionLocal
    from unimonitor.db.models.user import User
    from unimonitor.db.models.tenant import Tenant
    from sqlalchemy import select
    import bcrypt as _bcrypt

    class _PwdContext:
        """Thin bcrypt wrapper matching passlib's hash/verify interface."""
        @staticmethod
        def hash(password: str) -> str:
            return _bcrypt.hashpw(password.encode("utf-8")[:72], _bcrypt.gensalt()).decode("utf-8")

    pwd_context = _PwdContext()

    async with AsyncSessionLocal() as db:
        # Check for existing tenants
        result = await db.execute(select(Tenant).limit(1))
        tenant = result.scalar_one_or_none()

        if not tenant:
            print("[setup] Creating default tenant…")
            tenant = Tenant(
                id="00000000-0000-0000-0000-000000000001",
                name="Default Organization",
                tenant_id="default",
                domain="localhost",
                is_active=True,
            )
            db.add(tenant)
            await db.flush()
            print(f"[setup] Created tenant: {tenant.name}")

        # Check for existing admin
        result = await db.execute(select(User).where(User.role == "admin").limit(1))
        admin = result.scalar_one_or_none()

        if not admin:
            password = generate_password()
            print("[setup] Creating default admin user…")
            admin = User(
                id="00000000-0000-0000-0000-000000000002",
                email="admin@unimonitor.local",
                full_name="UniMonitor Admin",
                role="admin",
                is_active=True,
                tenant_id=tenant.id,
                hashed_password=pwd_context.hash(password),
            )
            db.add(admin)
            await db.commit()
            print(f"[setup] ✓ Admin user created:")
            print(f"         Email:    admin@unimonitor.local")
            print(f"         Password: {password}")
            print(f"         IMPORTANT: Change this password immediately after login!")
        else:
            await db.commit()
            print(f"[setup] Admin user already exists: {admin.email}")


async def seed_notification_settings() -> None:
    """Create default notification settings for the default tenant."""
    from unimonitor.db.session import AsyncSessionLocal
    from unimonitor.db.models.notification_setting import NotificationSetting
    from unimonitor.db.models.tenant import Tenant
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).limit(1))
        tenant = result.scalar_one_or_none()
        if not tenant:
            return

        result = await db.execute(
            select(NotificationSetting).where(NotificationSetting.tenant_id == tenant.id)
        )
        existing = result.scalar_one_or_none()
        if not existing:
            ns = NotificationSetting(
                tenant_id=tenant.id,
                smtp_enabled=False,
                smtp_to_emails="[]",
                immediate_alerts=True,
                daily_digest=False,
                weekly_digest=True,
                alert_severity_threshold="HIGH",
            )
            db.add(ns)
            await db.commit()
            print("[setup] Created default notification settings.")


def check_env() -> bool:
    """Validate required environment variables."""
    required = ["DATABASE_URL", "SECRET_KEY"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"[setup] ERROR: Missing required environment variables: {', '.join(missing)}")
        print("[setup] Copy deploy/docker/.env.example to .env and configure it.")
        return False
    return True


async def main() -> None:
    print("=" * 60)
    print("  UniMonitor Setup")
    print("=" * 60)

    if not check_env():
        sys.exit(1)

    try:
        await run_migrations()
        await create_default_admin()
        await seed_notification_settings()
    except Exception as e:
        print(f"[setup] FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print()
    print("=" * 60)
    print("  Setup complete! UniMonitor is ready.")
    print("  Visit http://localhost:8000 to get started.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())


def run_setup() -> None:
    """Entry point callable from unimonitor CLI."""
    asyncio.run(main())
