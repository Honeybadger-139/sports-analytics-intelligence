"""Add ab_experiments and causal_results tables for statistics module

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-26

WHY:
    The statistics module (Module 6.4) needs persistent storage for:
    - A/B experiment definitions and results (SPRT model comparisons)
    - Causal inference DiD results (home court advantage analysis)
    - Bayesian rating snapshots (team strength over time)

TABLES:
    ab_experiments       — one row per model comparison experiment
    causal_results       — DiD analysis results per season range
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── ab_experiments ────────────────────────────────────────────────────────
    op.create_table(
        "ab_experiments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("experiment_name", sa.Text(), nullable=False),
        sa.Column("model_a", sa.Text(), nullable=False),
        sa.Column("model_b", sa.Text(), nullable=False),
        sa.Column("n_observations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model_a_accuracy", sa.Numeric(6, 4), nullable=True),
        sa.Column("model_b_accuracy", sa.Numeric(6, 4), nullable=True),
        sa.Column("decision", sa.Text(), nullable=True),   # 'accept_h0' | 'accept_h1' | 'continue'
        sa.Column("winner", sa.Text(), nullable=True),
        sa.Column("p_value", sa.Numeric(8, 6), nullable=True),
        sa.Column("log_likelihood_ratio", sa.Numeric(10, 6), nullable=True),
        sa.Column("alpha", sa.Numeric(4, 3), nullable=True),
        sa.Column("min_detectable_effect", sa.Numeric(4, 3), nullable=True),
        sa.Column("season", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ab_experiments_name", "ab_experiments", ["experiment_name"])

    # ── causal_results ────────────────────────────────────────────────────────
    op.create_table(
        "causal_results",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("analysis_type", sa.Text(), nullable=False, server_default="home_court_did"),
        sa.Column("did_estimate", sa.Numeric(8, 6), nullable=True),
        sa.Column("p_value", sa.Numeric(8, 6), nullable=True),
        sa.Column("ci_lower", sa.Numeric(8, 6), nullable=True),
        sa.Column("ci_upper", sa.Numeric(8, 6), nullable=True),
        sa.Column("is_significant", sa.Boolean(), nullable=True),
        sa.Column("n_games", sa.Integer(), nullable=True),
        sa.Column("seasons_included", sa.Text(), nullable=True),  # JSON list
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_index("ix_ab_experiments_name", table_name="ab_experiments")
    op.drop_table("ab_experiments")
    op.drop_table("causal_results")
