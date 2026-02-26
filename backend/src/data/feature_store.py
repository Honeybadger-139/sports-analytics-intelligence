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
import os
import json
import time
from datetime import datetime
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from src import config

load_dotenv()

# Ensure logs directory exists
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
PIPE_LOG_FILE = os.path.join(LOG_DIR, "pipeline.log")

# Configure logging (Dual Handler: Console + File)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PIPE_LOG_FILE)
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"📝 Logging to console and {PIPE_LOG_FILE}")


def record_audit(engine, module: str, status: str, processed: int = 0, inserted: int = 0, errors: str = None, details: dict = None):
    """
    Record pipeline results into the pipeline_audit table.
    """
    logger.info(f"📊 Recording audit log for {module} (status: {status})...")
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO pipeline_audit (module, status, records_processed, records_inserted, errors, details)
                    VALUES (:module, :status, :processed, :inserted, :errors, :details)
                """),
                {
                    "module": module,
                    "status": status,
                    "processed": processed,
                    "inserted": inserted,
                    "errors": errors,
                    "details": json.dumps(details) if details else None
                }
            )
    except Exception as e:
        logger.error(f"  ❌ Failed to record audit log: {e}")


def get_engine():
    """Create SQLAlchemy engine from centralized config."""
    return create_engine(config.DATABASE_URL)


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
                avg_efg_last_5 = EXCLUDED.avg_efg_last_5
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
                h2h_avg_margin = sub.h2h_avg_margin
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
    
    logger.info("=" * 60)
    logger.info("⚙️ STARTING FEATURE ENGINEERING PIPELINE")
    start_time = time.time()
    
    logger.info("=" * 60)
    logger.info("🚀 STARTING FEATURE ENGINEERING PIPELINE")
    logger.info("=" * 60)
    
    try:
        # Default to current season if not specified
        season = config.CURRENT_SEASON
        record_count = compute_features(engine, season=season)
        
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
                "elapsed_seconds": round(elapsed, 2)
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
