"""
schedule_fetcher.py — SCR-331

Fetches today's + tomorrow's NBA schedule and upserts the games into the
`matches` table as status='scheduled' (is_completed=False).

Then immediately runs base ML predictions for each upcoming game so that
/api/v1/predictions/today can return them even before the games are played.

WHY THIS APPROACH:
  The existing ingest_season_games() fetches completed game logs via
  TeamGameLog (one call per team, 30 calls total).  For upcoming games
  we just need the schedule — ScoreboardV2 returns the full day's slate
  in a single API call.  We only fall back to LeagueScheduleV2 for
  tomorrow's games since ScoreboardV2 only covers the current day.

FLOW:
  1. fetch_schedule(date)   → list[ScheduledGame]
  2. upsert_scheduled_games → INSERT INTO matches (is_completed=False)
  3. ensure_team_features   → build "as-of-today" features for each team
  4. run_base_predictions   → INSERT INTO predictions (is_pre_game=True)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger("gamethread.schedule_fetcher")


@dataclass
class ScheduledGame:
    game_id: str
    game_date: date
    home_team_id: int
    away_team_id: int
    home_team_abbr: str
    away_team_abbr: str
    season: str
    arena: Optional[str] = None


# ---------------------------------------------------------------------------
# Schedule retrieval
# ---------------------------------------------------------------------------

def _fetch_scoreboard_games(target_date: date, season: str) -> list[ScheduledGame]:
    """Pull games for target_date using ScoreboardV2 (single API call)."""
    try:
        from nba_api.stats.endpoints import scoreboardv2
        date_str = target_date.strftime("%m/%d/%Y")
        board = scoreboardv2.ScoreboardV2(game_date=date_str, timeout=30)
        game_header = board.game_header.get_data_frame()
        team_map = _build_team_id_map()

        games: list[ScheduledGame] = []
        for _, row in game_header.iterrows():
            game_id = str(row.get("GAME_ID", "")).strip()
            if not game_id:
                continue
            home_id = int(row.get("HOME_TEAM_ID", 0))
            away_id = int(row.get("VISITOR_TEAM_ID", 0))
            home_abbr = team_map.get(home_id, "???")
            away_abbr = team_map.get(away_id, "???")
            games.append(ScheduledGame(
                game_id=game_id,
                game_date=target_date,
                home_team_id=home_id,
                away_team_id=away_id,
                home_team_abbr=home_abbr,
                away_team_abbr=away_abbr,
                season=season,
                arena=str(row.get("ARENA_NAME", "") or ""),
            ))
        return games
    except Exception as exc:
        logger.warning("[schedule_fetcher] ScoreboardV2 failed for %s: %s", target_date, exc)
        return []


def _build_team_id_map() -> dict[int, str]:
    """Return {team_id: abbreviation} for all 30 NBA teams."""
    try:
        from nba_api.stats.static import teams as nba_teams
        return {t["id"]: t["abbreviation"] for t in nba_teams.get_teams()}
    except Exception:
        return {}


def fetch_schedule_for_dates(
    target_dates: list[date],
    season: str,
    delay_between_calls: float = 1.5,
) -> list[ScheduledGame]:
    """Fetch schedule for a list of dates, returning all upcoming games."""
    all_games: list[ScheduledGame] = []
    for i, d in enumerate(target_dates):
        if i > 0:
            time.sleep(delay_between_calls)
        games = _fetch_scoreboard_games(d, season)
        logger.info("[schedule_fetcher] %s: found %d game(s)", d.isoformat(), len(games))
        all_games.extend(games)
    return all_games


# ---------------------------------------------------------------------------
# Database upsert
# ---------------------------------------------------------------------------

def upsert_scheduled_games(engine, games: list[ScheduledGame]) -> int:
    """
    Insert upcoming games into `matches` with is_completed=False.
    Uses ON CONFLICT DO NOTHING so completed games are never overwritten.
    """
    if not games:
        return 0

    from sqlalchemy import text

    inserted = 0
    with engine.begin() as conn:
        for g in games:
            result = conn.execute(
                text("""
                    INSERT INTO matches (
                        game_id, game_date, season,
                        home_team_id, away_team_id,
                        is_completed, home_score, away_score, winner_team_id
                    )
                    SELECT
                        :game_id, :game_date, :season,
                        ht.id, at.id,
                        FALSE, NULL, NULL, NULL
                    FROM teams ht, teams at
                    WHERE ht.team_id = :home_team_id AND at.team_id = :away_team_id
                    ON CONFLICT (game_id) DO NOTHING
                """),
                {
                    "game_id": g.game_id,
                    "game_date": g.game_date,
                    "season": g.season,
                    "home_team_id": g.home_team_id,
                    "away_team_id": g.away_team_id,
                },
            )
            inserted += result.rowcount

    logger.info("[schedule_fetcher] upserted %d new scheduled game(s)", inserted)
    return inserted


# ---------------------------------------------------------------------------
# Feature snapshot for upcoming games
# ---------------------------------------------------------------------------

def _get_latest_team_features(engine, team_id: int, season: str) -> dict:
    """
    Return the most recent match_features row for a team as the
    'as-of-today' feature snapshot for upcoming game prediction.
    """
    from sqlalchemy import text

    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT
                    mf.win_pct_last_5, mf.win_pct_last_10,
                    mf.avg_point_diff_last_5, mf.avg_point_diff_last_10,
                    mf.days_rest, mf.is_back_to_back,
                    mf.avg_off_rating_last_5, mf.avg_def_rating_last_5,
                    mf.avg_pace_last_5, mf.avg_efg_last_5,
                    mf.h2h_win_pct, mf.h2h_avg_margin, mf.current_streak
                FROM match_features mf
                JOIN matches m ON mf.game_id = m.game_id AND mf.team_id = :team_id
                WHERE m.season = :season AND m.is_completed = TRUE
                ORDER BY m.game_date DESC
                LIMIT 1
            """),
            {"team_id": team_id, "season": season},
        ).fetchone()

    if row:
        return dict(row._mapping)
    # Neutral defaults when no history exists for this team/season
    return {
        "win_pct_last_5": 0.5, "win_pct_last_10": 0.5,
        "avg_point_diff_last_5": 0.0, "avg_point_diff_last_10": 0.0,
        "days_rest": 2, "is_back_to_back": False,
        "avg_off_rating_last_5": 112.0, "avg_def_rating_last_5": 112.0,
        "avg_pace_last_5": 100.0, "avg_efg_last_5": 0.53,
        "h2h_win_pct": 0.5, "h2h_avg_margin": 0.0, "current_streak": 0,
    }


