"""player_game_stats: replace NULLs with 0 and add match_played column (SCR-348)

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-29

WHY:
    Some player_game_stats rows have NULL for integer stat columns because
    ESPN's boxscore occasionally omits a stat label.  NULL stats cause
    aggregation queries to silently exclude players and confuse ML features.
    Replacing with 0 is semantically correct: a missing value in a completed
    game means the player recorded zero of that stat (or the data is unknown,
    but 0 is a better default than NULL for numeric features).

    match_played boolean:
        true  — player had recorded minutes (> 0), i.e. they actually played
        false — player had a game row but no minutes (should be rare after
                SCR-344 DNP fix, but can occur for older historical data)

    Shooting percentages (field_goal_pct, three_point_pct, free_throw_pct)
    are intentionally left as-is (NULL = no attempts is semantically correct).
"""

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    # Add match_played column
    op.execute("""
        ALTER TABLE player_game_stats
        ADD COLUMN IF NOT EXISTS match_played BOOLEAN NOT NULL DEFAULT FALSE
    """)

    # Replace NULLs with 0 for integer/float stat columns
    op.execute("""
        UPDATE player_game_stats SET
            points                 = COALESCE(points, 0),
            rebounds               = COALESCE(rebounds, 0),
            assists                = COALESCE(assists, 0),
            steals                 = COALESCE(steals, 0),
            blocks                 = COALESCE(blocks, 0),
            turnovers              = COALESCE(turnovers, 0),
            personal_fouls         = COALESCE(personal_fouls, 0),
            field_goals_made       = COALESCE(field_goals_made, 0),
            field_goals_attempted  = COALESCE(field_goals_attempted, 0),
            three_points_made      = COALESCE(three_points_made, 0),
            three_points_attempted = COALESCE(three_points_attempted, 0),
            free_throws_made       = COALESCE(free_throws_made, 0),
            free_throws_attempted  = COALESCE(free_throws_attempted, 0),
            plus_minus             = COALESCE(plus_minus, 0)
    """)

    # Set match_played based on whether minutes were recorded
    op.execute("""
        UPDATE player_game_stats
        SET match_played = (minutes IS NOT NULL AND minutes > 0)
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE player_game_stats DROP COLUMN IF EXISTS match_played")
    # NULLs are not recoverable — leaving stats at 0 is acceptable
