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
from datetime import datetime
from typing import Optional

import pandas as pd
from nba_api.stats.static import teams as nba_teams
from nba_api.stats.endpoints import (
    teamgamelog,
    commonteamroster,
)
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Rate limiting: NBA.com throttles requests — be respectful
REQUEST_DELAY = 1.0  # seconds between API calls


def get_engine():
    """Create SQLAlchemy engine from environment variable."""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://analyst:analytics2026@localhost:5432/sports_analytics",
    )
    return create_engine(database_url)


def rate_limit():
    """
    Sleep between API calls to avoid being throttled.
    
    🎓 WHY:
        NBA.com rate-limits aggressive requests. If we fire 100 requests
        in 10 seconds, we'll get 429 (Too Many Requests) or worse, IP-banned.
        
        In production systems, you'd use exponential backoff with jitter.
        For our daily batch job, a simple 1-second delay is sufficient.
    """
    time.sleep(REQUEST_DELAY)


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
    
    all_teams = nba_teams.get_teams()
    games_seen = set()
    game_count = 0
    
    for i, team in enumerate(all_teams):
        team_id = team["id"]
        team_abbrev = team["abbreviation"]
        logger.info(f"  [{i+1}/30] Pulling games for {team_abbrev}...")
        
        try:
            game_log = teamgamelog.TeamGameLog(
                team_id=team_id,
                season=season,
                season_type_all_star="Regular Season",
            )
            rate_limit()
            
            df = game_log.get_data_frames()[0]
            
            if df.empty:
                logger.info(f"    No games found for {team_abbrev}")
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
                    game_date = pd.to_datetime(row["GAME_DATE"]).date()
                    
                    # Determine winner
                    wl = row["WL"]
                    winner_id = team_id if wl == "W" else opp_team_id
                    
                    # Insert match (only if not seen yet — dedup)
                    if game_id not in games_seen:
                        home_team = team_id if is_home else opp_team_id
                        away_team = opp_team_id if is_home else team_id
                        home_score = int(row["PTS"]) if is_home else None
                        away_score = int(row["PTS"]) if not is_home else None
                        
                        conn.execute(
                            text("""
                                INSERT INTO matches (game_id, game_date, season, home_team_id, 
                                    away_team_id, winner_team_id, is_completed)
                                VALUES (:game_id, :game_date, :season, :home_team, 
                                    :away_team, :winner_id, TRUE)
                                ON CONFLICT (game_id) DO UPDATE SET
                                    winner_team_id = EXCLUDED.winner_team_id,
                                    is_completed = TRUE
                            """),
                            {
                                "game_id": game_id,
                                "game_date": game_date,
                                "season": season,
                                "home_team": home_team,
                                "away_team": away_team,
                                "winner_id": winner_id,
                            },
                        )
                        games_seen.add(game_id)
                        game_count += 1
                    
                    # Insert team game stats (one row per team per game)
                    conn.execute(
                        text("""
                            INSERT INTO team_game_stats (
                                game_id, team_id, points, rebounds, assists, 
                                steals, blocks, turnovers, 
                                field_goal_pct, three_point_pct, free_throw_pct
                            )
                            VALUES (
                                :game_id, :team_id, :pts, :reb, :ast,
                                :stl, :blk, :tov,
                                :fg_pct, :fg3_pct, :ft_pct
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
                                free_throw_pct = EXCLUDED.free_throw_pct
                        """),
                        {
                            "game_id": game_id,
                            "team_id": team_id,
                            "pts": int(row["PTS"]) if pd.notna(row["PTS"]) else None,
                            "reb": int(row["REB"]) if pd.notna(row.get("REB", None)) else None,
                            "ast": int(row["AST"]) if pd.notna(row.get("AST", None)) else None,
                            "stl": int(row["STL"]) if pd.notna(row.get("STL", None)) else None,
                            "blk": int(row["BLK"]) if pd.notna(row.get("BLK", None)) else None,
                            "tov": int(row["TOV"]) if pd.notna(row.get("TOV", None)) else None,
                            "fg_pct": float(row["FG_PCT"]) if pd.notna(row.get("FG_PCT", None)) else None,
                            "fg3_pct": float(row["FG3_PCT"]) if pd.notna(row.get("FG3_PCT", None)) else None,
                            "ft_pct": float(row["FT_PCT"]) if pd.notna(row.get("FT_PCT", None)) else None,
                        },
                    )
            
        except Exception as e:
            logger.error(f"    ❌ Error pulling {team_abbrev}: {e}")
            continue
    
    logger.info(f"✅ Ingested {game_count} unique games for season {season}")
    return game_count