def _build_feature_row(
    home_features: dict,
    away_features: dict,
) -> dict:
    """
    Compose the flat feature dict the Predictor expects.
    Home team gets is_home=1; away team's features are prefixed opp_.
    """
    return {
        "win_pct_last_5":              float(home_features.get("win_pct_last_5", 0.5)),
        "win_pct_last_10":             float(home_features.get("win_pct_last_10", 0.5)),
        "avg_point_diff_last_5":       float(home_features.get("avg_point_diff_last_5", 0.0)),
        "avg_point_diff_last_10":      float(home_features.get("avg_point_diff_last_10", 0.0)),
        "is_home":                     1.0,
        "days_rest":                   float(home_features.get("days_rest", 2)),
        "is_back_to_back":             float(bool(home_features.get("is_back_to_back", False))),
        "avg_off_rating_last_5":       float(home_features.get("avg_off_rating_last_5", 112.0)),
        "avg_def_rating_last_5":       float(home_features.get("avg_def_rating_last_5", 112.0)),
        "avg_pace_last_5":             float(home_features.get("avg_pace_last_5", 100.0)),
        "avg_efg_last_5":              float(home_features.get("avg_efg_last_5", 0.53)),
        "h2h_win_pct":                 float(home_features.get("h2h_win_pct", 0.5)),
        "h2h_avg_margin":              float(home_features.get("h2h_avg_margin", 0.0)),
        "current_streak":              float(home_features.get("current_streak", 0)),
        "opp_win_pct_last_5":          float(away_features.get("win_pct_last_5", 0.5)),
        "opp_win_pct_last_10":         float(away_features.get("win_pct_last_10", 0.5)),
        "opp_avg_point_diff_last_5":   float(away_features.get("avg_point_diff_last_5", 0.0)),
        "opp_avg_point_diff_last_10":  float(away_features.get("avg_point_diff_last_10", 0.0)),
        "opp_days_rest":               float(away_features.get("days_rest", 2)),
        "opp_is_back_to_back":         float(bool(away_features.get("is_back_to_back", False))),
        "opp_avg_off_rating_last_5":   float(away_features.get("avg_off_rating_last_5", 112.0)),
        "opp_avg_def_rating_last_5":   float(away_features.get("avg_def_rating_last_5", 112.0)),
        "opp_avg_pace_last_5":         float(away_features.get("avg_pace_last_5", 100.0)),
        "opp_avg_efg_last_5":          float(away_features.get("avg_efg_last_5", 0.53)),
    }


