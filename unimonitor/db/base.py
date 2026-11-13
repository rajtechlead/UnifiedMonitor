"""SQLAlchemy async engine and session factory."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import MetaData, event
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from unimonitor.config import get_settings

settings = get_settings()

# Naming convention for constraints (Alembic-compatible)
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base for all ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Engine creation
def _create_engine():
    kwargs: dict[str, Any] = {
        "echo": settings.DATABASE_ECHO,
        "future": True,
    }
    if not settings.is_sqlite:
        kwargs.update(
            {
                "pool_size": settings.DATABASE_POOL_SIZE,
                "max_overflow": settings.DATABASE_MAX_OVERFLOW,
                "pool_pre_ping": True,
                "pool_recycle": 3600,
            }
        )
    else:
        kwargs["connect_args"] = {"check_same_thread": False}

    return create_async_engine(settings.DATABASE_URL, **kwargs)


engine = _create_engine()

# SQLite: enable WAL mode and foreign keys
if settings.is_sqlite:

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_all_tables() -> None:
    """Create all tables (dev/test only – use Alembic for prod)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables() -> None:
    """Drop all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# Alias used by monitoring.py and other API modules
get_session = get_async_session


@asynccontextmanager
async def db_session_context() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for direct use: `async with db_session_context() as session:`.

    This is for code that cannot use FastAPI DI (e.g. background tasks, CLI commands).
    Use the `get_db` / `get_async_session` generator for FastAPI routes.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Aliases used by main.py startup/shutdown lifecycle
async def init_db() -> None:
    """Initialise database (create tables if not present). Alias for create_all_tables."""
    await create_all_tables()
