# db/engine.py
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from api.app.config import get_settings

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_settings().database_url,
            pool_size=10,
            max_overflow=20,
            echo=False,
        )
    return _engine
