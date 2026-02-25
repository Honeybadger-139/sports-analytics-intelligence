"""
FastAPI Routes for Sports Analytics Intelligence Platform
=========================================================

All API endpoints for predictions, explanations, bet sizing,
and historical data access.
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
import pandas as pd

from src.data.db import get_db

router = APIRouter(prefix="/api/v1", tags=["predictions"])


# Lazy-load predictor (loaded once at first request)
_predictor = None

def get_predictor():
    global _predictor
    if _predictor is None:
        from src.models.predictor import Predictor
        _predictor = Predictor()
    return _predictor


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@router.get("/teams")
async def get_teams(db: Session = Depends(get_db)):
    """Get all NBA teams."""
    result = db.execute(text("SELECT team_id, abbreviation, full_name, city FROM teams ORDER BY abbreviation"))
    teams = [dict(row._mapping) for row in result]
    return {"teams": teams, "count": len(teams)}


@router.get("/matches")
async def get_matches(
    season: str = Query(default="2024-25"),
    team: Optional[str] = Query(default=None, description="Team abbreviation"),
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
):
    """Get recent matches with results."""
    query = """
        SELECT 
            m.game_id, m.game_date, m.season,
            ht.abbreviation as home_team,
            at.abbreviation as away_team,
            m.winner_team_id,
            ht_stats.points as home_score,
            at_stats.points as away_score
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        LEFT JOIN team_game_stats ht_stats ON m.game_id = ht_stats.game_id AND m.home_team_id = ht_stats.team_id
        LEFT JOIN team_game_stats at_stats ON m.game_id = at_stats.game_id AND m.away_team_id = at_stats.team_id
        WHERE m.season = :season
    """
    params = {"season": season, "limit": limit}
    
    if team:
        query += " AND (ht.abbreviation = :team OR at.abbreviation = :team)"
        params["team"] = team.upper()
    
    query += " ORDER BY m.game_date DESC LIMIT :limit"
    
    result = db.execute(text(query), params)
    matches = [dict(row._mapping) for row in result]
    return {"matches": matches, "count": len(matches)}


@router.get("/predictions/game/{game_id}")
async def predict_game(game_id: str, db: Session = Depends(get_db)):
    """Get AI prediction for a specific game with SHAP explanations."""
    predictor = get_predictor()
    
    # Load features for this game
    query = text("""
        SELECT 
            m.game_id,
            ht.abbreviation as home_team, ht.full_name as home_team_name,
            at.abbreviation as away_team, at.full_name as away_team_name,
            hf.win_pct_last_5, hf.win_pct_last_10,
            hf.avg_point_diff_last_5, hf.avg_point_diff_last_10,
            1 as is_home, hf.days_rest,
            CASE WHEN hf.is_back_to_back THEN 1 ELSE 0 END as is_back_to_back,
            hf.avg_off_rating_last_5, hf.avg_def_rating_last_5,
            hf.avg_pace_last_5, hf.avg_efg_last_5,
            hf.h2h_win_pct, hf.h2h_avg_margin, hf.current_streak,
            af.win_pct_last_5 as opp_win_pct_last_5,
            af.win_pct_last_10 as opp_win_pct_last_10,
            af.avg_point_diff_last_5 as opp_avg_point_diff_last_5,
            af.avg_point_diff_last_10 as opp_avg_point_diff_last_10,
            af.days_rest as opp_days_rest,
            CASE WHEN af.is_back_to_back THEN 1 ELSE 0 END as opp_is_back_to_back,
            af.avg_off_rating_last_5 as opp_avg_off_rating_last_5,
            af.avg_def_rating_last_5 as opp_avg_def_rating_last_5,
            af.avg_pace_last_5 as opp_avg_pace_last_5,
            af.avg_efg_last_5 as opp_avg_efg_last_5
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        LEFT JOIN match_features hf ON m.game_id = hf.game_id AND m.home_team_id = hf.team_id
        LEFT JOIN match_features af ON m.game_id = af.game_id AND m.away_team_id = af.team_id
        WHERE m.game_id = :game_id
    """)
    
    result = db.execute(query, {"game_id": game_id})
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    
    row_dict = dict(row._mapping)
    feature_cols = predictor.feature_columns
    features = pd.DataFrame([{col: float(row_dict.get(col, 0) or 0) for col in feature_cols}])
    
    predictions = predictor.predict_game(features)
    
    # SHAP explanation for the best model
    from src.models.explainability import explain_prediction
    explanation = {}
    if "xgboost" in predictor.models:
        explanation = explain_prediction(predictor.models["xgboost"], features, "xgboost")
    
    return {
        "game_id": game_id,
        "home_team": row_dict["home_team"],
        "home_team_name": row_dict["home_team_name"],
        "away_team": row_dict["away_team"],
        "away_team_name": row_dict["away_team_name"],
        "predictions": predictions,
        "explanation": explanation,
    }


@router.get("/predictions/bet-sizing")
async def get_bet_sizing(
    model_prob: float = Query(..., ge=0, le=1, description="Model probability"),
    odds: int = Query(..., description="American odds (e.g., +150 or -200)"),
    bankroll: float = Query(default=1000, description="Current bankroll"),
    kelly_fraction: float = Query(default=0.25, ge=0.1, le=1.0),
):
    """Calculate optimal bet size using Kelly Criterion."""
    from src.models.bet_sizing import american_to_decimal, calculate_bet_amount
    
    decimal_odds = american_to_decimal(odds)
    result = calculate_bet_amount(bankroll, model_prob, decimal_odds, kelly_fraction)
    return result


@router.get("/standings")
async def get_standings(
    season: str = Query(default="2024-25"),
    db: Session = Depends(get_db),
):
    """Get team standings based on win-loss record."""
    query = text("""
        WITH team_records AS (
            SELECT 
                t.team_id,
                t.abbreviation,
                t.full_name,
                COUNT(*) as games_played,
                SUM(CASE WHEN m.winner_team_id = t.team_id THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN m.winner_team_id != t.team_id THEN 1 ELSE 0 END) as losses
            FROM teams t
            JOIN (
                SELECT game_id, home_team_id as team_id, winner_team_id FROM matches WHERE season = :season
                UNION ALL
                SELECT game_id, away_team_id as team_id, winner_team_id FROM matches WHERE season = :season
            ) m ON t.team_id = m.team_id
            GROUP BY t.team_id, t.abbreviation, t.full_name
        )
        SELECT *,
            ROUND(wins::numeric / NULLIF(games_played, 0), 3) as win_pct
        FROM team_records
        ORDER BY win_pct DESC
    """)
    
    result = db.execute(query, {"season": season})
    standings = [dict(row._mapping) for row in result]
    return {"standings": standings, "season": season}


@router.get("/features/{game_id}")
async def get_features(game_id: str, db: Session = Depends(get_db)):
    """Get computed features for a specific game."""
    query = text("""
        SELECT mf.*, t.abbreviation, t.full_name
        FROM match_features mf
        JOIN teams t ON mf.team_id = t.team_id
        WHERE mf.game_id = :game_id
    """)
    
    result = db.execute(query, {"game_id": game_id})
    features = [dict(row._mapping) for row in result]
    
    if not features:
        raise HTTPException(status_code=404, detail=f"Features not found for game {game_id}")
    
    return {"game_id": game_id, "features": features}
# ==========================================
# SYSTEM STATUS & AUDIT ROUTES
# ==========================================

@router.get("/system/status")
def get_system_status(db: Session = Depends(get_db)):
    """
    Get the health and history of the data pipeline.
    
    🎓 WHY THIS MATTERS:
        Observability is a key difference between a "script" and a "product."
        This endpoint gives the frontend a way to show users if the data
        is fresh or if a sync failed.
    """
    try:
        # 1. Get database connectivity
        db_status = "online"
        try:
            db.execute(text("SELECT 1"))
        except Exception:
            db_status = "offline"

        # 2. Get recent audit logs
        audit_logs = db.execute(text("""
            SELECT id, sync_time, module, status, records_processed, records_inserted, errors, details
            FROM pipeline_audit
            ORDER BY sync_time DESC
            LIMIT 10
        """)).fetchall()
        
        # Format logs as dictionaries
        logs = []
        for log in audit_logs:
            logs.append({
                "id": log.id,
                "sync_time": log.sync_time.isoformat(),
                "module": log.module,
                "status": log.status,
                "processed": log.records_processed,
                "inserted": log.records_inserted,
                "errors": log.errors,
                "details": log.details
            })

        # 3. Get record counts for current season
        # Using CURRENT_SEASON from config
        from src import config
        season = config.CURRENT_SEASON
        
        matches_count = db.execute(text("SELECT COUNT(*) FROM matches WHERE season = :s"), {"s": season}).scalar()
        features_count = db.execute(text("SELECT COUNT(*) FROM match_features WHERE game_id IN (SELECT game_id FROM matches WHERE season = :s)"), {"s": season}).scalar()
        players_count = db.execute(text("SELECT COUNT(*) FROM players WHERE is_active = TRUE")).scalar()

        return {
            "status": "healthy" if db_status == "online" else "degraded",
            "database": db_status,
            "pipeline": {
                "last_sync": logs[0]["sync_time"] if logs else None,
                "last_status": logs[0]["status"] if logs else "unknown"
            },
            "stats": {
                "season": season,
                "matches": matches_count,
                "features": features_count,
                "active_players": players_count
            },
            "audit_history": logs
        }
    except Exception as e:
        logger.error(f"Error fetching system status: {e}")
        return {"status": "error", "message": str(e)}
