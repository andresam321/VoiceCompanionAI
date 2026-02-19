# models/user_profile.py
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKey


class UserProfile(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False
    )

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    interests: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    preferences: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    personality_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="user_profile")
