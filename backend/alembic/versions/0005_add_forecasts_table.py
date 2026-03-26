"""Add team_forecasts table for time-series module

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-26

WHY:
    Store time-series forecast results so the frontend can render trend charts
    without re-computing on every request. Forecasts are refreshed by an Airflow
    DAG every 6 hours (same cadence as the RAG refresh pipeline).

TABLE:
    team_forecasts — one row per team per forecast date
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "team_forecasts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("team_name", sa.Text(), nullable=False),
        sa.Column("season", sa.Text(), nullable=False),
        sa.Column("forecast_date", sa.Date(), nullable=False),       # date being forecast
        sa.Column("prophet_forecast", sa.Numeric(6, 4), nullable=True),
        sa.Column("arima_forecast", sa.Numeric(6, 4), nullable=True),
        sa.Column("ci_lower", sa.Numeric(6, 4), nullable=True),
        sa.Column("ci_upper", sa.Numeric(6, 4), nullable=True),
        sa.Column("momentum_score", sa.Numeric(6, 4), nullable=True),
        sa.Column("momentum_trend", sa.Text(), nullable=True),       # 'hot' | 'cold' | 'neutral'
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_name", "season", "forecast_date", name="uq_team_forecast_date"),
    )
    op.create_index(
        "ix_team_forecasts_team_season",
        "team_forecasts",
        ["team_name", "season"],
    )


def downgrade() -> None:
    op.drop_index("ix_team_forecasts_team_season", table_name="team_forecasts")
    op.drop_table("team_forecasts")
