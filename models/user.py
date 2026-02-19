# models/user.py
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKey


class User(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    devices = relationship("Device", back_populates="user", lazy="selectin")
    conversations = relationship("Conversation", back_populates="user", lazy="selectin")
    bot_profile = relationship("BotProfile", back_populates="user", uselist=False, lazy="selectin")
    user_profile = relationship("UserProfile", back_populates="user", uselist=False, lazy="selectin")
