# models/job.py
from __future__ import annotations

import uuid

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin, UUIDPrimaryKey


class Job(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "jobs"

    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # PROCESS_VOICE_INTERACTION | SUMMARIZE_PROFILE | PROACTIVE_CHECKIN
    status: Mapped[str] = mapped_column(String(32), default="pending")
    # pending | locked | complete | failed
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
