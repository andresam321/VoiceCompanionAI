# services/observability.py
"""
Structured event logging to the events table.
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from models.event import Event

logger = logging.getLogger(__name__)


async def log_event(
    db: AsyncSession,
    event_type: str,
    level: str = "info",
    source: str | None = None,
    message: str | None = None,
    metadata: dict | None = None,
) -> Event:
    """Persist a structured event log entry."""
    event = Event(
        event_type=event_type,
        level=level,
        source=source,
        message=message,
        metadata_=metadata,
    )
    db.add(event)
    await db.flush()
    logger.log(
        getattr(logging, level.upper(), logging.INFO),
        "[%s] %s — %s",
        event_type,
        message or "",
        metadata or {},
    )
    return event
