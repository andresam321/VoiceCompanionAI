# models/device.py
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKey


class Device(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "devices"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(255), default="default")
    hw_model: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user = relationship("User", back_populates="devices")
