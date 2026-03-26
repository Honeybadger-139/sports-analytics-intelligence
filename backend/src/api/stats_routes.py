"""
Statistics API routes — SCR-326.

Exposes Phase 6.4 Statistics module to the REST layer:

  GET  /api/v1/stats/team-ratings       → Bradley-Terry strength rankings
  GET  /api/v1/stats/home-court-effect  → Diff-in-Differences causal estimate
  POST /api/v1/stats/ab-test            → SPRT sequential A/B model comparison

WHY THESE ENDPOINTS MATTER (interview angle):
  These are not just analytics features — they demonstrate production-grade
  statistical rigour:
  - Bradley-Terry: schedule-adjusted team strength (Elo variant, used by FiveThirtyEight)
  - Diff-in-Diff:  causal inference from a natural experiment (COVID empty arenas)
  - SPRT:          sequential testing that saves 50-70% of evaluation samples

  A Data Scientist who can explain these at a Senior level (WHY and WHEN, not just HOW)
  will stand out from candidates who only know t-tests and chi-squared.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src import config
from src.data.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stats", tags=["statistics"])


# ── Request / Response Models ──────────────────────────────────────────────────


class TeamRatingEntry(BaseModel):
    rank: int
    team: str
    strength: float
    win_vs_average_team: float
    tier: str  # 'elite' | 'contender' | 'average' | 'rebuilding' | 'lottery'


class TeamRatingsResponse(BaseModel):
    season: str
    n_teams: int
    n_games_used: int
    rankings: List[TeamRatingEntry]
    summary: Dict[str, Any]
    model: str = "bradley_terry_mle"


class HomeCourtEffectResponse(BaseModel):
    did_estimate: float
    interpretation: str
    home_win_pct_with_fans: float
    home_win_pct_without_fans: float
    home_change: float
    away_change: float
    p_value: float
    confidence_interval_95: List[float]
    is_significant: bool
    sample_sizes: Dict[str, int]
    parallel_trends: Dict[str, Any]
    n_total_games: int


class ABTestRequest(BaseModel):
    model_a_name: str = Field(..., min_length=1, max_length=100, description="Name of model A")
    model_b_name: str = Field(..., min_length=1, max_length=100, description="Name of model B")
    model_a_predictions: List[int] = Field(
        ..., min_length=2, max_length=2000,
        description="Binary predictions from model A (0 or 1)",
    )
    model_b_predictions: List[int] = Field(
        ..., min_length=2, max_length=2000,
        description="Binary predictions from model B (0 or 1)",
    )
    actuals: List[int] = Field(
        ..., min_length=2, max_length=2000,
        description="Ground truth binary outcomes (0 or 1)",
    )
    alpha: float = Field(default=0.05, ge=0.01, le=0.20, description="Type I error rate")
    min_detectable_effect: float = Field(
        default=0.05, ge=0.01, le=0.30,
        description="Minimum accuracy improvement to detect (e.g. 0.05 = 5pp)",
    )


class ABTestResponse(BaseModel):
    model_a: str
    model_b: str
    n_observations: int
    model_a_accuracy: float
    model_b_accuracy: float
    current_llr: float
    decision: str   # 'continue' | 'accept_h0' | 'accept_h1'
    winner: Optional[str]
    is_significant: bool
    p_value_estimate: float
    stopped_early: bool
    config: Dict[str, Any]


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/team-ratings", response_model=TeamRatingsResponse)
async def get_team_ratings(
    season: str = Query(default=config.CURRENT_SEASON, description="Season string e.g. 2025-26"),
    top_n: int = Query(default=30, ge=1, le=30, description="Number of teams to return"),
    db: Session = Depends(get_db),
):
    """
    Return Bradley-Terry strength ratings for all NBA teams.

    The Bradley-Terry model fits latent strength parameters (α) to game outcomes:
      P(team_i beats team_j) = σ(α_i - α_j)

    This is schedule-adjusted — a team that beats strong opponents gets a higher
    rating than a team with the same record against weak opponents.

    Tier classification:
      - elite:      win probability vs average team ≥ 75%
      - contender:  ≥ 60%
      - average:    45-60%
      - rebuilding: 30-45%
      - lottery:    < 30%
    """
    try:
        from src.models.bayesian_ratings import load_ratings_from_db

        ratings = load_ratings_from_db(db_session=db, season=season)

        if not ratings.is_fitted:
            return TeamRatingsResponse(
                season=season,
                n_teams=0,
                n_games_used=0,
                rankings=[],
                summary={"error": f"No completed games found for season {season}"},
            )

        rankings_raw = ratings.get_rankings(top_n=top_n)
        summary = ratings.strength_summary()

        return TeamRatingsResponse(
            season=season,
            n_teams=len(rankings_raw),
            n_games_used=summary.get("n_teams", 0),
            rankings=[TeamRatingEntry(**r) for r in rankings_raw],
            summary=summary,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Team ratings error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compute team ratings: {str(exc)}")


@router.get("/home-court-effect", response_model=HomeCourtEffectResponse)
async def get_home_court_effect(
    db: Session = Depends(get_db),
):
    """
    Causal estimate of crowd presence on home court advantage.

    Uses Difference-in-Differences (DiD) with the COVID-19 empty-arena seasons
    (2020-21) as a natural experiment.

    DiD estimate = (home_win_rate_with_fans - home_win_rate_without_fans)
                 - (away_win_rate_with_fans - away_win_rate_without_fans)

    A positive DiD means crowd presence causally increases home court advantage,
    controlling for team quality and time trends.

    Key assumption: parallel trends — home/away win rates were trending similarly
    before the fanless season. The `parallel_trends` field in the response lets you
    verify this assumption.
    """
    try:
        from src.models.causal_inference import run_home_court_causal_analysis

        result = run_home_court_causal_analysis(db_session=db)

        if "error" in result:
            raise HTTPException(
                status_code=422,
                detail=f"Causal analysis failed: {result['error']}",
            )

        did = result["did_result"]
        return HomeCourtEffectResponse(
            did_estimate=did["did_estimate"],
            interpretation=did["interpretation"],
            home_win_pct_with_fans=did["home_win_pct_with_fans"],
            home_win_pct_without_fans=did["home_win_pct_without_fans"],
            home_change=did["home_change"],
            away_change=did["away_change"],
            p_value=did["p_value"],
            confidence_interval_95=list(did["confidence_interval_95"]),
            is_significant=did["is_significant"],
            sample_sizes=did["sample_sizes"],
            parallel_trends=result["parallel_trends"],
            n_total_games=result["n_total_games"],
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Home court causal analysis error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Causal analysis failed: {str(exc)}")


@router.post("/ab-test", response_model=ABTestResponse)
async def run_ab_test(
    payload: ABTestRequest,
):
    """
    Run a Sequential Probability Ratio Test (SPRT) to compare two models.

    Unlike classical A/B testing (fixed sample size, t-test), SPRT:
      - Evaluates after every observation
      - Stops as soon as the evidence is strong enough
      - Requires ~50-70% fewer samples on average
      - Controls both Type I (false positive) and Type II (false negative) error rates

    Decisions:
      - `accept_h0`:  models are statistically equivalent
      - `accept_h1`:  model A is significantly better (by min_detectable_effect)
      - `continue`:   not enough evidence yet (need more observations)

    If `stopped_early=True`, the test concluded before exhausting all observations.
    If `decision='continue'`, collect more game data before drawing conclusions.
    """
    try:
        from src.models.ab_testing import compare_models

        # Validate equal-length arrays
        if not (len(payload.model_a_predictions) == len(payload.model_b_predictions) == len(payload.actuals)):
            raise HTTPException(
                status_code=422,
                detail="model_a_predictions, model_b_predictions, and actuals must have the same length",
            )

        result = compare_models(
            model_a_name=payload.model_a_name,
            model_b_name=payload.model_b_name,
            model_a_preds=payload.model_a_predictions,
            model_b_preds=payload.model_b_predictions,
            actuals=payload.actuals,
            alpha=payload.alpha,
            min_detectable_effect=payload.min_detectable_effect,
        )

        final = result.get("final_result", {})
        stopped_early = (result.get("n_observations", 0) < len(payload.actuals))

        return ABTestResponse(
            model_a=result["model_a"],
            model_b=result["model_b"],
            n_observations=result["n_observations"],
            model_a_accuracy=result["model_a_accuracy"],
            model_b_accuracy=result["model_b_accuracy"],
            current_llr=result["current_llr"],
            decision=result["decision"],
            winner=result["winner"],
            is_significant=result["is_significant"],
            p_value_estimate=final.get("p_value_estimate", 1.0),
            stopped_early=stopped_early,
            config=result.get("config", {}),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("SPRT A/B test error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"A/B test failed: {str(exc)}")
