"""
Shared pytest fixtures for UniMonitor tests.
"""
import asyncio
import os
from typing import AsyncGenerator, Generator
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Use in-memory SQLite for tests
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32chars")
os.environ.setdefault("UNIMONITOR_ENV", "test")           # avoids production secret-key validation
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

from unimonitor.db.base import Base
import unimonitor.db.models  # noqa: F401 — registers all ORM models with Base.metadata
from unimonitor.db.session import get_db
import unimonitor.db.base as _db_base  # patched below to redirect async_session_factory
from unimonitor.main import app


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create a single event loop for all session-scoped fixtures."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create the test database engine."""
    db_url = os.environ["DATABASE_URL"]
    _engine = create_async_engine(db_url, echo=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def _session_factory(engine):
    """A session factory bound to the test engine (session-scoped, shared)."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def db_session(_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean DB session per test, rolled back after each."""
    async with _session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, _session_factory) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with DB session and session_factory overrides.

    Patches both FastAPI dependency injection (get_db / get_session) AND
    the module-level async_session_factory used by routers that call it
    directly (e.g. tenants.py, monitoring.py).
    """
    from unimonitor.db.base import get_session  # alias of get_async_session

    async def override_get_db():
        yield db_session

    # Override both injectable session providers
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session] = override_get_db

    # Patch the module-level async_session_factory so routers that call
    # `async with async_session_factory() as session:` also hit the test DB.
    original_factory = _db_base.async_session_factory
    _db_base.async_session_factory = _session_factory

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True,
    ) as ac:
        yield ac

    # Restore originals
    app.dependency_overrides.clear()
    _db_base.async_session_factory = original_factory


@pytest_asyncio.fixture
async def tenant(db_session: AsyncSession):
    """Create a test tenant."""
    from unimonitor.db.models.tenant import Tenant
    t = Tenant(
        id="test-tenant-id-00000000000001",
        name="Test Organization",
        tenant_id="test-tenant",
        domain="test.example.com",
        is_active=True,
    )
    db_session.add(t)
    await db_session.flush()
    return t


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession, tenant):
    """Create a test admin user."""
    from unimonitor.db.models.user import AppUser
    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    u = AppUser(
        id="test-user-id-000000000000001",
        email="admin@test.example.com",
        full_name="Test Admin",
        hashed_password=pwd.hash("TestPassword123!"),
        role="admin",
        is_active=True,
        tenant_id=tenant.id,
    )
    db_session.add(u)
    await db_session.flush()
    return u


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient, admin_user, tenant) -> str:
    """Get a valid JWT token for the test admin."""
    r = await client.post(
        "/api/v1/auth/login",
        data={"username": admin_user.email, "password": "TestPassword123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    return {"Authorization": f"Bearer {auth_token}"}
