"""Replace NULL shooting pct columns with 0 in player_game_stats and player_season_stats (SCR-350)

Revision ID: 0015
Revises: 0014
Create Date: 2026-03-29

WHY:
    Migration 0012/0013 left shooting percentage columns (field_goal_pct,
    three_point_pct, free_throw_pct) as NULL when a player had 0 attempts —
    semantically correct but practically breaks ML models, which cannot
    handle NaN/NULL in feature vectors.  Setting to 0.0 is the standard
    ML convention for "no attempts recorded".
"""

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        UPDATE player_game_stats SET
            field_goal_pct   = COALESCE(field_goal_pct, 0),
            three_point_pct  = COALESCE(three_point_pct, 0),
            free_throw_pct   = COALESCE(free_throw_pct, 0),
            fantasy_points   = COALESCE(fantasy_points, 0)
    """)
    op.execute("""
        UPDATE player_season_stats SET
            field_goal_pct   = COALESCE(field_goal_pct, 0),
            three_point_pct  = COALESCE(three_point_pct, 0),
            free_throw_pct   = COALESCE(free_throw_pct, 0)
    """)


def downgrade() -> None:
    pass
