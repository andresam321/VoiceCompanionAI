"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── users ──
    op.create_table(
        "users",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── devices ──
    op.create_table(
        "devices",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token", sa.String(255), unique=True, nullable=False),
        sa.Column("label", sa.String(255), server_default="default"),
        sa.Column("hw_model", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── conversations ──
    op.create_table(
        "conversations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── interactions ──
    op.create_table(
        "interactions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("audio_input_path", sa.String(1024), nullable=True),
        sa.Column("audio_output_path", sa.String(1024), nullable=True),
        sa.Column("transcript", sa.Text, nullable=True),
        sa.Column("assistant_reply", sa.Text, nullable=True),
        sa.Column("detected_emotion", sa.String(64), nullable=True),
        sa.Column("emotion_confidence", sa.Float, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── memories ──
    op.create_table(
        "memories",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("interaction_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("interactions.id"), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("category", sa.String(64), server_default="general"),
        sa.Column("emotional_context", sa.String(64), nullable=True),
        sa.Column("salience_score", sa.Float, server_default="0.5"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── memory_embeddings ──
    op.create_table(
        "memory_embeddings",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("memory_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("memories.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── user_profiles ──
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), unique=True, nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("interests", sa.dialects.postgresql.JSONB, server_default="{}"),
        sa.Column("preferences", sa.dialects.postgresql.JSONB, server_default="{}"),
        sa.Column("personality_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── bot_profiles ──
    op.create_table(
        "bot_profiles",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), unique=True, nullable=False),
        sa.Column("name", sa.String(128), server_default="Buddy"),
        sa.Column("voice", sa.String(64), server_default="nova"),
        sa.Column("traits", sa.dialects.postgresql.JSONB, server_default='{"warmth":0.9,"humor":0.7,"curiosity":0.8,"energy":0.6,"verbosity":0.4}'),
        sa.Column("rules", sa.dialects.postgresql.JSONB, server_default='{"safe_topics_only":true,"max_response_sentences":4,"always_encourage":true}'),
        sa.Column("favorite_modes", sa.dialects.postgresql.JSONB, server_default='["default","bedtime","homework","creative"]'),
        sa.Column("active_mode", sa.String(64), server_default="default"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── jobs ──
    op.create_table(
        "jobs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("payload", sa.dialects.postgresql.JSONB, server_default="{}"),
        sa.Column("result", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("attempts", sa.Integer, server_default="0"),
        sa.Column("max_attempts", sa.Integer, server_default="3"),
        sa.Column("locked_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_jobs_status_pending", "jobs", ["status"], postgresql_where=sa.text("status = 'pending'"))

    # ── events ──
    op.create_table(
        "events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("level", sa.String(16), server_default="info"),
        sa.Column("source", sa.String(128), nullable=True),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("metadata", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_events_type", "events", ["event_type"])


def downgrade() -> None:
    for table in [
        "events", "jobs", "bot_profiles", "user_profiles",
        "memory_embeddings", "memories", "interactions",
        "conversations", "devices", "users",
    ]:
        op.drop_table(table)
