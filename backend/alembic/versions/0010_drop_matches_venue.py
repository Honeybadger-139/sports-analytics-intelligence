"""Drop matches.venue column (SCR-348)

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-29

WHY:
    The venue column was added to matches but has never been populated.
    ESPN's scoreboard endpoint omits venue; fetching it from the game summary
    endpoint for every historical row (1,105+ games) is wasteful.  Venue
    is not used by any ML feature, RAG pipeline, or Scribble explorer view.
    Dropping it keeps the schema honest.
"""

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("ALTER TABLE matches DROP COLUMN IF EXISTS venue")


def downgrade() -> None:
    op.execute("ALTER TABLE matches ADD COLUMN IF NOT EXISTS venue VARCHAR(200)")
