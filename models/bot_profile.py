# models/bot_profile.py
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKey

DEFAULT_TRAITS = {
    "warmth": 0.9,
    "humor": 0.7,
    "curiosity": 0.8,
    "energy": 0.6,
    "verbosity": 0.4,
}

DEFAULT_RULES = {
    "safe_topics_only": True,
    "max_response_sentences": 20,
    "always_encourage": True,
}

DEFAULT_MODES = ["default", "bedtime", "homework", "creative"]


class BotProfile(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "bot_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), default="Pal")
    voice: Mapped[str] = mapped_column(String(64), default="nova")
    traits: Mapped[dict] = mapped_column(JSONB, default=DEFAULT_TRAITS)
    rules: Mapped[dict] = mapped_column(JSONB, default=DEFAULT_RULES)
    favorite_modes: Mapped[list] = mapped_column(JSONB, default=DEFAULT_MODES)
    active_mode: Mapped[str] = mapped_column(String(64), default="default")
    wake_words: Mapped[list] = mapped_column(JSONB, default=["Pal"])
    user = relationship("User", back_populates="bot_profile")
