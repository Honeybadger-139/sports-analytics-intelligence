"""Add position column to players table (SCR-332)

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-27

WHY:
    ESPN roster endpoint provides player positions (PG/SG/SF/PF/C) for every
    active NBA player. Adding a VARCHAR(5) position column to the players table
    surfaces this data in player stats views and downstream ML feature engineering
    (e.g. position-adjusted efficiency metrics, positional matchup features).

    This column is NULLABLE so that:
      1. Existing rows migrated from the old nba_api pipeline are not invalidated.
      2. The ESPN ingestion pipeline can backfill positions on first run without
         a separate migration step.

COLUMN ADDED:
    players.position  VARCHAR(5)  NULLABLE
    Expected values:  'PG', 'SG', 'SF', 'PF', 'C'
    Edge cases:       'G', 'F', 'G-F', 'F-C' (ESPN flex positions) — kept as-is,
                      hence VARCHAR(5) rather than a constrained ENUM.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column(
            "position",
            sa.String(5),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("players", "position")
