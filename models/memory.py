# models/memory.py
from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKey


class Memory(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "memories"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    interaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interactions.id"), nullable=True
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="general")  # preference, fact, emotion, event
    emotional_context: Mapped[str | None] = mapped_column(String(64), nullable=True)
    salience_score: Mapped[float] = mapped_column(Float, default=0.5)

    embedding = relationship("MemoryEmbedding", back_populates="memory", uselist=False, lazy="selectin")