# ---------------------------------------------------------------------------
# Base ML predictions for scheduled games
# ---------------------------------------------------------------------------

def run_base_predictions_for_schedule(engine, games: list[ScheduledGame], season: str) -> int:
    """
    For each scheduled game, build features from the teams' most recent stats
    and run the Predictor. Persist results with is_pre_game=True.

    Returns the number of games predicted.
    """
    if not games:
        return 0

    try:
        import pandas as pd
        from sqlalchemy.orm import Session
        from src.models.predictor import Predictor
        from src.data.prediction_store import persist_game_predictions, ensure_pre_game_columns
    except ImportError as exc:
        logger.warning("[schedule_fetcher] ML deps not available, skipping predictions: %s", exc)
        return 0

    try:
        predictor = Predictor()
    except Exception as exc:
        logger.warning("[schedule_fetcher] Predictor init failed: %s", exc)
        return 0

    predicted = 0
    with Session(engine) as session:
        ensure_pre_game_columns(session)
        for game in games:
            try:
                home_f = _get_latest_team_features(engine, game.home_team_id, season)
                away_f = _get_latest_team_features(engine, game.away_team_id, season)
                feature_row = _build_feature_row(home_f, away_f)
                features_df = pd.DataFrame([{
                    col: float(feature_row.get(col, 0) or 0)
                    for col in predictor.feature_columns
                }])
                predictions = predictor.predict_game(features_df)
                shap_factors = predictor.explain_game(features_df, top_n=5)
                persist_game_predictions(
                    session,
                    game_id=game.game_id,
                    predictions=predictions,
                    shap_factors_by_model=shap_factors,
                    is_pre_game=True,
                )
                predicted += 1
                logger.info(
                    "[schedule_fetcher] predicted %s vs %s → ensemble %.1f%%",
                    game.home_team_abbr,
                    game.away_team_abbr,
                    predictions.get("ensemble", {}).get("home_win_prob", 0) * 100,
                )
            except Exception as exc:
                logger.warning(
                    "[schedule_fetcher] prediction failed for %s: %s", game.game_id, exc
                )

    return predicted


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def fetch_and_predict_upcoming(engine, season: str, days_ahead: int = 1) -> dict:
    """
    Convenience function called from run_ingestion.py.

    Fetches today + tomorrow, upserts scheduled games, runs base predictions.
    Returns a summary dict for logging.
    """
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days_ahead + 1)]

    games = fetch_schedule_for_dates(target_dates, season)
    upserted = upsert_scheduled_games(engine, games)
    predicted = run_base_predictions_for_schedule(engine, games, season)

    return {
        "dates_checked": [d.isoformat() for d in target_dates],
        "games_found": len(games),
        "games_upserted": upserted,
        "games_predicted": predicted,
    }
