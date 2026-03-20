"""
Feature Engineering Module
==========================

🎓 WHAT IS FEATURE ENGINEERING?
    Feature engineering is the process of transforming raw data into meaningful
    inputs for ML models. It's often said that "feature engineering is 80% of
    the work in ML" — and this is what separates senior Data Scientists from
    juniors.

    Raw data: "Lakers scored 110 points on Feb 20"
    Engineered feature: "Lakers' rolling 5-game win% is 0.6, they're 3-1 at
    home in the last 4, and their opponent has a 2-game losing streak"

🧠 WHY IT MATTERS:
    A model can only learn from the patterns in its features. If we give it
    raw game scores, it doesn't understand "momentum" or "fatigue." But if
    we compute rolling win%, rest days, and streaks — those features ENCODE
    the patterns that predict future outcomes.

💡 INTERVIEW ANGLE:
    Junior: "I used the raw data columns as features"
    Senior: "I engineered temporal features using rolling windows to capture
    team momentum, computed head-to-head features for matchup-specific edges,
    and added rest-day features to model fatigue effects. I used PostgreSQL
    window functions for efficient computation."

    Awe moment: "I discovered that the rest-days feature had a non-linear
    relationship with win probability — teams with 1-2 days rest performed
    best, but 3+ days showed diminishing returns (rustiness effect)."

FEATURES WE COMPUTE:
    1. Rolling Win % (5 and 10 games) — team momentum
    2. Rolling Point Differential — margin of victory/loss trend
    3. Head-to-Head Win % — matchup-specific edge
    4. H2H Average Margin — how dominant is the matchup historically
    5. Rest Days — fatigue factor
    6. Back-to-Back Flag — extreme fatigue
    7. Home/Away — venue advantage
    8. Rolling Offensive Rating — points per 100 possessions (efficiency)
    9. Rolling Defensive Rating — opponent points per 100 possessions
    10. Current Streak — hot/cold streak signal
"""

import logging
from logging.handlers import RotatingFileHandler
import os
import json
import time
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from src import config
from src.data.audit_store import (
    ensure_pipeline_audit_table,
    is_missing_pipeline_audit_error,
)

load_dotenv()

# Ensure logs directory exists
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
PIPE_LOG_FILE = os.path.join(LOG_DIR, "pipeline.log")
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3

# Configure logging (Dual Handler: Console + File)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            PIPE_LOG_FILE,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
        ),
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"📝 Logging to console and {PIPE_LOG_FILE}")


def record_audit(engine, module: str, status: str, processed: int = 0, inserted: int = 0, errors: str = None, details: dict = None):
    """
    Record pipeline results into the pipeline_audit table.
    """
    logger.info(f"📊 Recording audit log for {module} (status: {status})...")
    payload = {
        "module": module,
        "status": status,
        "processed": processed,
        "inserted": inserted,
        "errors": errors,
        "details": json.dumps(details) if details else None
    }
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO pipeline_audit (module, status, records_processed, records_inserted, errors, details)
                    VALUES (:module, :status, :processed, :inserted, :errors, :details)
                """),
                payload
            )
    except Exception as e:
        if is_missing_pipeline_audit_error(e):
            logger.warning("  ⚠️ pipeline_audit missing. Bootstrapping table and retrying once...")
            try:
                ensure_pipeline_audit_table(engine)
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            INSERT INTO pipeline_audit (module, status, records_processed, records_inserted, errors, details)
                            VALUES (:module, :status, :processed, :inserted, :errors, :details)
                        """),
                        payload
                    )
                logger.info("  ✅ pipeline_audit bootstrapped and audit log recorded.")
                return
            except Exception as retry_err:
                logger.error(f"  ❌ Failed to bootstrap/retry audit log: {retry_err}")
                return
        logger.error(f"  ❌ Failed to record audit log: {e}")


def get_engine():
    """Create SQLAlchemy engine from centralized config."""
    return create_engine(config.DATABASE_URL)


