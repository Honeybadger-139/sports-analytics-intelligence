"""
NBA Data Ingestion Module
=========================

🎓 WHAT THIS MODULE DOES:
    Pulls NBA data from the official NBA stats API (via the nba_api Python package)
    and loads it into our PostgreSQL database.

🧠 WHY WE BUILT IT THIS WAY:
    - nba_api wraps the official NBA.com stats endpoints — same data NBA analysts use
    - We pull in batch (not real-time) because historical data is what trains our models
    - Rate limiting is critical: NBA.com throttles aggressive requests
    - We use upsert (INSERT ON CONFLICT UPDATE) to make this idempotent — safe to re-run

📋 DATA WE PULL:
    1. Teams: All 30 NBA teams with conference/division
    2. Game Logs: Every game for a season (scores, dates, venues)
    3. Team Game Stats: Per-game shooting, rebounding, advanced metrics
    4. Players: Active roster information

💡 INTERVIEW ANGLE:
    "I designed the ingestion pipeline to be idempotent using PostgreSQL's
    ON CONFLICT clause. This means I can rerun it safely without duplicates —
    a critical property for any production data pipeline."

Architecture Decision (see docs/decisions/decision-log.md):
    We chose nba_api over web scraping because:
    - Structured JSON responses (no HTML parsing fragility)
    - Official endpoints = reliable data quality
    - Active Python community maintaining the package
    - Free, no API key required
"""

import time
import logging
import random
from logging.handlers import RotatingFileHandler
from datetime import datetime, date
from typing import Optional, Dict, Any, Set
import json

import pandas as pd
from nba_api.stats.static import teams as nba_teams
from nba_api.stats.endpoints import (
    teamgamelog,
    commonallplayers,
    leaguegamelog,
    leaguedashplayerstats,
)
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

from src import config
from src.data.audit_store import (
    ensure_pipeline_audit_table,
    is_missing_pipeline_audit_error,
)

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


def get_engine():
    """Create SQLAlchemy engine from centralized config."""
    return create_engine(config.DATABASE_URL)


def rate_limit():
    """
    Sleep between API calls to avoid being throttled with added jitter.
    
    🎓 WHY JITTER?
        If we call the API at EXACTLY 2.0s intervals, anti-scraping
        filters might flag the "robotic" pattern. Jitter adds 
        organic randomness.
    """
    jitter = random.uniform(-0.2, 0.2)
    sleep_time = max(0.5, config.REQUEST_DELAY + jitter)
    time.sleep(sleep_time)


def check_health(engine) -> bool:
    """
    Pre-flight check: Verify DB and API connectivity.
    """
    logger.info("🩺 Performing pre-flight health checks...")
    
    # 1. DB Connectivity
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("  ✅ Database connectivity: OK")
    except Exception as e:
        logger.error(f"  ❌ Database connectivity FAILED: {e}")
        return False
        
    # 2. NBA API Connectivity (Simple Heartbeat)
    try:
        from nba_api.stats.endpoints import commonallplayers
        commonallplayers.CommonAllPlayers(is_only_current_season=1, timeout=10)
        logger.info("  ✅ NBA API connectivity: OK")
    except Exception as e:
        logger.error(f"  ❌ NBA API connectivity FAILED: {e}")
        return False
        
    return True


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


def retry_api_call(func, *args, **kwargs):
    """
    Retry an nba_api call with exponential backoff.
    
    🎓 EXPONENTIAL BACKOFF:
        Attempt 1: fails → wait 10s
        Attempt 2: fails → wait 20s  (10 * 2^1)
        Attempt 3: fails → wait 40s  (10 * 2^2)
        
        This is the standard pattern for handling flaky APIs.
        If an interviewer asks about resilient API integrations,
        mention exponential backoff with jitter.
    """
    for attempt in range(config.MAX_RETRIES):
        try:
            rate_limit()
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < config.MAX_RETRIES - 1:
                wait_time = config.BASE_BACKOFF * (2 ** attempt)
                logger.warning(f"    ⏳ Attempt {attempt+1} failed: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"    ❌ All {config.MAX_RETRIES} attempts failed: {e}")
                raise


def _to_float(value) -> Optional[float]:
    """Safely cast numeric-like values to float."""
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value) -> Optional[int]:
    """Safely cast numeric-like values to int."""
    if pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load_games_missing_advanced_metrics(engine, season: str) -> Set[str]:
    """
    Return game_ids where advanced team metrics are missing and need backfill.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT DISTINCT tgs.game_id
                FROM team_game_stats tgs
                JOIN matches m ON tgs.game_id = m.game_id
                WHERE m.season = :season
                    AND (
                        tgs.offensive_rating IS NULL
                        OR tgs.defensive_rating IS NULL
                        OR tgs.pace IS NULL
                        OR tgs.effective_fg_pct IS NULL
                        OR tgs.true_shooting_pct IS NULL
                    )
                """
            ),
            {"season": season},
        ).fetchall()
    return {str(r[0]) for r in rows}


