"""player_season_stats: replace NULLs with 0 and add has_played column (SCR-348)

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-29

WHY:
    The NBA stats API (nba_api LeagueDashPlayerStats) returns NaN for players
    who played very few games or were injured early in the season.  These NaNs
    become NULL in the DB, which makes aggregation and ML feature queries
    silently skip those players.

    has_played boolean:
        true  — player appeared in at least 1 game (games_played >= 1)
        false — player is on a roster but has not played yet this season

    Shooting percentages (field_goal_pct, three_point_pct, free_throw_pct)
    are intentionally left as-is (NULL = no attempts taken).
"""

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    # Add has_played column
    op.execute("""
        ALTER TABLE player_season_stats
        ADD COLUMN IF NOT EXISTS has_played BOOLEAN NOT NULL DEFAULT FALSE
    """)

    # Replace NULLs with 0 for numeric stat columns
    op.execute("""
        UPDATE player_season_stats SET
            minutes       = COALESCE(minutes, 0),
            points        = COALESCE(points, 0),
            rebounds      = COALESCE(rebounds, 0),
            assists       = COALESCE(assists, 0),
            steals        = COALESCE(steals, 0),
            blocks        = COALESCE(blocks, 0),
            turnovers     = COALESCE(turnovers, 0),
            plus_minus    = COALESCE(plus_minus, 0),
            fantasy_points = COALESCE(fantasy_points, 0)
    """)

    # Set has_played
    op.execute("""
        UPDATE player_season_stats
        SET has_played = (games_played >= 1)
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE player_season_stats DROP COLUMN IF EXISTS has_played")
