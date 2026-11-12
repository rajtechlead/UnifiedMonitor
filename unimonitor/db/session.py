"""
DB session aliases — compatibility shim so imports like
`from unimonitor.db.session import get_db, AsyncSessionLocal`
work alongside the canonical engine / session factory in `base.py`.
"""
from __future__ import annotations

from unimonitor.db.base import (
    async_session_factory as AsyncSessionLocal,
)
from unimonitor.db.base import (
    create_all_tables,
    drop_all_tables,
    engine,
)
from unimonitor.db.base import (
    get_async_session as get_db,
)

__all__ = [
    "AsyncSessionLocal",
    "get_db",
    "engine",
    "create_all_tables",
    "drop_all_tables",
]