def ensure_h2h_data_available_column(engine):
    """Add the H2H availability flag column if the table is behind the code."""
    if not hasattr(engine, "begin"):
        logger.warning(
            json.dumps(
                {
                    "schema_update": "skipped",
                    "reason": "engine_missing_begin",
                    "table": "match_features",
                },
                default=str,
            )
        )
        return

    with engine.begin() as conn:
        conn.execute(text("""
            ALTER TABLE match_features
            ADD COLUMN IF NOT EXISTS h2h_data_available INTEGER DEFAULT 0
        """))


def validate_raw_data(engine, seasons):
    """
    Validate raw tables before computing features.

    Returns a summary dict when validation passes. On failure, logs a
    structured error payload, writes a validation audit row, and raises.
    """
    if not seasons:
        seasons = [config.CURRENT_SEASON]

    if not hasattr(engine, "connect"):
        payload = {
            "validation": "skipped",
            "reason": "engine_missing_connect",
            "seasons": seasons,
        }
        logger.warning(json.dumps(payload, default=str))
        return payload

    season_stats = []
    failures = []
    current_date = datetime.utcnow().date()

    with engine.connect() as conn:
        for season in seasons:
            match_count = int(conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM matches
                    WHERE season = :season
                """),
                {"season": season},
            ).scalar() or 0)

            team_stats_count = int(conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM team_game_stats tgs
                    JOIN matches m ON m.game_id = tgs.game_id
                    WHERE m.season = :season
                """),
                {"season": season},
            ).scalar() or 0)

            max_game_date = conn.execute(
                text("""
                    SELECT MAX(m.game_date)
                    FROM matches m
                    WHERE m.season = :season
                """),
                {"season": season},
            ).scalar()

            null_counts = {
                "game_date": int(conn.execute(
                    text("""
                        SELECT COUNT(*)
                        FROM matches
                        WHERE season = :season AND game_date IS NULL
                    """),
                    {"season": season},
                ).scalar() or 0),
                "home_team_id": int(conn.execute(
                    text("""
                        SELECT COUNT(*)
                        FROM matches
                        WHERE season = :season AND home_team_id IS NULL
                    """),
                    {"season": season},
                ).scalar() or 0),
                "away_team_id": int(conn.execute(
                    text("""
                        SELECT COUNT(*)
                        FROM matches
                        WHERE season = :season AND away_team_id IS NULL
                    """),
                    {"season": season},
                ).scalar() or 0),
                "points": int(conn.execute(
                    text("""
                        SELECT COUNT(*)
                        FROM team_game_stats tgs
                        JOIN matches m ON m.game_id = tgs.game_id
                        WHERE m.season = :season AND tgs.points IS NULL
                    """),
                    {"season": season},
                ).scalar() or 0),
            }

            season_stats.append(
                {
                    "season": season,
                    "matches": match_count,
                    "team_game_stats": team_stats_count,
                    "max_game_date": max_game_date.isoformat() if max_game_date else None,
                    "null_counts": null_counts,
                }
            )

            if match_count < 10:
                failures.append({
                    "reason": "not_enough_matches",
                    "value": {"season": season, "matches": match_count},
                })

            match_denominator = match_count or 1
            team_stats_denominator = team_stats_count or 1
            null_rates = {
                "game_date": null_counts["game_date"] / match_denominator,
                "home_team_id": null_counts["home_team_id"] / match_denominator,
                "away_team_id": null_counts["away_team_id"] / match_denominator,
                "points": null_counts["points"] / team_stats_denominator,
            }
            for column_name, null_rate in null_rates.items():
                if null_rate > 0.15:
                    failures.append({
                        "reason": "critical_null_rate_exceeded",
                        "value": {
                            "season": season,
                            "column": column_name,
                            "null_rate": round(null_rate, 4),
                        },
                    })

            if max_game_date is None:
                failures.append({
                    "reason": "stale_or_missing_game_date",
                    "value": {"season": season, "max_game_date": None},
                })
            else:
                max_game_dt = pd.to_datetime(max_game_date).date()
                if (current_date - max_game_dt).days > 7:
                    failures.append({
                        "reason": "stale_game_data",
                        "value": {
                            "season": season,
                            "max_game_date": max_game_dt.isoformat(),
                            "days_old": (current_date - max_game_dt).days,
                        },
                    })

    if failures:
        payload = {
            "validation": "failed",
            "reason": failures[0]["reason"],
            "value": {
                "season_stats": season_stats,
                "failures": failures,
            },
        }
        logger.error(json.dumps(payload, default=str))
        record_audit(
            engine,
            module="feature_store",
            status="validation_failed",
            processed=season_stats[0]["matches"] if season_stats else 0,
            inserted=season_stats[0]["team_game_stats"] if season_stats else 0,
            errors=failures[0]["reason"],
            details=payload["value"],
        )
        raise ValueError(f"Raw data validation failed: {failures[0]['reason']}")

    payload = {
        "validation": "passed",
        "matches": sum(item["matches"] for item in season_stats),
        "max_date": max(
            (item["max_game_date"] for item in season_stats if item["max_game_date"]),
            default=None,
        ),
        "seasons": seasons,
    }
    logger.info(json.dumps(payload, default=str))
    return payload


