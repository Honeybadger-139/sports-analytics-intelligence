"""Delete stub player records and cascade their stats (SCR-348)

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-29

WHY:
    When the ESPN bulk roster endpoint returns a player ID whose biographical
    data hasn't loaded yet, our transformer writes a placeholder row:
        full_name = "Player <espn_id>", is_active = false
    These stub records pollute any ML model trained on player data.
    They are all is_active=false, so no active game references them.

    Cascade order: delete stats first (FK), then players.
    If a real player with the same ESPN ID appears in a future game, the
    ingestion pipeline will upsert their real name at that point.

ROWS DELETED:
    - player_game_stats  WHERE player_id IN (stub players)
    - player_season_stats WHERE player_id IN (stub players)
    - players            WHERE full_name LIKE 'Player %'
"""

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        DELETE FROM player_game_stats
        WHERE player_id IN (
            SELECT player_id FROM players WHERE full_name LIKE 'Player %'
        )
    """)
    op.execute("""
        DELETE FROM player_season_stats
        WHERE player_id IN (
            SELECT player_id FROM players WHERE full_name LIKE 'Player %'
        )
    """)
    op.execute("DELETE FROM players WHERE full_name LIKE 'Player %'")


def downgrade() -> None:
    # Deleted stub records are not recoverable — they will be re-created
    # automatically by the next ingestion run if ESPN still serves placeholders.
    pass
