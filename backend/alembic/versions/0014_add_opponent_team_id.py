"""Add opponent_team_id to team_game_stats and player_game_stats (SCR-349)

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-29

WHY:
    Without opponent_team_id, querying "who did this team/player play against"
    requires joining to the matches table. Adding the column directly on the
    stats tables makes per-row context self-contained — critical for ML feature
    engineering (e.g. opponent strength, head-to-head records) and Scribble
    explorer views.

BACKFILL LOGIC:
    team_game_stats:
        opponent = the other team in that game (from matches home/away columns)
        if team_id = home_team_id  → opponent = away_team_id
        if team_id = away_team_id  → opponent = home_team_id

    player_game_stats:
        same derivation — join through team_game_stats or matches to find
        the team that is NOT the player's team_id for that game_id.
"""

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    # --- team_game_stats ---
    op.execute("""
        ALTER TABLE team_game_stats
        ADD COLUMN IF NOT EXISTS opponent_team_id INTEGER REFERENCES teams(team_id)
    """)
    op.execute("""
        UPDATE team_game_stats tgs
        SET opponent_team_id = CASE
            WHEN tgs.team_id = m.home_team_id THEN m.away_team_id
            ELSE m.home_team_id
        END
        FROM matches m
        WHERE tgs.game_id = m.game_id
    """)

    # --- player_game_stats ---
    op.execute("""
        ALTER TABLE player_game_stats
        ADD COLUMN IF NOT EXISTS opponent_team_id INTEGER REFERENCES teams(team_id)
    """)
    op.execute("""
        UPDATE player_game_stats pgs
        SET opponent_team_id = CASE
            WHEN pgs.team_id = m.home_team_id THEN m.away_team_id
            ELSE m.home_team_id
        END
        FROM matches m
        WHERE pgs.game_id = m.game_id
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE team_game_stats DROP COLUMN IF EXISTS opponent_team_id")
    op.execute("ALTER TABLE player_game_stats DROP COLUMN IF EXISTS opponent_team_id")
