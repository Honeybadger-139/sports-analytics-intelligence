"""
Time-Series Forecast API routes — SCR-327.

Exposes Phase 6.5 Time-Series module to the REST layer:

  GET /api/v1/forecast/{team_name}           → 14-day Prophet+ARIMA win-rate forecast
  GET /api/v1/forecast/{team_name}/momentum  → Momentum score, trend, current streak
  GET /api/v1/forecast/league/momentum       → All teams ranked by momentum (league view)

WHY THIS MATTERS (interview angle):
  Static features (season win %) miss the most important signal: MOMENTUM.
  A 30-30 team on a 10-0 streak is a completely different bet from a 30-30 team
  going 0-10. These endpoints surface that temporal signal via:

  - Prophet:         14-day win-rate forecast + confidence intervals
  - ARIMA:           classical baseline for anomaly detection
  - MomentumEngine:  exponentially-weighted recent form with streak detection

Part of: Phase 6.5 Time-Series Forecasting (SCR-327)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src import config
from src.data.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/forecast", tags=["forecasting"])


# ── Response Models ───────────────────────────────────────────────────────────


class ForecastPoint(BaseModel):
    date: str
    prophet_forecast: Optional[float] = None
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    arima_forecast: Optional[float] = None


class MomentumSummary(BaseModel):
    momentum_score: float
    trend: str           # 'hot' | 'cold' | 'neutral'
    streak_type: str     # 'win' | 'loss' | 'none'
    streak_length: int
    recent_win_pct: float
    n_recent_games: int
    total_games_analysed: int


class TeamForecastResponse(BaseModel):
    team: str
    season: str
    n_games_used: int
    current_win_rate: float
    last_10_win_rate: float
    momentum: MomentumSummary
    forecast: List[ForecastPoint]
    changepoints: List[Dict[str, Any]]
    model: str


class TeamMomentumResponse(BaseModel):
    team: str
    season: str
    momentum: MomentumSummary


class LeagueMomentumEntry(BaseModel):
    rank: int
    team: str
    momentum_score: float
    trend: str
    streak_type: str
    streak_length: int
    recent_win_pct: float
    season_win_rate: float


class LeagueMomentumResponse(BaseModel):
    season: str
    n_teams: int
    teams: List[LeagueMomentumEntry]


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/league/momentum", response_model=LeagueMomentumResponse)
async def get_league_momentum(
    season: str = Query(default=config.CURRENT_SEASON),
    db: Session = Depends(get_db),
):
    """
    Return all NBA teams ranked by current momentum score.

    Momentum = exponentially-weighted win rate over the last 10 games.
    Recent games carry more weight (decay_factor=0.85).

    High momentum (>0.65) = hot streak — team is performing above season baseline.
    Low momentum  (<0.35) = cold streak — team underperforming season baseline.

    Use this for a league-wide heat map of "who's peaking right now".
    """
    try:
        from sqlalchemy import text
        from src.models.timeseries_forecaster import MomentumEngine

        # Load all teams with their recent game results
        rows = db.execute(
            text(
                """
                SELECT
                    t.full_name,
                    m.game_date,
                    (m.winner_team_id = t.team_id) AS won
                FROM matches m
                JOIN teams t ON (m.home_team_id = t.team_id OR m.away_team_id = t.team_id)
                WHERE m.is_completed = TRUE
                  AND m.season = :season
                ORDER BY t.full_name, m.game_date ASC
                """
            ),
            {"season": season},
        ).fetchall()

        if not rows:
            return LeagueMomentumResponse(season=season, n_teams=0, teams=[])

        # Group by team
        teams_data: Dict[str, Dict] = {}
        for team_name, game_date, won in rows:
            if team_name not in teams_data:
                teams_data[team_name] = {"dates": [], "results": []}
            teams_data[team_name]["dates"].append(game_date)
            teams_data[team_name]["results"].append(bool(won))

        engine = MomentumEngine(window=10, decay_factor=0.85)
        team_entries = []

        for team_name, data in teams_data.items():
            results = data["results"]
            if not results:
                continue

            momentum = engine.get_team_momentum(data["dates"], results)
            season_win_rate = round(sum(results) / len(results), 4) if results else 0.5

            team_entries.append({
                "team": team_name,
                "momentum_score": momentum["momentum_score"],
                "trend": momentum["trend"],
                "streak_type": momentum["streak_type"],
                "streak_length": momentum["streak_length"],
                "recent_win_pct": momentum["recent_win_pct"],
                "season_win_rate": season_win_rate,
            })

        # Sort by momentum score descending
        team_entries.sort(key=lambda x: x["momentum_score"], reverse=True)
        ranked = [
            LeagueMomentumEntry(rank=i + 1, **entry)
            for i, entry in enumerate(team_entries)
        ]

        return LeagueMomentumResponse(season=season, n_teams=len(ranked), teams=ranked)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("League momentum error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compute league momentum: {str(exc)}")


@router.get("/{team_name}/momentum", response_model=TeamMomentumResponse)
async def get_team_momentum(
    team_name: str,
    season: str = Query(default=config.CURRENT_SEASON),
    db: Session = Depends(get_db),
):
    """
    Return the momentum score, trend, and current streak for a single team.

    Faster than the full forecast endpoint — returns just the real-time
    momentum signal without running Prophet/ARIMA.

    Use this for real-time pre-game checks:
      - Is this team on a hot streak heading into tonight's game?
      - What's their recent win rate over the last 10 games?
      - Are they on a win streak or a losing skid?
    """
    try:
        from src.models.timeseries_forecaster import TeamPerformanceForecaster

        forecaster = TeamPerformanceForecaster()
        games_df = forecaster._load_team_games(db, team_name, season)

        if games_df is None or games_df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No game data found for team '{team_name}' in season {season}. "
                       "Check the team name (partial match supported, e.g. 'Lakers', 'lakers', 'los angeles lakers').",
            )

        games_df = games_df.sort_values("game_date")
        dates = games_df["game_date"].tolist()
        results = games_df["won"].tolist()

        momentum = forecaster.momentum_engine.get_team_momentum(dates, results)

        return TeamMomentumResponse(
            team=team_name,
            season=season,
            momentum=MomentumSummary(**momentum),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Team momentum error for %s: %s", team_name, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compute momentum for {team_name}: {str(exc)}")


@router.get("/{team_name}", response_model=TeamForecastResponse)
async def get_team_forecast(
    team_name: str,
    season: str = Query(default=config.CURRENT_SEASON),
    db: Session = Depends(get_db),
):
    """
    Return a 14-day win-rate forecast for a team using Prophet + ARIMA ensemble.

    Forecast pipeline:
      1. Load all completed games for the team from PostgreSQL
      2. Compute 7-game rolling win rate as the time series
      3. Fit ARIMA(2,1,2) as the classical baseline
      4. Fit Prophet with changepoint detection and weekly seasonality
      5. Return 14-day forward forecast with 95% confidence intervals

    Response includes:
      - `forecast`: 14 data points, each with Prophet forecast + CI + ARIMA overlay
      - `momentum`:  real-time momentum score and current streak
      - `changepoints`: dates where Prophet detected significant trend changes
        (useful for identifying roster trades, injuries, or coaching changes)

    Team name is matched case-insensitively with partial matching:
      /api/v1/forecast/lakers   → Los Angeles Lakers
      /api/v1/forecast/celtics  → Boston Celtics
    """
    try:
        from src.models.timeseries_forecaster import TeamPerformanceForecaster

        forecaster = TeamPerformanceForecaster(forecast_days=14)
        result = forecaster.forecast_team(
            db_session=db,
            team_name=team_name,
            season=season,
        )

        if "error" in result and not result.get("forecast"):
            raise HTTPException(
                status_code=404,
                detail=result["error"],
            )

        # Parse response — be lenient with missing optional fields
        momentum_data = result.get("momentum") or {}
        forecast_data = result.get("forecast") or []

        return TeamForecastResponse(
            team=result["team"],
            season=result.get("season", season),
            n_games_used=result.get("n_games_used", 0),
            current_win_rate=result.get("current_win_rate", 0.0),
            last_10_win_rate=result.get("last_10_win_rate", 0.0),
            momentum=MomentumSummary(
                momentum_score=momentum_data.get("momentum_score", 0.5),
                trend=momentum_data.get("trend", "neutral"),
                streak_type=momentum_data.get("streak_type", "none"),
                streak_length=momentum_data.get("streak_length", 0),
                recent_win_pct=momentum_data.get("recent_win_pct", 0.0),
                n_recent_games=momentum_data.get("n_recent_games", 0),
                total_games_analysed=momentum_data.get("total_games_analysed", 0),
            ),
            forecast=[ForecastPoint(**p) for p in forecast_data],
            changepoints=result.get("changepoints", []),
            model=result.get("model", "prophet+arima_ensemble"),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Team forecast error for %s: %s", team_name, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Forecast failed for {team_name}: {str(exc)}")