def _compute_advanced_team_metrics(row: pd.Series) -> Dict[str, Optional[float]]:
    """
    Compute advanced metrics from team game-log columns when available.

    Notes:
    - `pace` is modeled as estimated possessions/game.
    - Defensive rating uses opponent points inferred via plus-minus.
    """
    fga = _to_float(row.get("FGA"))
    fgm = _to_float(row.get("FGM"))
    fg3m = _to_float(row.get("FG3M"))
    fta = _to_float(row.get("FTA"))
    oreb = _to_float(row.get("OREB"))
    tov = _to_float(row.get("TOV"))
    pts = _to_float(row.get("PTS"))
    plus_minus = _to_float(row.get("PLUS_MINUS"))

    possessions = None
    if None not in (fga, oreb, tov, fta):
        poss = fga - oreb + tov + 0.44 * fta
        if poss > 0:
            possessions = poss

    effective_fg_pct = None
    if fga and fga > 0 and fgm is not None and fg3m is not None:
        effective_fg_pct = (fgm + 0.5 * fg3m) / fga

    true_shooting_pct = None
    if pts is not None and fga is not None and fta is not None:
        ts_denom = 2 * (fga + 0.44 * fta)
        if ts_denom > 0:
            true_shooting_pct = pts / ts_denom

    offensive_rating = None
    if possessions and pts is not None:
        offensive_rating = 100 * pts / possessions

    defensive_rating = None
    if possessions and pts is not None and plus_minus is not None:
        opp_points = pts - plus_minus
        defensive_rating = 100 * opp_points / possessions

    pace = possessions

    return {
        "offensive_rating": round(offensive_rating, 2) if offensive_rating is not None else None,
        "defensive_rating": round(defensive_rating, 2) if defensive_rating is not None else None,
        "pace": round(pace, 2) if pace is not None else None,
        "effective_fg_pct": round(effective_fg_pct, 3) if effective_fg_pct is not None else None,
        "true_shooting_pct": round(true_shooting_pct, 3) if true_shooting_pct is not None else None,
    }


def _backfill_defensive_rating_from_opponent_points(engine, season: str) -> None:
    """
    Fill missing defensive ratings using opponent points and estimated pace.
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                WITH opponent_points AS (
                    SELECT
                        tgs.game_id,
                        tgs.team_id,
                        opp.points AS opp_points
                    FROM team_game_stats tgs
                    JOIN team_game_stats opp
                        ON tgs.game_id = opp.game_id
                        AND tgs.team_id <> opp.team_id
                    JOIN matches m ON m.game_id = tgs.game_id
                    WHERE m.season = :season
                )
                UPDATE team_game_stats tgs
                SET defensive_rating = ROUND((op.opp_points::numeric * 100) / NULLIF(tgs.pace, 0), 2)
                FROM opponent_points op
                WHERE tgs.game_id = op.game_id
                    AND tgs.team_id = op.team_id
                    AND tgs.pace IS NOT NULL
                    AND tgs.defensive_rating IS NULL
                """
            ),
            {"season": season},
        )


# ==========================================
# 1. TEAMS INGESTION
# ==========================================

def ingest_teams(engine) -> int:
    """
    Pull all 30 NBA teams and upsert into the teams table.
    
    🎓 WHAT'S HAPPENING:
        nba_api.stats.static.teams gives us a static list of all NBA teams.
        We enrich this with conference/division data.
        
    Returns:
        Number of teams ingested.
    """
    logger.info("🏀 Ingesting NBA teams...")
    
    all_teams = nba_teams.get_teams()
    
    with engine.begin() as conn:
        for team in all_teams:
            conn.execute(
                text("""
                    INSERT INTO teams (team_id, abbreviation, full_name, city, updated_at)
                    VALUES (:team_id, :abbrev, :full_name, :city, :now)
                    ON CONFLICT (team_id) DO UPDATE SET
                        abbreviation = EXCLUDED.abbreviation,
                        full_name = EXCLUDED.full_name,
                        city = EXCLUDED.city,
                        updated_at = EXCLUDED.updated_at
                """),
                {
                    "team_id": team["id"],
                    "abbrev": team["abbreviation"],
                    "full_name": team["full_name"],
                    "city": team["city"],
                    "now": datetime.now(),
                },
            )
    
    count = len(all_teams)
    logger.info(f"✅ Ingested {count} teams")
    return count


