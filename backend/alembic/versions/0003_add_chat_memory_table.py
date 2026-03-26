"""Add chat_sessions and chat_messages tables for PostgreSQL-backed memory

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-26

WHY:
    LangGraph chatbot needs persistent conversation memory that survives
    Cloud Run container restarts. Instead of in-memory lists (lost on
    restart) or Redis (extra infra cost), we store chat history in the
    same PostgreSQL instance as game data.

TABLES:
    chat_sessions  — one row per browser session (session_id = UUID from frontend)
    chat_messages  — one row per message turn (user + assistant alternating)

INDEXES:
    chat_messages.session_id + created_at — the primary access pattern
    chat_sessions.last_active_at — for cleanup queries (expiring old sessions)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── chat_sessions ─────────────────────────────────────────────────────────
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("sport", sa.Text(), nullable=False, server_default="nba"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_active_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_chat_sessions_session_id"),
    )
    op.create_index(
        "ix_chat_sessions_last_active_at",
        "chat_sessions",
        ["last_active_at"],
    )

    # ── chat_messages ─────────────────────────────────────────────────────────
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),          # 'user' | 'assistant'
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["chat_sessions.session_id"],
            name="fk_chat_messages_session_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_chat_messages_session_created",
        "chat_messages",
        ["session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_session_created", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_last_active_at", table_name="chat_sessions")
    op.drop_table("chat_sessions")