# ==========================================
# 3. PLAYER ROSTER INGESTION
# ==========================================

def ingest_players(engine, season: str = "2025-26") -> int:
    """
    Pull current rosters for all teams and upsert into players table.
    
    🎓 WHY PLAYER DATA MATTERS:
        Even though our v1 model uses team-level features, knowing which
        players are on each team lets us:
        1. Detect roster changes (trades, injuries)
        2. Build player-impact features later (star player availability)
        3. Support player-prop bet predictions in future versions
    
    Returns:
        Number of players ingested.
    """
    logger.info("👤 Ingesting player rosters...")
    
    all_teams = nba_teams.get_teams()
    player_count = 0
    
    for i, team in enumerate(all_teams):
        team_id = team["id"]
        team_abbrev = team["abbreviation"]
        
        try:
            roster = commonteamroster.CommonTeamRoster(
                team_id=team_id,
                season=season,
            )
            rate_limit()
            
            df = roster.get_data_frames()[0]
            
            with engine.begin() as conn:
                for _, player in df.iterrows():
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
                            "player_id": int(player["PLAYER_ID"]),
                            "full_name": player["PLAYER"],
                            "team_id": team_id,
                            "position": player.get("POSITION", None),
                            "now": datetime.now(),
                        },
                    )
                    player_count += 1
            
            logger.info(f"  [{i+1}/30] {team_abbrev}: {len(df)} players")
            
        except Exception as e:
            logger.error(f"  ❌ Error pulling roster for {team_abbrev}: {e}")
            continue
    
    logger.info(f"✅ Ingested {player_count} players")
    return player_count


# ==========================================
# MAIN INGESTION PIPELINE
# ==========================================

def run_full_ingestion(seasons: Optional[list] = None):
    """
    Run the complete data ingestion pipeline.
    
    🎓 PIPELINE DESIGN:
        1. Teams first (other tables reference team_id via foreign key)
        2. Games next (matches + team_game_stats)
        3. Players last (references team_id)
        
        Order matters because of foreign key constraints!
        This is a common pattern in ETL pipelines — load dimension tables
        before fact tables.
    
    Args:
        seasons: List of seasons to ingest. Default: ["2024-25", "2025-26"]
    """
    if seasons is None:
        seasons = ["2024-25", "2025-26"]
    
    engine = get_engine()
    
    logger.info("=" * 60)
    logger.info("🚀 STARTING FULL NBA DATA INGESTION")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    # Step 1: Teams (dimension table — load first)
    team_count = ingest_teams(engine)
    
    # Step 2: Game logs for each season (fact table)
    total_games = 0
    for season in seasons:
        game_count = ingest_season_games(engine, season=season)
        total_games += game_count
    
    # Step 3: Player rosters (dimension table)
    player_count = ingest_players(engine, season=seasons[-1])
    
    elapsed = time.time() - start_time
    
    logger.info("=" * 60)
    logger.info(f"✅ INGESTION COMPLETE in {elapsed:.1f}s")
    logger.info(f"   Teams:   {team_count}")
    logger.info(f"   Games:   {total_games}")
    logger.info(f"   Players: {player_count}")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_full_ingestion()