# ==========================================
# 2. GAME LOGS INGESTION
# ==========================================

def ingest_season_games(engine, season: str = "2025-26") -> int:
    """
    Pull all games for a season and upsert into matches + team_game_stats.
    
    🎓 WHAT'S HAPPENING:
        For each of the 30 teams, we pull their game log for the season.
        Each game appears twice (once per team), so we deduplicate on game_id.
        
        We extract:
        - Match info: date, teams, scores, venue
        - Team stats: shooting %, rebounds, assists, turnovers, etc.
        
    🎓 WHY GAME LOGS (not box scores):
        Game logs give us team-level aggregates per game in a single API call.
        Box scores give player-level detail but require one call per game.
        For our v1 model, team-level features are sufficient.
        We'll add player-level in a future iteration.
    
    Args:
        season: NBA season string, e.g. "2025-26"
    
    Returns:
        Number of games ingested.
    """
    logger.info(f"📊 Ingesting game logs for season {season}...")
    
    # Check latest date for incremental sync (only trust completed games)
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT MAX(game_date) FROM matches WHERE season = :season AND is_completed = TRUE"),
            {"season": season}
        ).scalar()
    latest_date = pd.to_datetime(result).date() if result else None
    
    if latest_date:
        logger.info(f"  -> Incremental sync: fetching games on or after {latest_date}")
    else:
        logger.info("  -> Full sync: no existing games found for season")

    games_requiring_backfill = _load_games_missing_advanced_metrics(engine, season)
    if games_requiring_backfill:
        logger.info(
            f"  -> Advanced-metrics backfill detected for {len(games_requiring_backfill)} games"
        )
    
    all_teams = nba_teams.get_teams()
    games_seen = set()
    game_count = 0
    
    for i, team in enumerate(all_teams):
        team_id = team["id"]
        team_abbrev = team["abbreviation"]
        logger.info(f"  [{i+1}/30] Pulling games for {team_abbrev}...")
        
        try:
            game_log = retry_api_call(
                lambda tid=team_id, s=season: teamgamelog.TeamGameLog(
                    team_id=tid,
                    season=s,
                    season_type_all_star="Regular Season",
                    timeout=60,
                )
            )
            
            df = game_log.get_data_frames()[0]
            
            if latest_date:
                df["GAME_DATE_DT"] = pd.to_datetime(df["GAME_DATE"], format="mixed").dt.date
                if games_requiring_backfill:
                    df["GAME_ID_STR"] = df["Game_ID"].astype(str)
                    df = df[
                        (df["GAME_DATE_DT"] >= latest_date)
                        | (df["GAME_ID_STR"].isin(games_requiring_backfill))
                    ]
                else:
                    df = df[df["GAME_DATE_DT"] >= latest_date]
            
            if df.empty:
                logger.info(f"    No new games found for {team_abbrev}")
                continue
            
            with engine.begin() as conn:
                for _, row in df.iterrows():
                    game_id = row["Game_ID"]
                    
                    # Parse matchup to determine home/away
                    matchup = row["MATCHUP"]
                    is_home = "vs." in matchup
                    
                    # Parse opponent
                    if "vs." in matchup:
                        opp_abbrev = matchup.split("vs. ")[-1].strip()
                    else:
                        opp_abbrev = matchup.split("@ ")[-1].strip()
                    
                    # Find opponent team_id
                    opp_team = next(
                        (t for t in all_teams if t["abbreviation"] == opp_abbrev),
                        None,
                    )
                    opp_team_id = opp_team["id"] if opp_team else None
                    
                    # Parse game date
                    game_date = row["GAME_DATE_DT"] if "GAME_DATE_DT" in row else pd.to_datetime(row["GAME_DATE"], format="mixed").date()
                    

                    # Determine winner
                    wl = row["WL"]
                    winner_id = team_id if wl == "W" else opp_team_id
                    
                    # Upsert match data
                    home_team_id = team_id if is_home else opp_team_id
                    away_team_id = opp_team_id if is_home else team_id
                    home_score = int(row["PTS"]) if is_home else None
                    away_score = int(row["PTS"]) if not is_home else None
                    is_completed = pd.notna(row.get("WL"))
                    
                    conn.execute(
                        text("""
                            INSERT INTO matches (
                                game_id, game_date, season, home_team_id, 
                                away_team_id, winner_team_id, is_completed, 
                                home_score, away_score
                            )
                            VALUES (
                                :game_id, :game_date, :season, :home_team_id, 
                                :away_team_id, :winner_id, :is_completed,
                                :home_score, :away_score
                            )
                            ON CONFLICT (game_id) DO UPDATE SET
                                winner_team_id = COALESCE(EXCLUDED.winner_team_id, matches.winner_team_id),
                                is_completed = EXCLUDED.is_completed,
                                home_score = CASE WHEN EXCLUDED.home_score IS NOT NULL THEN EXCLUDED.home_score ELSE matches.home_score END,
                                away_score = CASE WHEN EXCLUDED.away_score IS NOT NULL THEN EXCLUDED.away_score ELSE matches.away_score END
                        """),
                        {
                            "game_id": game_id,
                            "game_date": game_date,
                            "season": season,
                            "home_team_id": home_team_id,
                            "away_team_id": away_team_id,
                            "winner_id": winner_id,
                            "is_completed": is_completed,
                            "home_score": home_score,
                            "away_score": away_score
                        },
                    )
                    if game_id not in games_seen:
                        games_seen.add(game_id)
                        game_count += 1
                    
                    # Insert team game stats (one row per team per game)
                    advanced_metrics = _compute_advanced_team_metrics(row)
                    conn.execute(
                        text("""
                            INSERT INTO team_game_stats (
                                game_id, team_id, points, rebounds, assists, 
                                steals, blocks, turnovers, 
                                field_goal_pct, three_point_pct, free_throw_pct,
                                offensive_rating, defensive_rating, pace,
                                effective_fg_pct, true_shooting_pct
                            )
                            VALUES (
                                :game_id, :team_id, :pts, :reb, :ast,
                                :stl, :blk, :tov,
                                :fg_pct, :fg3_pct, :ft_pct,
                                :off_rating, :def_rating, :pace,
                                :efg_pct, :ts_pct
                            )
                            ON CONFLICT (game_id, team_id) DO UPDATE SET
                                points = EXCLUDED.points,
                                rebounds = EXCLUDED.rebounds,
                                assists = EXCLUDED.assists,
                                steals = EXCLUDED.steals,
                                blocks = EXCLUDED.blocks,
                                turnovers = EXCLUDED.turnovers,
                                field_goal_pct = EXCLUDED.field_goal_pct,
                                three_point_pct = EXCLUDED.three_point_pct,
                                free_throw_pct = EXCLUDED.free_throw_pct,
                                offensive_rating = EXCLUDED.offensive_rating,
                                defensive_rating = EXCLUDED.defensive_rating,
                                pace = EXCLUDED.pace,
                                effective_fg_pct = EXCLUDED.effective_fg_pct,
                                true_shooting_pct = EXCLUDED.true_shooting_pct
                        """),
                        {
                            "game_id": game_id,
                            "team_id": team_id,
                            "pts": _to_int(row.get("PTS")),
                            "reb": _to_int(row.get("REB")),
                            "ast": _to_int(row.get("AST")),
                            "stl": _to_int(row.get("STL")),
                            "blk": _to_int(row.get("BLK")),
                            "tov": _to_int(row.get("TOV")),
                            "fg_pct": _to_float(row.get("FG_PCT")),
                            "fg3_pct": _to_float(row.get("FG3_PCT")),
                            "ft_pct": _to_float(row.get("FT_PCT")),
                            "off_rating": advanced_metrics["offensive_rating"],
                            "def_rating": advanced_metrics["defensive_rating"],
                            "pace": advanced_metrics["pace"],
                            "efg_pct": advanced_metrics["effective_fg_pct"],
                            "ts_pct": advanced_metrics["true_shooting_pct"],
                        },
                    )
            
        except Exception as e:
            logger.error(f"    ❌ Error pulling {team_abbrev}: {e}")
            continue

    # Final pass: ensure defensive ratings are backfilled even when PLUS_MINUS
    # is unavailable in upstream payload.
    _backfill_defensive_rating_from_opponent_points(engine, season)
    
    logger.info(f"✅ Ingested {game_count} unique games for season {season}")
    return game_count


