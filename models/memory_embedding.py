# models/memory_embedding.py
from __future__ import annotations

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKey

EMBEDDING_DIM = 1536


class MemoryEmbedding(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "memory_embeddings"

    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)

    memory = relationship("Memory", back_populates="embedding")
