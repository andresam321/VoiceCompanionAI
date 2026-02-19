# models/conversation.py
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base, TimestampMixin, UUIDPrimaryKey


class Conversation(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pending_intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pending_slots: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    user = relationship("User", back_populates="conversations")
    interactions = relationship("Interaction", back_populates="conversation", lazy="selectin")
