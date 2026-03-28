"""Backfill conference and division for all 30 NBA teams (SCR-347)

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-29

WHY:
    The teams table had conference/division as NULL because:
    1. ESPN bulk teams endpoint never returns conference/division strings
    2. The static map in espn_transformer.py was added after initial ingestion
    3. ingest_teams was not called during incremental runs (fixed in SCR-345)

    This migration directly writes the correct conference/division for all
    30 teams using the same hardcoded map as the transformer, so the data
    is populated immediately on deploy without waiting for an ingestion run.

    Also corrects Dallas Mavericks (team_id=6) from Northwest → Southwest.
"""

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

from alembic import op


# ESPN team_id → (conference, division)
_TEAM_MAP = [
    # Eastern Conference
    (1,  "East", "Southeast"),   # Atlanta Hawks
    (2,  "East", "Atlantic"),    # Boston Celtics
    (17, "East", "Atlantic"),    # Brooklyn Nets
    (30, "East", "Southeast"),   # Charlotte Hornets
    (4,  "East", "Central"),     # Chicago Bulls
    (5,  "East", "Central"),     # Cleveland Cavaliers
    (8,  "East", "Central"),     # Detroit Pistons
    (11, "East", "Central"),     # Indiana Pacers
    (14, "East", "Southeast"),   # Miami Heat
    (15, "East", "Central"),     # Milwaukee Bucks
    (18, "East", "Atlantic"),    # New York Knicks
    (19, "East", "Southeast"),   # Orlando Magic
    (20, "East", "Atlantic"),    # Philadelphia 76ers
    (28, "East", "Atlantic"),    # Toronto Raptors
    (27, "East", "Southeast"),   # Washington Wizards
    # Western Conference
    (6,  "West", "Southwest"),   # Dallas Mavericks  ← was "Northwest", corrected
    (7,  "West", "Northwest"),   # Denver Nuggets
    (9,  "West", "Pacific"),     # Golden State Warriors
    (10, "West", "Southwest"),   # Houston Rockets
    (12, "West", "Pacific"),     # LA Clippers
    (13, "West", "Pacific"),     # Los Angeles Lakers
    (29, "West", "Southwest"),   # Memphis Grizzlies
    (16, "West", "Northwest"),   # Minnesota Timberwolves
    (3,  "West", "Southwest"),   # New Orleans Pelicans
    (25, "West", "Northwest"),   # Oklahoma City Thunder
    (21, "West", "Pacific"),     # Phoenix Suns
    (22, "West", "Northwest"),   # Portland Trail Blazers
    (23, "West", "Pacific"),     # Sacramento Kings
    (24, "West", "Southwest"),   # San Antonio Spurs
    (26, "West", "Northwest"),   # Utah Jazz
]


def upgrade() -> None:
    for team_id, conference, division in _TEAM_MAP:
        op.execute(
            f"UPDATE teams SET conference = '{conference}', division = '{division}' "
            f"WHERE team_id = {team_id}"
        )


def downgrade() -> None:
    op.execute("UPDATE teams SET conference = NULL, division = NULL")
