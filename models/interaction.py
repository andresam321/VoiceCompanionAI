# models/interaction.py
from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKey


class Interaction(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "interactions"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Audio paths
    audio_input_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    audio_output_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Transcripts
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    assistant_reply: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Emotion
    detected_emotion: Mapped[str | None] = mapped_column(String(64), nullable=True)
    emotion_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Performance
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending | processing | complete | failed

    conversation = relationship("Conversation", back_populates="interactions")
