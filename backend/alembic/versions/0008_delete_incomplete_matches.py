"""Delete incomplete (future/scheduled) matches and their stats (SCR-346)

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-29

WHY:
    The incremental ingestion pipeline previously fetched a 3-day window
    (yesterday + today + tomorrow) and wrote scheduled future games to the
    matches table with is_completed=false and NULL scores. This polluted the
    Scribble explorer and the DB with rows that have no real data.

    The pipeline has been updated to only persist completed games going
    forward. This migration cleans up all pre-existing incomplete rows and
    their associated stats records (cascade order: stats first, then matches).

ROWS DELETED:
    - player_game_stats  WHERE game_id IN (incomplete matches)
    - team_game_stats    WHERE game_id IN (incomplete matches)
    - matches            WHERE is_completed = false
"""

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        DELETE FROM player_game_stats
        WHERE game_id IN (
            SELECT game_id FROM matches WHERE is_completed = false
        )
    """)
    op.execute("""
        DELETE FROM team_game_stats
        WHERE game_id IN (
            SELECT game_id FROM matches WHERE is_completed = false
        )
    """)
    op.execute("DELETE FROM matches WHERE is_completed = false")


def downgrade() -> None:
    # Deleted rows are not recoverable via downgrade — data will be
    # re-ingested by the next incremental pipeline run.
    pass