# ==========================================
# 3. PLAYER ROSTER INGESTION
# ==========================================

def ingest_players(engine, season: str = "2025-26") -> int:
    """
    Pull all players for the given season and upsert into players table.
    
    🎓 WHY PLAYER DATA MATTERS:
        Even though our v1 model uses team-level features, knowing which
        players are on each team lets us:
        1. Detect roster changes (trades, injuries)
        2. Build player-impact features later (star player availability)
        3. Support player-prop bet predictions in future versions
        
    Note: We use CommonAllPlayers to get EVERY player who played in the season,
    not just the current active rosters.
    
    Returns:
        Number of players ingested.
    """
    logger.info(f"👤 Ingesting all players for season {season}...")
    
    player_count = 0
    try:
        roster = retry_api_call(
            lambda s=season: commonallplayers.CommonAllPlayers(
                is_only_current_season=1,
                season=s,
                timeout=60,
            )
        )
        
        df = roster.get_data_frames()[0]
        
        with engine.begin() as conn:
            for _, player in df.iterrows():
                # TEAM_ID can be 0 or NaN for free agents/waived players
                team_id = int(player["TEAM_ID"]) if pd.notna(player.get("TEAM_ID")) and player.get("TEAM_ID") != 0 and player.get("TEAM_ID") != "0" else None
                
                conn.execute(
                    text("""
                        INSERT INTO players (player_id, full_name, team_id, position, is_active, updated_at)
                        VALUES (:player_id, :full_name, :team_id, :position, TRUE, :now)
                        ON CONFLICT (player_id) DO UPDATE SET
                            full_name = EXCLUDED.full_name,
                            team_id = EXCLUDED.team_id,
                            position = EXCLUDED.position,
                            is_active = TRUE,
                            updated_at = EXCLUDED.updated_at
                    """),
                    {
                        "player_id": int(player["PERSON_ID"]),
                        "full_name": player["DISPLAY_FIRST_LAST"],
                        "team_id": team_id,
                        "position": None,  # CommonAllPlayers doesn't provide position easily, dropping for now
                        "now": datetime.now(),
                    },
                )
                player_count += 1
                
        logger.info(f"✅ Ingested {player_count} players")
        
    except Exception as e:
        logger.error(f"❌ Error pulling players: {e}")
        
    return player_count

