"""Add pre-game prediction columns to predictions table (SCR-331)

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-27

WHY:
    SCR-331 introduced a two-layer prediction system:
      - Layer 1: ML models run before tip-off (is_pre_game=True)
      - Layer 2: RAG news enrichment updates confidence post-refresh

    Three new columns are needed on the `predictions` table:
      - is_pre_game   BOOLEAN  — True when prediction was made before game start
      - news_context  JSONB    — RAG-derived factors (injuries, lineup, form)
      - enriched_at   TIMESTAMP — When Gemini enrichment last ran for this prediction

    Without these columns the /predictions/today endpoint crashes with
    "column p.is_pre_game does not exist" (psycopg2.errors.UndefinedColumn).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use raw SQL with IF NOT EXISTS so this migration is safe to re-run if the
    # columns were already added manually by ensure_pre_game_columns() before
    # Alembic tracked them. op.add_column() has no IF NOT EXISTS equivalent and
    # raises DuplicateColumn on an already-existing column.
    op.execute(
        "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS "
        "is_pre_game BOOLEAN DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS news_context JSONB"
    )
    op.execute(
        "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS enriched_at TIMESTAMP"
    )


def downgrade() -> None:
    op.drop_column("predictions", "enriched_at")
    op.drop_column("predictions", "news_context")
    op.drop_column("predictions", "is_pre_game")