def compute_features(engine, season: str = "2025-26"):
    """
    Compute all match features using PostgreSQL window functions.
    
    🎓 WHY POSTGRESQL WINDOW FUNCTIONS?
        We could compute these in Python with pandas, but:
        1. PostgreSQL handles it in-database (no data movement overhead)
        2. Window functions (LAG, AVG OVER, SUM OVER) are DESIGNED for
           exactly this kind of rolling computation
        3. It scales — even with millions of rows, the DB handles it
        4. Your SQL skills from Analytics Engineering shine here!
        
        This is a "Senior Manager" decision: "I pushed computation to the
        database layer to avoid moving large datasets into Python memory,
        which wouldn't scale in production."
    
    🎓 WINDOW FUNCTIONS CRASH COURSE:
        - LAG(col, N) OVER (ORDER BY ...) → get the value from N rows back
        - AVG(col) OVER (ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) → 5-game rolling avg
        - SUM(CASE WHEN ...) → conditional aggregation for win counting
    """
    logger.info(f"⚙️ Computing features for season {season}...")
    
    with engine.begin() as conn:
        # First, clear existing features for this season to recompute
        conn.execute(text("""
            DELETE FROM match_features 
            WHERE game_id IN (SELECT game_id FROM matches WHERE season = :season)
        """), {"season": season})
        
        # Compute all features using a single powerful SQL query
        # This demonstrates advanced SQL: CTEs, window functions, self-joins
        conn.execute(text("""
            WITH team_games AS (
                /*
                 * Step 1: Build a unified view of each team's games
                 * Each row = one team's perspective on one game
                 * We need this because matches table has home/away columns,
                 * but we want a team-centric view
                 */
                SELECT 
                    m.game_id,
                    m.game_date,
                    m.season,
                    tgs.team_id,
                    CASE WHEN m.home_team_id = tgs.team_id THEN TRUE ELSE FALSE END as is_home,
                    CASE WHEN m.winner_team_id = tgs.team_id THEN 1 ELSE 0 END as won,
                    tgs.points,
                    -- Opponent points (for point differential)
                    opp_tgs.points as opp_points,
                    tgs.field_goal_pct,
                    tgs.three_point_pct,
                    -- Offensive/Defensive ratings if available
                    tgs.offensive_rating,
                    tgs.defensive_rating,
                    tgs.pace,
                    -- Effective FG% = (FG + 0.5 * 3PM) / FGA
                    tgs.effective_fg_pct,
                    -- Row number for each team's games (chronological order)
                    ROW_NUMBER() OVER (
                        PARTITION BY tgs.team_id 
                        ORDER BY m.game_date
                    ) as game_num
                FROM matches m
                JOIN team_game_stats tgs ON m.game_id = tgs.game_id
                -- Self-join to get opponent stats for the same game
                LEFT JOIN team_game_stats opp_tgs 
                    ON m.game_id = opp_tgs.game_id 
                    AND opp_tgs.team_id != tgs.team_id
                WHERE m.season = :season
                    AND m.is_completed = TRUE
            ),
            rolling_features AS (
                /*
                 * Step 2: Compute rolling statistics using window functions
                 * 
                 * Key insight: We use ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
                 * (not CURRENT ROW) because we want PAST performance to predict
                 * the CURRENT game. Including the current game would be data leakage!
                 * 
                 * 🎓 DATA LEAKAGE:
                 *   If you accidentally include future information in your features,
                 *   your model will look amazing in training but fail in production.
                 *   This is the #1 mistake juniors make with time-series features.
                 */
                SELECT 
                    game_id,
                    team_id,
                    is_home,
                    game_date,
                    -- Rolling 5-game win percentage (exclude current game!)
                    AVG(won) OVER (
                        PARTITION BY team_id 
                        ORDER BY game_date 
                        ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
                    ) as win_pct_last_5,
                    -- Rolling 10-game win percentage
                    AVG(won) OVER (
                        PARTITION BY team_id 
                        ORDER BY game_date 
                        ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING
                    ) as win_pct_last_10,
                    -- Rolling 5-game point differential
                    AVG(points - opp_points) OVER (
                        PARTITION BY team_id 
                        ORDER BY game_date 
                        ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
                    ) as avg_point_diff_last_5,
                    -- Rolling 10-game point differential
                    AVG(points - opp_points) OVER (
                        PARTITION BY team_id 
                        ORDER BY game_date 
                        ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING
                    ) as avg_point_diff_last_10,
                    -- Rolling 5-game offensive/defensive ratings
                    AVG(offensive_rating) OVER (
                        PARTITION BY team_id 
                        ORDER BY game_date 
                        ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
                    ) as avg_off_rating_last_5,
                    AVG(defensive_rating) OVER (
                        PARTITION BY team_id 
                        ORDER BY game_date 
                        ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
                    ) as avg_def_rating_last_5,
                    AVG(pace) OVER (
                        PARTITION BY team_id 
                        ORDER BY game_date 
                        ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
                    ) as avg_pace_last_5,
                    AVG(effective_fg_pct) OVER (
                        PARTITION BY team_id 
                        ORDER BY game_date 
                        ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
                    ) as avg_efg_last_5,
                    -- Rest days: days since previous game
                    (game_date - LAG(game_date) OVER (
                        PARTITION BY team_id 
                        ORDER BY game_date
                    )) as days_rest,
                    -- Current streak: count consecutive wins (positive) or losses (negative)
                    game_num
                FROM team_games
            )
            /*
             * Step 3: Insert computed features into match_features table
             */
            INSERT INTO match_features (
                game_id, team_id, 
                win_pct_last_5, win_pct_last_10,
                avg_point_diff_last_5, avg_point_diff_last_10,
                is_home, days_rest, is_back_to_back,
                avg_off_rating_last_5, avg_def_rating_last_5,
                avg_pace_last_5, avg_efg_last_5,
                h2h_data_available,
                current_streak
            )
            SELECT 
                rf.game_id,
                rf.team_id,
                ROUND(rf.win_pct_last_5::numeric, 3),
                ROUND(rf.win_pct_last_10::numeric, 3),
                ROUND(rf.avg_point_diff_last_5::numeric, 2),
                ROUND(rf.avg_point_diff_last_10::numeric, 2),
                rf.is_home,
                COALESCE(rf.days_rest, 7),  -- Default 7 for season opener
                CASE WHEN rf.days_rest <= 1 THEN TRUE ELSE FALSE END,
                ROUND(rf.avg_off_rating_last_5::numeric, 2),
                ROUND(rf.avg_def_rating_last_5::numeric, 2),
                ROUND(rf.avg_pace_last_5::numeric, 2),
                ROUND(rf.avg_efg_last_5::numeric, 3),
                0,
                0  -- Streak calculation done separately for simplicity
            FROM rolling_features rf
            WHERE rf.game_num > 5  -- Need at least 5 games to compute rolling features
            ON CONFLICT (game_id, team_id) DO UPDATE SET
                win_pct_last_5 = EXCLUDED.win_pct_last_5,
                win_pct_last_10 = EXCLUDED.win_pct_last_10,
                avg_point_diff_last_5 = EXCLUDED.avg_point_diff_last_5,
                avg_point_diff_last_10 = EXCLUDED.avg_point_diff_last_10,
                is_home = EXCLUDED.is_home,
                days_rest = EXCLUDED.days_rest,
                is_back_to_back = EXCLUDED.is_back_to_back,
                avg_off_rating_last_5 = EXCLUDED.avg_off_rating_last_5,
                avg_def_rating_last_5 = EXCLUDED.avg_def_rating_last_5,
                avg_pace_last_5 = EXCLUDED.avg_pace_last_5,
                avg_efg_last_5 = EXCLUDED.avg_efg_last_5,
                h2h_data_available = EXCLUDED.h2h_data_available
        """), {"season": season})
    
    # Count features created
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) FROM match_features 
            WHERE game_id IN (SELECT game_id FROM matches WHERE season = :season)
        """), {"season": season})
        count = result.scalar()
    
    logger.info(f"✅ Computed {count} feature rows for season {season}")
    return count


def compute_h2h_features(engine, season: str = "2025-26"):
    """
    Compute head-to-head features between every pair of teams.
    
    🎓 WHY H2H MATTERS:
        Some matchups have persistent advantages that go beyond overall
        team quality. For example, a fast-paced team might consistently
        beat a slow defensive team, even if the defensive team has a better
        overall record.
        
        H2H features capture these matchup-specific edges that overall
        stats miss.
    """
    logger.info(f"🤝 Computing head-to-head features for season {season}...")
    
    with engine.begin() as conn:
        conn.execute(text("""
            WITH h2h_history AS (
                SELECT 
                    mf.game_id,
                    mf.team_id,
                    m.game_date,
                    -- Determine opponent
                    CASE 
                        WHEN m.home_team_id = mf.team_id THEN m.away_team_id
                        ELSE m.home_team_id 
                    END as opponent_id,
                    CASE WHEN m.winner_team_id = mf.team_id THEN 1.0 ELSE 0.0 END as won,
                    -- Point differential
                    tgs.points - opp_tgs.points as margin
                FROM match_features mf
                JOIN matches m ON mf.game_id = m.game_id
                JOIN team_game_stats tgs ON m.game_id = tgs.game_id AND tgs.team_id = mf.team_id
                LEFT JOIN team_game_stats opp_tgs ON m.game_id = opp_tgs.game_id AND opp_tgs.team_id != mf.team_id
                WHERE m.season = :season
            )
            UPDATE match_features mf SET
                h2h_win_pct = sub.h2h_win_pct,
                h2h_avg_margin = sub.h2h_avg_margin,
                h2h_data_available = CASE WHEN sub.h2h_win_pct IS NOT NULL THEN 1 ELSE 0 END
            FROM (
                SELECT 
                    h.game_id,
                    h.team_id,
                    -- H2H win % against this specific opponent in the season
                    AVG(prev.won) as h2h_win_pct,
                    AVG(prev.margin) as h2h_avg_margin
                FROM h2h_history h
                LEFT JOIN h2h_history prev 
                    ON h.team_id = prev.team_id 
                    AND h.opponent_id = prev.opponent_id
                    AND prev.game_date < h.game_date
                GROUP BY h.game_id, h.team_id
            ) sub
            WHERE mf.game_id = sub.game_id 
            AND mf.team_id = sub.team_id
        """), {"season": season})
    
    logger.info(f"✅ H2H features computed for season {season}")


def compute_streak_features(engine, season: str = "2025-26"):
    """
    Compute non-leaky pregame streak values for each team-game row.

    A positive value means entering this game on a win streak, negative means
    entering on a loss streak, and 0 means no prior streak context.
    """
    logger.info(f"🔥 Computing streak features for season {season}...")

    with engine.begin() as conn:
        conn.execute(text("""
            WITH ordered_games AS (
                SELECT
                    mf.game_id,
                    mf.team_id,
                    m.game_date,
                    CASE WHEN m.winner_team_id = mf.team_id THEN 1 ELSE 0 END AS won
                FROM match_features mf
                JOIN matches m ON mf.game_id = m.game_id
                WHERE m.season = :season
                    AND m.is_completed = TRUE
            ),
            with_prev AS (
                SELECT
                    game_id,
                    team_id,
                    game_date,
                    won,
                    LAG(won) OVER (
                        PARTITION BY team_id
                        ORDER BY game_date, game_id
                    ) AS prev_won
                FROM ordered_games
            ),
            grouped AS (
                SELECT
                    game_id,
                    team_id,
                    game_date,
                    won,
                    CASE
                        WHEN prev_won IS NULL OR won != prev_won THEN 1
                        ELSE 0
                    END AS change_flag
                FROM with_prev
            ),
            segmented AS (
                SELECT
                    game_id,
                    team_id,
                    game_date,
                    won,
                    SUM(change_flag) OVER (
                        PARTITION BY team_id
                        ORDER BY game_date, game_id
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) AS streak_group
                FROM grouped
            ),
            signed_streaks AS (
                SELECT
                    game_id,
                    team_id,
                    game_date,
                    CASE
                        WHEN won = 1 THEN
                            ROW_NUMBER() OVER (
                                PARTITION BY team_id, streak_group
                                ORDER BY game_date, game_id
                            )
                        ELSE
                            -ROW_NUMBER() OVER (
                                PARTITION BY team_id, streak_group
                                ORDER BY game_date, game_id
                            )
                    END AS signed_streak_including_current
                FROM segmented
            ),
            pregame_streaks AS (
                SELECT
                    game_id,
                    team_id,
                    COALESCE(
                        LAG(signed_streak_including_current) OVER (
                            PARTITION BY team_id
                            ORDER BY game_date, game_id
                        ),
                        0
                    )::INTEGER AS pregame_streak
                FROM signed_streaks
            )
            UPDATE match_features mf
            SET current_streak = ps.pregame_streak
            FROM pregame_streaks ps
            WHERE mf.game_id = ps.game_id
                AND mf.team_id = ps.team_id
        """), {"season": season})

    logger.info(f"✅ Streak features computed for season {season}")


def run_feature_engineering(seasons: list = None):
    """
    Run the complete feature engineering pipeline.
    
    🎓 PIPELINE ORDER:
        1. Rolling features first (win%, point diff, ratings)
        2. H2H features second (needs game context)
        
        This produces a complete feature set for every game where we have
        at least 5 prior games of data.
    """
    if seasons is None:
        seasons = ["2025-26"]
    
    engine = get_engine()
    validation_summary = validate_raw_data(engine, seasons)
    ensure_h2h_data_available_column(engine)
    
    logger.info("=" * 60)
    logger.info("⚙️ STARTING FEATURE ENGINEERING PIPELINE")
    start_time = time.time()
    
    logger.info("=" * 60)
    logger.info("🚀 STARTING FEATURE ENGINEERING PIPELINE")
    logger.info("=" * 60)
    
    try:
        # Default to current season if not specified
        season = seasons[0] if seasons else config.CURRENT_SEASON
        record_count = compute_features(engine, season=season)
        compute_h2h_features(engine, season=season)
        compute_streak_features(engine, season=season)
        
        elapsed = time.time() - start_time
        
        # Record success
        record_audit(
            engine,
            module="feature_store",
            status="success",
            processed=record_count,
            inserted=record_count,
            details={
                "season": season,
                "elapsed_seconds": round(elapsed, 2),
                "h2h_features_updated": True,
                "streak_features_updated": True,
                "validation": validation_summary,
            }
        )
        
        logger.info("=" * 60)
        logger.info(f"✅ COMPLETED in {elapsed:.1f}s")
        logger.info(f"   Features Computed: {record_count}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"💥 CRITICAL FEATURE ERROR: {e}")
        record_audit(
            engine,
            module="feature_store",
            status="failed",
            errors=str(e),
            details={"step": "main_loop"}
        )
        raise e


if __name__ == "__main__":
    run_feature_engineering()