# ==========================================
# 4. PLAYER GAME LOGS (Per Game Stats)
# ==========================================

def ingest_player_game_logs(engine, season: str = "2025-26") -> int:
    """
    Fetch all player game logs across the league incrementally.
    """
    logger.info(f"🏀 Ingesting player game logs for season {season}...")
    
    # 1. Incremental Sync Logic
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                SELECT MAX(m.game_date) 
                FROM player_game_stats pgs
                JOIN matches m ON pgs.game_id = m.game_id
                WHERE m.season = :season
            """),
            {"season": season}
        ).fetchone()
        max_date_in_db = result[0] if result and result[0] else None

    logger.info(f"   -> Incremental sync: fetching player games on or after {max_date_in_db if max_date_in_db else 'the beginning of the season'}")

    game_count = 0
    try:
        # LeagueGameLog with player abbreviation 'P' gets all player performances
        log = retry_api_call(
            lambda s=season: leaguegamelog.LeagueGameLog(
                season=s,
                player_or_team_abbreviation="P",
                timeout=60
            )
        )
        
        df = log.get_data_frames()[0]
        
        if max_date_in_db:
            df["GAME_DATE_DT"] = pd.to_datetime(df["GAME_DATE"], format="mixed").dt.date
            df = df[df["GAME_DATE_DT"] >= max_date_in_db]
            
        if df.empty:
            logger.info("    No new player game logs found")
            return 0
            
        with engine.begin() as conn:
            for _, row in df.iterrows():
                game_id = str(row["GAME_ID"])
                player_id = int(row["PLAYER_ID"])
                team_id = int(row["TEAM_ID"])
                
                conn.execute(
                    text("""
                        INSERT INTO player_game_stats (
                            game_id, player_id, team_id, minutes, points, rebounds, assists,
                            steals, blocks, turnovers, personal_fouls, field_goals_made,
                            field_goals_attempted, field_goal_pct, three_points_made,
                            three_points_attempted, three_point_pct, free_throws_made,
                            free_throws_attempted, free_throw_pct, plus_minus, fantasy_points
                        )
                        VALUES (
                            :game_id, :player_id, :team_id, :min, :pts, :reb, :ast,
                            :stl, :blk, :tov, :pf, :fgm, :fga, :fg_pct, :fg3m, :fg3a,
                            :fg3_pct, :ftm, :fta, :ft_pct, :plus_minus, :fantasy_pts
                        )
                        ON CONFLICT (game_id, player_id) DO UPDATE SET
                            team_id = EXCLUDED.team_id,
                            minutes = EXCLUDED.minutes,
                            points = EXCLUDED.points,
                            rebounds = EXCLUDED.rebounds,
                            assists = EXCLUDED.assists,
                            steals = EXCLUDED.steals,
                            blocks = EXCLUDED.blocks,
                            turnovers = EXCLUDED.turnovers,
                            personal_fouls = EXCLUDED.personal_fouls,
                            field_goals_made = EXCLUDED.field_goals_made,
                            field_goals_attempted = EXCLUDED.field_goals_attempted,
                            field_goal_pct = EXCLUDED.field_goal_pct,
                            three_points_made = EXCLUDED.three_points_made,
                            three_points_attempted = EXCLUDED.three_points_attempted,
                            three_point_pct = EXCLUDED.three_point_pct,
                            free_throws_made = EXCLUDED.free_throws_made,
                            free_throws_attempted = EXCLUDED.free_throws_attempted,
                            free_throw_pct = EXCLUDED.free_throw_pct,
                            plus_minus = EXCLUDED.plus_minus,
                            fantasy_points = EXCLUDED.fantasy_points
                    """),
                    {
                        "game_id": game_id,
                        "player_id": player_id,
                        "team_id": team_id,
                        "min": float(row["MIN"]) if pd.notna(row.get("MIN")) else None,
                        "pts": int(row["PTS"]) if pd.notna(row.get("PTS")) else None,
                        "reb": int(row["REB"]) if pd.notna(row.get("REB")) else None,
                        "ast": int(row["AST"]) if pd.notna(row.get("AST")) else None,
                        "stl": int(row["STL"]) if pd.notna(row.get("STL")) else None,
                        "blk": int(row["BLK"]) if pd.notna(row.get("BLK")) else None,
                        "tov": int(row["TOV"]) if pd.notna(row.get("TOV")) else None,
                        "pf": int(row["PF"]) if pd.notna(row.get("PF")) else None,
                        "fgm": int(row["FGM"]) if pd.notna(row.get("FGM")) else None,
                        "fga": int(row["FGA"]) if pd.notna(row.get("FGA")) else None,
                        "fg_pct": float(row["FG_PCT"]) if pd.notna(row.get("FG_PCT")) else None,
                        "fg3m": int(row["FG3M"]) if pd.notna(row.get("FG3M")) else None,
                        "fg3a": int(row["FG3A"]) if pd.notna(row.get("FG3A")) else None,
                        "fg3_pct": float(row["FG3_PCT"]) if pd.notna(row.get("FG3_PCT")) else None,
                        "ftm": int(row["FTM"]) if pd.notna(row.get("FTM")) else None,
                        "fta": int(row["FTA"]) if pd.notna(row.get("FTA")) else None,
                        "ft_pct": float(row["FT_PCT"]) if pd.notna(row.get("FT_PCT")) else None,
                        "plus_minus": int(row["PLUS_MINUS"]) if pd.notna(row.get("PLUS_MINUS")) else None,
                        "fantasy_pts": float(row["FANTASY_PTS"]) if pd.notna(row.get("FANTASY_PTS")) else None,
                    },
                )
                game_count += 1
                
    except Exception as e:
        logger.error(f"    ❌ Error pulling player game logs: {e}")
        
    logger.info(f"✅ Ingested {game_count} player game logs for season {season}")
    return game_count


# ==========================================
# 5. PLAYER SEASON STATS (Dashboard Aggregates)
# ==========================================

def ingest_player_season_stats(engine, season: str = "2025-26") -> int:
    """
    Fetch season-to-date aggregates for all players.
    Uses UPSERT to overwrite yesterday's totals with today's totals.
    """
    logger.info(f"📊 Ingesting player season stats for season {season}...")
    
    player_count = 0
    try:
        dash = retry_api_call(
            lambda s=season: leaguedashplayerstats.LeagueDashPlayerStats(
                season=s,
                timeout=60
            )
        )
        
        df = dash.get_data_frames()[0]
        
        with engine.begin() as conn:
            for _, row in df.iterrows():
                player_id = int(row["PLAYER_ID"])
                team_id = int(row["TEAM_ID"]) if pd.notna(row.get("TEAM_ID")) and row["TEAM_ID"] != 0 and str(row["TEAM_ID"]) != "0" else None
                
                conn.execute(
                    text("""
                        INSERT INTO player_season_stats (
                            player_id, season, team_id, games_played, wins, losses, win_pct,
                            minutes, points, rebounds, assists, steals, blocks, turnovers,
                            field_goal_pct, three_point_pct, free_throw_pct, plus_minus,
                            fantasy_points, updated_at
                        )
                        VALUES (
                            :player_id, :season, :team_id, :gp, :w, :l, :w_pct, :min, :pts,
                            :reb, :ast, :stl, :blk, :tov, :fg_pct, :fg3_pct, :ft_pct,
                            :plus_minus, :fantasy_pts, :now
                        )
                        ON CONFLICT (player_id, season) DO UPDATE SET
                            team_id = EXCLUDED.team_id,
                            games_played = EXCLUDED.games_played,
                            wins = EXCLUDED.wins,
                            losses = EXCLUDED.losses,
                            win_pct = EXCLUDED.win_pct,
                            minutes = EXCLUDED.minutes,
                            points = EXCLUDED.points,
                            rebounds = EXCLUDED.rebounds,
                            assists = EXCLUDED.assists,
                            steals = EXCLUDED.steals,
                            blocks = EXCLUDED.blocks,
                            turnovers = EXCLUDED.turnovers,
                            field_goal_pct = EXCLUDED.field_goal_pct,
                            three_point_pct = EXCLUDED.three_point_pct,
                            free_throw_pct = EXCLUDED.free_throw_pct,
                            plus_minus = EXCLUDED.plus_minus,
                            fantasy_points = EXCLUDED.fantasy_points,
                            updated_at = EXCLUDED.updated_at
                    """),
                    {
                        "player_id": player_id,
                        "season": season,
                        "team_id": team_id,
                        "gp": int(row["GP"]) if pd.notna(row.get("GP")) else 0,
                        "w": int(row["W"]) if pd.notna(row.get("W")) else 0,
                        "l": int(row["L"]) if pd.notna(row.get("L")) else 0,
                        "w_pct": float(row["W_PCT"]) if pd.notna(row.get("W_PCT")) else 0.0,
                        "min": float(row["MIN"]) if pd.notna(row.get("MIN")) else 0.0,
                        "pts": float(row["PTS"]) if pd.notna(row.get("PTS")) else 0.0,
                        "reb": float(row["REB"]) if pd.notna(row.get("REB")) else 0.0,
                        "ast": float(row["AST"]) if pd.notna(row.get("AST")) else 0.0,
                        "stl": float(row["STL"]) if pd.notna(row.get("STL")) else 0.0,
                        "blk": float(row["BLK"]) if pd.notna(row.get("BLK")) else 0.0,
                        "tov": float(row["TOV"]) if pd.notna(row.get("TOV")) else 0.0,
                        "fg_pct": float(row["FG_PCT"]) if pd.notna(row.get("FG_PCT")) else 0.0,
                        "fg3_pct": float(row["FG3_PCT"]) if pd.notna(row.get("FG3_PCT")) else 0.0,
                        "ft_pct": float(row["FT_PCT"]) if pd.notna(row.get("FT_PCT")) else 0.0,
                        "plus_minus": float(row["PLUS_MINUS"]) if pd.notna(row.get("PLUS_MINUS")) else 0.0,
                        "fantasy_pts": float(row["NBA_FANTASY_PTS"]) if pd.notna(row.get("NBA_FANTASY_PTS")) else 0.0,
                        "now": datetime.now()
                    }
                )
                player_count += 1
                
    except Exception as e:
        logger.error(f"    ❌ Error pulling player season stats: {e}")
        
    logger.info(f"✅ Ingested {player_count} player season records for {season}")
    return player_count


# ==========================================
# DATA INTEGRITY AUDIT
# ==========================================

def audit_data(engine):
    """
    Perform a consistency check on the ingested data.
    
    🎓 WHY:
        In professional ML engineering, model accuracy is only as good 
        as your data. This function flags suspicious "gaps" in the dataset.
    """
    logger.info("🔍 STARTING DATA INTEGRITY AUDIT...")
    with engine.connect() as conn:
        # 1. Check for Matches without Team Stats (should be exactly 2 stats records per match)
        stats_check = conn.execute(text("""
            SELECT m.game_id, COUNT(tgs.id) as stats_count
            FROM matches m
            LEFT JOIN team_game_stats tgs ON m.game_id = tgs.game_id
            WHERE m.is_completed = TRUE
            GROUP BY m.game_id
            HAVING COUNT(tgs.id) != 2;
        """)).fetchall()
        
        if stats_check:
            logger.warning(f"  ⚠️ ALERT: Found {len(stats_check)} completed games with missing team stats!")
        else:
            logger.info("  ✅ Team Stats: Every match has exactly 2 team records.")

        # 2. Check for Matches without Player Stats
        player_check = conn.execute(text("""
            SELECT m.game_id
            FROM matches m
            LEFT JOIN player_game_stats pgs ON m.game_id = pgs.game_id
            WHERE m.is_completed = TRUE
            GROUP BY m.game_id
            HAVING COUNT(pgs.id) = 0;
        """)).fetchall()
        
        if player_check:
            logger.warning(f"  ⚠️ ALERT: Found {len(player_check)} games with ZERO player stats!")
        else:
            logger.info("  ✅ Player Stats: No completed games are missing player box scores.")

        # 3. Check for NULL values in critical columns (Only for completed games)
        null_check = conn.execute(text("""
            SELECT COUNT(*) 
            FROM matches 
            WHERE is_completed = TRUE AND (home_score IS NULL OR away_score IS NULL);
        """)).scalar()
        
        if null_check > 0:
            logger.warning(f"  ⚠️ ALERT: Found {null_check} matches with NULL scores!")
        else:
            logger.info("  ✅ Data Quality: No NULL scores detected in matches table.")
    
    logger.info("🏁 AUDIT COMPLETE.")
    summary = {
        "team_stats_violations": len(stats_check),
        "player_stats_missing_games": len(player_check),
        "null_score_matches": int(null_check or 0),
    }
    summary["passed"] = (
        summary["team_stats_violations"] == 0
        and summary["player_stats_missing_games"] == 0
        and summary["null_score_matches"] == 0
    )
    return summary


# ==========================================
# MAIN INGESTION PIPELINE
# ==========================================

def run_full_ingestion(seasons: Optional[list] = None):
    """
    Run the complete data ingestion pipeline.
    """
    if seasons is None:
        seasons = [config.CURRENT_SEASON]
    
    engine = get_engine()
    
    # Pre-flight Check
    if not check_health(engine):
        logger.error("🚫 HEALTH CHECK FAILED. Aborting ingestion.")
        return

    logger.info("=" * 60)
    logger.info("🚀 STARTING FULL NBA DATA INGESTION")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    audit_details = {}
    
    try:
        # Step 1: Teams (dimension table)
        team_count = ingest_teams(engine)
        
        # Step 2: Game logs
        total_games = 0
        for season in seasons:
            total_games += ingest_season_games(engine, season=season)
        
        # Step 3: Player rosters
        player_count = ingest_players(engine, season=seasons[-1])
        
        # Step 4: Player Game Logs & Season Stats
        total_player_games = 0
        total_season_stats = 0
        for season in seasons:
            total_player_games += ingest_player_game_logs(engine, season=season)
            total_season_stats += ingest_player_season_stats(engine, season=season)
        
        # Step 5: Data Integrity Audit
        audit_summary = audit_data(engine)
        
        elapsed = time.time() - start_time
        total_processed = team_count + total_games + player_count + total_player_games + total_season_stats
        
        audit_details = {
            "teams": team_count,
            "games": total_games,
            "players": player_count,
            "player_logs": total_player_games,
            "season_aggs": total_season_stats,
            "elapsed_seconds": round(elapsed, 2),
            "audit_violations": audit_summary,
        }

        # Record final success
        record_audit(
            engine, 
            module="ingestion", 
            status="success", 
            processed=total_processed, 
            inserted=total_processed, 
            details=audit_details
        )
        
        logger.info("=" * 60)
        logger.info(f"✅ INGESTED in {elapsed:.1f}s")
        logger.info(f"   Teams:   {team_count}")
        logger.info(f"   Games:   {total_games}")
        logger.info(f"   Players: {player_count}")
        logger.info(f"   Player Logs: {total_player_games}")
        logger.info(f"   Season Aggs: {total_season_stats}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"💥 CRITICAL INGESTION ERROR: {e}")
        record_audit(
            engine,
            module="ingestion",
            status="failed",
            errors=str(e),
            details={"step": "main_loop"}
        )
        raise e


if __name__ == "__main__":
    run_full_ingestion()
