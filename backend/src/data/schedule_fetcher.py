"""
schedule_fetcher.py — SCR-331 / SCR-336
=========================================

Fetches today's + tomorrow's NBA schedule and upserts the games into the
`matches` table as status='scheduled' (is_completed=False).

Then immediately runs base ML predictions for each upcoming game so that
/api/v1/predictions/today can return them even before the games are played.

WHY THIS APPROACH:
  The existing ingest_season_games() fetches completed game logs via ESPN
  box scores.  For upcoming games we use EspnFetcher.fetch_scoreboard(date),
  which hits site.api.espn.com — GCP-friendly, no API key, no IP blocking.

  Previously this used nba_api.ScoreboardV2 (stats.nba.com) which is
  IP-blocked from GCP Cloud Run — causing 30s timeout failures on every
  incremental run.  Replaced as part of SCR-336.

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
from datetime import date, datetime, timedelta
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
# Schedule retrieval — ESPN-based (replaces nba_api.ScoreboardV2)
# ---------------------------------------------------------------------------

def _parse_espn_event(event: dict, season: str) -> ScheduledGame | None:
    """
    Parse a raw ESPN scoreboard event dict into a ScheduledGame.

    Returns None if the event is missing required fields or is a non-real
    game (All-Star, exhibition, pre-season).

    ESPN event structure (key paths used here):
      event["id"]                                       → ESPN game ID
      event["competitions"][0]["date"]                  → ISO-8601 start time
      event["competitions"][0]["type"]["abbreviation"]  → "STD"/"ASG"/etc.
      event["competitions"][0]["competitors"]           → list of 2 dicts
        competitor["homeAway"]                          → "home" or "away"
        competitor["team"]["id"]                        → ESPN integer team ID
        competitor["team"]["abbreviation"]              → e.g. "LAL"
      event["competitions"][0]["venue"]["fullName"]     → arena name (optional)
    """
    event_id = str(event.get("id") or "").strip()
    if not event_id:
        return None

    competitions: list[dict] = event.get("competitions") or []
    if not competitions:
        return None
    comp = competitions[0]

    # Skip non-real games: All-Star, exhibitions, pre-season
    comp_type_abbr = (
        (comp.get("type") or {}).get("abbreviation") or ""
    ).upper()
    if comp_type_abbr in {"ASG", "ALLSTAR", "ASW", "EXH", "PRE"}:
        logger.debug(
            "[schedule_fetcher] skipping non-regular event %s (type=%s)",
            event_id, comp_type_abbr,
        )
        return None

    # Parse date — ESPN returns ISO-8601 with Z or offset
    raw_date = comp.get("date") or event.get("date") or ""
    try:
        normalised = raw_date.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalised)
        game_date = dt.date()
    except (ValueError, AttributeError):
        game_date = date.today()

    # Extract home / away team IDs and abbreviations from competitors list
    home_team_id: int | None = None
    away_team_id: int | None = None
    home_abbr = "???"
    away_abbr = "???"

    for competitor in comp.get("competitors") or []:
        home_away = (competitor.get("homeAway") or "").lower()
        team = competitor.get("team") or {}
        try:
            tid = int(team.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if tid == 0:
            continue
        abbr = (team.get("abbreviation") or "???").strip()
        if home_away == "home":
            home_team_id = tid
            home_abbr = abbr
        elif home_away == "away":
            away_team_id = tid
            away_abbr = abbr

    if home_team_id is None or away_team_id is None:
        logger.debug(
            "[schedule_fetcher] event %s missing home or away team, skipping",
            event_id,
        )
        return None

    arena = ((comp.get("venue") or {}).get("fullName") or "").strip() or None

    return ScheduledGame(
        game_id=event_id,
        game_date=game_date,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_team_abbr=home_abbr,
        away_team_abbr=away_abbr,
        season=season,
        arena=arena,
    )


def _fetch_scoreboard_games(target_date: date, season: str) -> list[ScheduledGame]:
    """
    Pull games for target_date using EspnFetcher.fetch_scoreboard.

    Replaces nba_api.ScoreboardV2 (stats.nba.com — IP-blocked on GCP).
    ESPN's CDN endpoint (site.api.espn.com) works natively from Cloud Run.
    """
    from src.data.espn_fetcher import EspnFetcher

    fetcher = EspnFetcher()
    try:
        events = fetcher.fetch_scoreboard(target_date)
    except Exception as exc:
        logger.warning(
            "[schedule_fetcher] ESPN scoreboard failed for %s: %s",
            target_date, exc,
        )
        return []

    games: list[ScheduledGame] = []
    for event in events:
        game = _parse_espn_event(event, season)
        if game is not None:
            games.append(game)
    return games


def fetch_schedule_for_dates(
    target_dates: list[date],
    season: str,
    delay_between_calls: float = 1.0,
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

    Joins to `teams.team_id` (ESPN integer IDs after SCR-332 migration)
    to resolve the DB surrogate PK used in home_team_id / away_team_id FKs.
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

    Note: ensure_pre_game_columns() is no longer called here.  The
    is_pre_game / news_context / enriched_at columns are added by Alembic
    migration 0006 at startup, avoiding DDL-inside-request session corruption.
    """
    if not games:
        return 0

    try:
        import pandas as pd
        from sqlalchemy.orm import Session
        from src.models.predictor import Predictor
        from src.data.prediction_store import persist_game_predictions
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
    Convenience function called from run_espn_ingestion.py.

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
