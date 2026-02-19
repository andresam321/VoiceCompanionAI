# models/event.py
from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin, UUIDPrimaryKey


class Event(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "events"

    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    level: Mapped[str] = mapped_column(String(16), default="info")  # debug | info | warn | error
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
