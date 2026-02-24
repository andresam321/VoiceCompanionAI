"""add fields

Revision ID: a36252f2dcbb
Revises: e7cababcdc36
Create Date: 2026-02-24 06:56:51.821529

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a36252f2dcbb'
down_revision = 'e7cababcdc36'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- bot_profiles.wake_words ----
    op.add_column(
        'bot_profiles',
        sa.Column('wake_words', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.execute("UPDATE bot_profiles SET wake_words='[\"pal\"]'::jsonb WHERE wake_words IS NULL")
    op.alter_column('bot_profiles', 'wake_words', nullable=False)

    # ---- jobs.locked_at ----
    op.add_column('jobs', sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True))

    # ---- jobs.run_after ----
    op.add_column('jobs', sa.Column('run_after', sa.DateTime(timezone=True), nullable=True))
    op.execute('UPDATE jobs SET run_after=NOW() WHERE run_after IS NULL')
    op.alter_column('jobs', 'run_after', nullable=False)

    # ---- jobs.trace_id ----
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')
    op.add_column('jobs', sa.Column('trace_id', sa.UUID(), nullable=True))
    op.execute('UPDATE jobs SET trace_id=gen_random_uuid() WHERE trace_id IS NULL')
    op.alter_column('jobs', 'trace_id', nullable=False)


def downgrade() -> None:
    op.drop_column('jobs', 'trace_id')
    op.drop_column('jobs', 'run_after')
    op.drop_column('jobs', 'locked_at')
    op.drop_column('bot_profiles', 'wake_words')
