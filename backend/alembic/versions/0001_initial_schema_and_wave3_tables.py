"""Initial schema + Wave 3 tables (failed_ingestion, app_config)

Revision ID: 0001
Revises: None
Create Date: 2026-03-14

Wave 3 Design Decision:
    Alembic replaces ad-hoc schema creation via init.sql at the app level.
    init.sql is still mounted in Docker for Postgres first-boot (fresh volume),
    but the application startup now calls `alembic upgrade head` to ensure
    all migrations are applied to an existing database.

    This migration is written with IF NOT EXISTS everywhere so it is safe to
    run against a database that already has the legacy schema.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply the full schema including two new Wave 3 tables."""

    # ── Existing tables (safe with IF NOT EXISTS) ─────────────────────────────

    op.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id SERIAL PRIMARY KEY,
            team_id INTEGER UNIQUE NOT NULL,
            abbreviation VARCHAR(10) NOT NULL,
            full_name VARCHAR(100) NOT NULL,
            city VARCHAR(50),
            conference VARCHAR(10),
            division VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id SERIAL PRIMARY KEY,
            player_id INTEGER UNIQUE NOT NULL,
            full_name VARCHAR(100) NOT NULL,
            team_id INTEGER REFERENCES teams(team_id),
            position VARCHAR(10),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id SERIAL PRIMARY KEY,
            game_id VARCHAR(20) UNIQUE NOT NULL,
            game_date DATE NOT NULL,
            season VARCHAR(10) NOT NULL,
            home_team_id INTEGER REFERENCES teams(team_id),
            away_team_id INTEGER REFERENCES teams(team_id),
            home_score INTEGER,
            away_score INTEGER,
            winner_team_id INTEGER REFERENCES teams(team_id),
            is_completed BOOLEAN DEFAULT FALSE,
            venue VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS team_game_stats (
            id SERIAL PRIMARY KEY,
            game_id VARCHAR(20) REFERENCES matches(game_id),
            team_id INTEGER REFERENCES teams(team_id),
            points INTEGER,
            rebounds INTEGER,
            assists INTEGER,
            steals INTEGER,
            blocks INTEGER,
            turnovers INTEGER,
            field_goal_pct DECIMAL(5,3),
            three_point_pct DECIMAL(5,3),
            free_throw_pct DECIMAL(5,3),
            offensive_rating DECIMAL(6,2),
            defensive_rating DECIMAL(6,2),
            pace DECIMAL(6,2),
            effective_fg_pct DECIMAL(5,3),
            true_shooting_pct DECIMAL(5,3),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (game_id, team_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS player_game_stats (
            id SERIAL PRIMARY KEY,
            game_id VARCHAR(20) REFERENCES matches(game_id),
            player_id INTEGER REFERENCES players(player_id),
            team_id INTEGER REFERENCES teams(team_id),
            minutes DECIMAL(5,2),
            points INTEGER,
            rebounds INTEGER,
            assists INTEGER,
            steals INTEGER,
            blocks INTEGER,
            turnovers INTEGER,
            personal_fouls INTEGER,
            field_goals_made INTEGER,
            field_goals_attempted INTEGER,
            field_goal_pct DECIMAL(5,3),
            three_points_made INTEGER,
            three_points_attempted INTEGER,
            three_point_pct DECIMAL(5,3),
            free_throws_made INTEGER,
            free_throws_attempted INTEGER,
            free_throw_pct DECIMAL(5,3),
            plus_minus INTEGER,
            fantasy_points DECIMAL(6,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (game_id, player_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS player_season_stats (
            id SERIAL PRIMARY KEY,
            player_id INTEGER REFERENCES players(player_id),
            season VARCHAR(10) NOT NULL,
            team_id INTEGER REFERENCES teams(team_id),
            games_played INTEGER,
            wins INTEGER,
            losses INTEGER,
            win_pct DECIMAL(5,3),
            minutes DECIMAL(8,2),
            points DECIMAL(8,2),
            rebounds DECIMAL(8,2),
            assists DECIMAL(8,2),
            steals DECIMAL(8,2),
            blocks DECIMAL(8,2),
            turnovers DECIMAL(8,2),
            field_goal_pct DECIMAL(5,3),
            three_point_pct DECIMAL(5,3),
            free_throw_pct DECIMAL(5,3),
            plus_minus DECIMAL(8,2),
            fantasy_points DECIMAL(8,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (player_id, season)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS match_features (
            id SERIAL PRIMARY KEY,
            game_id VARCHAR(20) REFERENCES matches(game_id),
            team_id INTEGER REFERENCES teams(team_id),
            win_pct_last_5 DECIMAL(5,3),
            win_pct_last_10 DECIMAL(5,3),
            avg_point_diff_last_5 DECIMAL(6,2),
            avg_point_diff_last_10 DECIMAL(6,2),
            h2h_win_pct DECIMAL(5,3),
            h2h_avg_margin DECIMAL(6,2),
            days_rest INTEGER,
            is_back_to_back BOOLEAN DEFAULT FALSE,
            is_home BOOLEAN,
            avg_off_rating_last_5 DECIMAL(6,2),
            avg_def_rating_last_5 DECIMAL(6,2),
            avg_pace_last_5 DECIMAL(6,2),
            avg_efg_last_5 DECIMAL(5,3),
            current_streak INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (game_id, team_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id SERIAL PRIMARY KEY,
            game_id VARCHAR(20) REFERENCES matches(game_id),
            model_name VARCHAR(50) NOT NULL,
            home_win_prob DECIMAL(5,4),
            away_win_prob DECIMAL(5,4),
            confidence DECIMAL(5,4),
            shap_factors JSONB,
            predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            was_correct BOOLEAN,
            UNIQUE (game_id, model_name)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS bets (
            id SERIAL PRIMARY KEY,
            game_id VARCHAR(20) REFERENCES matches(game_id),
            bet_type VARCHAR(50) NOT NULL,
            selection VARCHAR(100) NOT NULL,
            odds DECIMAL(8,4) NOT NULL,
            stake DECIMAL(10,2) NOT NULL,
            kelly_fraction DECIMAL(5,4),
            model_probability DECIMAL(5,4),
            result VARCHAR(20),
            pnl DECIMAL(10,2),
            placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            settled_at TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_audit (
            id SERIAL PRIMARY KEY,
            sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            module VARCHAR(50) NOT NULL,
            status VARCHAR(20) NOT NULL,
            records_processed INTEGER DEFAULT 0,
            records_inserted INTEGER DEFAULT 0,
            errors TEXT,
            details JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS intelligence_audit (
            id SERIAL PRIMARY KEY,
            run_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            module VARCHAR(50) NOT NULL,
            status VARCHAR(20) NOT NULL,
            records_processed INTEGER DEFAULT 0,
            errors TEXT,
            details JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS mlops_monitoring_snapshot (
            id SERIAL PRIMARY KEY,
            snapshot_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            season VARCHAR(10) NOT NULL,
            evaluated_predictions INTEGER DEFAULT 0,
            accuracy DECIMAL(6,4),
            brier_score DECIMAL(6,4),
            game_data_freshness_days INTEGER,
            pipeline_freshness_days INTEGER,
            alert_count INTEGER DEFAULT 0,
            details JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS retrain_jobs (
            id SERIAL PRIMARY KEY,
            season VARCHAR(10) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'queued',
            trigger_source VARCHAR(40) NOT NULL DEFAULT 'policy',
            reasons JSONB,
            metrics JSONB,
            thresholds JSONB,
            artifact_snapshot JSONB,
            rollback_plan JSONB,
            run_details JSONB,
            error TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Wave 3 NEW tables ─────────────────────────────────────────────────────

    op.execute("""
        CREATE TABLE IF NOT EXISTS failed_ingestion (
            id SERIAL PRIMARY KEY,
            entity_type VARCHAR(30) NOT NULL,
            raw_payload JSONB NOT NULL,
            validation_errors JSONB NOT NULL,
            source_module VARCHAR(60) NOT NULL DEFAULT 'ingestion',
            attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS app_config (
            key VARCHAR(120) PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Seed default config values ────────────────────────────────────────────
    op.execute("""
        INSERT INTO app_config (key, value, description)
        VALUES
            ('active_model_path', '', 'Path to the active model artifact directory. Empty = use latest from disk.'),
            ('rag_min_similarity', '0.4', 'Minimum cosine similarity for RAG context inclusion.'),
            ('mlops_accuracy_threshold', '0.55', 'Minimum prediction accuracy before retrain is triggered.'),
            ('mlops_max_brier', '0.25', 'Maximum Brier score before retrain is triggered.'),
            ('psi_drift_threshold', '0.2', 'PSI score above which feature drift is flagged as significant.')
        ON CONFLICT (key) DO NOTHING
    """)

    # ── Indexes ───────────────────────────────────────────────────────────────
    op.execute("CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(game_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_matches_season ON matches(season)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_team_stats_game ON team_game_stats(game_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_player_stats_game ON player_game_stats(game_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_player_season ON player_season_stats(season)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_features_game ON match_features(game_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_predictions_game ON predictions(game_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_bets_game ON bets(game_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_bets_result ON bets(result)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_audit_module ON pipeline_audit(module)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_audit_status ON pipeline_audit(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_intelligence_audit_module ON intelligence_audit(module)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_intelligence_audit_status ON intelligence_audit(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mlops_snapshot_season_time ON mlops_monitoring_snapshot(season, snapshot_time DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_retrain_jobs_season_status_time ON retrain_jobs(season, status, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_failed_ingestion_entity_type ON failed_ingestion(entity_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_failed_ingestion_attempted_at ON failed_ingestion(attempted_at DESC)")


def downgrade() -> None:
    """Drop Wave 3-only tables; leave legacy tables intact."""
    op.execute("DROP TABLE IF EXISTS app_config CASCADE")
    op.execute("DROP TABLE IF EXISTS failed_ingestion CASCADE")
