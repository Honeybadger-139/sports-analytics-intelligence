#!/usr/bin/env python3
"""
run_espn_ingestion.py — SCR-332
================================
ESPN-based ingestion pipeline. Replaces nba_api / stats.nba.com calls.
Works natively from GCP Cloud Run (no IP blocking).

WHY ESPN over nba_api:
    - stats.nba.com aggressively rate-limits Cloud Run egress IPs — requests
      fail silently or return 403 in production.
    - ESPN's undocumented JSON API (site.api.espn.com/v2) does not require an
      API key and is reliably accessible from GCP.
    - ESPN provides position data on the roster endpoint, which nba_api does not
      surface cleanly — enabling the migration 0007 positional feature work.

Modes:
  --mode flush       : TRUNCATE all data tables then full reload (all 3 seasons).
                       Use for clean-slate environment setup or schema changes.
  --mode backfill    : Load all 3 seasons without truncating (safe re-run).
                       Idempotent — uses ON CONFLICT DO UPDATE throughout.
  --mode incremental : Load only games from yesterday onwards (daily Cloud
                       Scheduler job). Fast — typically 1-3 games per run.

Usage:
  python pipeline/run_espn_ingestion.py --mode flush
  python pipeline/run_espn_ingestion.py --mode backfill
  python pipeline/run_espn_ingestion.py --mode incremental

Environment variables required:
  DATABASE_URL   — PostgreSQL connection string (resolved from Secret Manager
                   if not set as a plain env var, matching the pattern in
                   run_ingestion.py).

Dockerfile.ingestion CMD to update:
  CMD ["python", "pipeline/run_espn_ingestion.py", "--mode", "incremental"]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import traceback
from datetime import date, datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

load_dotenv()

# ── Structured JSON logging (matches run_ingestion.py convention) ──────────────

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("gamethread.pipeline.espn_ingestion")


def log_event(event: str, level: str = "INFO", **fields: Any) -> None:
    payload = {
        "event": event,
        "level": level.upper(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    logger.log(
        getattr(logging, level.upper(), logging.INFO),
        json.dumps(payload, default=str),
    )


# ── Season definitions ─────────────────────────────────────────────────────────
# year = the calendar year in which the season *ends* (ESPN's convention).
# label = human-readable label stored in the DB season column.

SEASONS = [
    {"label": "2023-24", "year": 2024},
    {"label": "2024-25", "year": 2025},
    {"label": "2025-26", "year": 2026},
]


# ── Engine factory ─────────────────────────────────────────────────────────────

def _build_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine with conservative pool settings.

    Cloud Run jobs are short-lived, so pool_size=2 avoids unnecessary
    connection slots on the Cloud SQL instance.
    """
    return create_engine(
        database_url,
        pool_size=2,
        max_overflow=4,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
        echo=False,
    )


def _resolve_database_url() -> str:
    """Read DATABASE_URL from env, with a GCP Secret Manager fallback.

    Mirrors the resolution order used in load_runtime_config() in
    run_ingestion.py, keeping operational behaviour consistent.
    """
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return url

    # Attempt Secret Manager lookup (only available inside GCP runtimes)
    project_id = (
        os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or ""
    ).strip()
    if project_id:
        try:
            from google.cloud import secretmanager  # type: ignore[import]

            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{project_id}/secrets/DATABASE_URL/versions/latest"
            response = client.access_secret_version(request={"name": name})
            secret_url = response.payload.data.decode("utf-8").strip()
            if secret_url:
                log_event("database_url_resolved_from_secret_manager", project_id=project_id)
                return secret_url
        except Exception as exc:
            log_event(
                "secret_manager_lookup_failed",
                level="WARNING",
                error=str(exc),
            )

    raise ValueError(
        "DATABASE_URL is not set and could not be resolved from Secret Manager. "
        "Set DATABASE_URL as an environment variable or Secret Manager secret."
    )


# ── Table helpers ──────────────────────────────────────────────────────────────

def _table_exists(engine: Engine, table_name: str) -> bool:
    """Return True if the given table exists in the public schema."""
    insp = inspect(engine)
    return insp.has_table(table_name)


# ── Flush (TRUNCATE + CASCADE) ─────────────────────────────────────────────────

def flush_tables(engine: Engine) -> None:
    """TRUNCATE all data tables in FK-safe dependency order.

    Using CASCADE lets Postgres handle the foreign-key ordering automatically.
    Tables are listed leaf-first anyway for explicitness and safety on
    Postgres versions that do not propagate CASCADE across all FK types.

    Tables flushed:
        player_season_stats  (references player_game_stats / players)
        player_game_stats    (references matches, players)
        match_features       (references matches)
        predictions          (references matches)
        team_game_stats      (references matches, teams — optional table)
        matches              (references teams)
        players              (references teams)
        teams                (root dimension)

    Note: predictions and match_features are flushed here so the reloaded
    historical match rows are self-consistent. Pre-game predictions for future
    games will be re-generated by the schedule_fetcher after ingestion completes.
    """
    tables_in_order = [
        "player_season_stats",
        "player_game_stats",
        "match_features",
        "predictions",
        "team_game_stats",
        "matches",
        "players",
        "teams",
    ]

    log_event("flush_tables_start", tables=tables_in_order)

    with engine.begin() as conn:
        for table in tables_in_order:
            if _table_exists(engine, table):
                conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                log_event("table_truncated", table=table)
            else:
                log_event("table_skip_not_found", table=table, level="WARNING")

    log_event("flush_tables_complete")


# ── Teams ──────────────────────────────────────────────────────────────────────

def ingest_teams(fetcher: Any, engine: Engine) -> int:
    """Fetch all 30 NBA teams from ESPN and upsert into the teams table.

    Upsert strategy:
        ON CONFLICT (team_id) DO UPDATE — safe for repeated runs.
        team_id is ESPN's numeric team id stored as an INTEGER.

    Returns:
        Number of teams upserted.
    """
    from src.data.espn_transformer import transform_teams

    log_event("ingest_teams_start")

    raw_teams = fetcher.fetch_teams()
    if not raw_teams:
        log_event("ingest_teams_no_data", level="WARNING")
        return 0

    teams = transform_teams(raw_teams)
    if not teams:
        log_event("ingest_teams_transform_empty", level="WARNING")
        return 0

    upsert_sql = text(
        """
        INSERT INTO teams (
            team_id, full_name, abbreviation, city, conference, division
        )
        VALUES (
            :team_id, :full_name, :abbreviation, :city, :conference, :division
        )
        ON CONFLICT (team_id) DO UPDATE SET
            full_name    = EXCLUDED.full_name,
            abbreviation = EXCLUDED.abbreviation,
            city         = EXCLUDED.city,
            conference   = EXCLUDED.conference,
            division     = EXCLUDED.division
        """
    )

    with engine.begin() as conn:
        conn.execute(upsert_sql, teams)

    log_event("ingest_teams_complete", count=len(teams))
    return len(teams)


# ── Rosters / Players ──────────────────────────────────────────────────────────

def ingest_rosters(fetcher: Any, engine: Engine) -> int:
    """Fetch each team's active roster and upsert players with positions.

    The position column was added in migration 0007 specifically to surface
    ESPN's PG/SG/SF/PF/C data. The upsert always refreshes the position so
    that mid-season position changes are captured on each backfill.

    Returns:
        Total number of player rows upserted across all teams.
    """
    from src.data.espn_transformer import transform_players

    log_event("ingest_rosters_start")

    raw_teams = fetcher.fetch_teams()
    if not raw_teams:
        log_event("ingest_rosters_no_teams", level="WARNING")
        return 0

    upsert_sql = text(
        """
        INSERT INTO players (
            player_id, full_name, team_id, position, is_active
        )
        VALUES (
            :player_id, :full_name, :team_id, :position, :is_active
        )
        ON CONFLICT (player_id) DO UPDATE SET
            full_name = EXCLUDED.full_name,
            team_id   = EXCLUDED.team_id,
            position  = EXCLUDED.position,
            is_active = EXCLUDED.is_active
        """
    )

    total = 0
    for team in raw_teams:
        # raw_teams are raw ESPN dicts — use "id" key (not "team_id")
        team_id = str(team.get("id", ""))
        if not team_id:
            continue
        try:
            raw_players = fetcher.fetch_team_roster(team_id)
            if not raw_players:
                continue
            players = transform_players(raw_players, team_id)
            if not players:
                continue
            with engine.begin() as conn:
                conn.execute(upsert_sql, players)
            total += len(players)
            log_event("roster_ingested", team_id=team_id, player_count=len(players))
        except Exception as exc:
            log_event(
                "roster_ingest_failed",
                level="WARNING",
                team_id=team_id,
                error=str(exc),
            )

    log_event("ingest_rosters_complete", total_players=total)
    return total


# ── Single-season ingestion ────────────────────────────────────────────────────

def ingest_season(
    fetcher: Any,
    engine: Engine,
    season_label: str,
    season_year: int,
) -> dict[str, int]:
    """Ingest all completed games for one NBA season from ESPN.

    Steps:
        1. fetch_season_games(season_year) — returns a list of unique event IDs
           for every game (regular season + playoffs).
        2. For each game event ID:
           a. fetch_game_summary(game_id) — full boxscore JSON from ESPN.
           b. transform_game(raw) — produces a single dict for the matches table.
           c. transform_team_game_stats(raw) — produces 2 dicts (home + away) for
              team_game_stats (table is optional; skipped if not yet created).
           d. transform_player_game_stats(raw) — produces N dicts (one per player)
              for player_game_stats.
        3. Log progress every 50 games so Cloud Logging has heartbeat entries.
        4. Sleep 0.5s between game summary requests — polite rate limiting.

    Returns:
        {"games": int, "player_rows": int}
    """
    from src.data.espn_transformer import (
        transform_game,
        transform_player_game_stats,
        transform_team_game_stats,
    )

    log_event("season_ingest_start", season=season_label, season_year=season_year)

    # fetch_season_games returns a list of raw ESPN event dicts (from team schedule
    # endpoint), each with an "id" field.  We use transform_game on the event dict
    # (which has competitions at the root), then separately call fetch_game_summary
    # to get the boxscore for team/player stat transformers.
    events = fetcher.fetch_season_games(season_year)
    total_games = len(events)
    log_event("season_games_fetched", season=season_label, total_games=total_games)

    match_upsert = text(
        """
        INSERT INTO matches (
            game_id, game_date, season, home_team_id, away_team_id,
            home_score, away_score, winner_team_id, is_completed
        )
        VALUES (
            :game_id, :game_date, :season, :home_team_id, :away_team_id,
            :home_score, :away_score, :winner_team_id, :is_completed
        )
        ON CONFLICT (game_id) DO UPDATE SET
            game_date      = EXCLUDED.game_date,
            season         = EXCLUDED.season,
            home_team_id   = EXCLUDED.home_team_id,
            away_team_id   = EXCLUDED.away_team_id,
            home_score     = EXCLUDED.home_score,
            away_score     = EXCLUDED.away_score,
            winner_team_id = EXCLUDED.winner_team_id,
            is_completed   = EXCLUDED.is_completed
        """
    )

    team_game_upsert = text(
        """
        INSERT INTO team_game_stats (
            game_id, team_id,
            points, rebounds, assists, steals, blocks, turnovers,
            field_goal_pct, three_point_pct, free_throw_pct,
            offensive_rating, defensive_rating, pace,
            effective_fg_pct, true_shooting_pct
        )
        VALUES (
            :game_id, :team_id,
            :points, :rebounds, :assists, :steals, :blocks, :turnovers,
            :field_goal_pct, :three_point_pct, :free_throw_pct,
            :offensive_rating, :defensive_rating, :pace,
            :effective_fg_pct, :true_shooting_pct
        )
        ON CONFLICT (game_id, team_id) DO UPDATE SET
            points           = EXCLUDED.points,
            rebounds         = EXCLUDED.rebounds,
            assists          = EXCLUDED.assists,
            steals           = EXCLUDED.steals,
            blocks           = EXCLUDED.blocks,
            turnovers        = EXCLUDED.turnovers,
            field_goal_pct   = EXCLUDED.field_goal_pct,
            three_point_pct  = EXCLUDED.three_point_pct,
            free_throw_pct   = EXCLUDED.free_throw_pct,
            offensive_rating = EXCLUDED.offensive_rating,
            defensive_rating = EXCLUDED.defensive_rating,
            pace             = EXCLUDED.pace,
            effective_fg_pct = EXCLUDED.effective_fg_pct,
            true_shooting_pct = EXCLUDED.true_shooting_pct
        """
    )

    player_game_upsert = text(
        """
        INSERT INTO player_game_stats (
            game_id, player_id, team_id,
            minutes, points, rebounds, assists, steals, blocks, turnovers,
            personal_fouls, field_goals_made, field_goals_attempted, field_goal_pct,
            three_points_made, three_points_attempted, three_point_pct,
            free_throws_made, free_throws_attempted, free_throw_pct,
            plus_minus, fantasy_points
        )
        VALUES (
            :game_id, :player_id, :team_id,
            :minutes, :points, :rebounds, :assists, :steals, :blocks, :turnovers,
            :personal_fouls, :field_goals_made, :field_goals_attempted, :field_goal_pct,
            :three_points_made, :three_points_attempted, :three_point_pct,
            :free_throws_made, :free_throws_attempted, :free_throw_pct,
            :plus_minus, :fantasy_points
        )
        ON CONFLICT (game_id, player_id) DO UPDATE SET
            team_id                  = EXCLUDED.team_id,
            minutes                  = EXCLUDED.minutes,
            points                   = EXCLUDED.points,
            rebounds                 = EXCLUDED.rebounds,
            assists                  = EXCLUDED.assists,
            steals                   = EXCLUDED.steals,
            blocks                   = EXCLUDED.blocks,
            turnovers                = EXCLUDED.turnovers,
            personal_fouls           = EXCLUDED.personal_fouls,
            field_goals_made         = EXCLUDED.field_goals_made,
            field_goals_attempted    = EXCLUDED.field_goals_attempted,
            field_goal_pct           = EXCLUDED.field_goal_pct,
            three_points_made        = EXCLUDED.three_points_made,
            three_points_attempted   = EXCLUDED.three_points_attempted,
            three_point_pct          = EXCLUDED.three_point_pct,
            free_throws_made         = EXCLUDED.free_throws_made,
            free_throws_attempted    = EXCLUDED.free_throws_attempted,
            free_throw_pct           = EXCLUDED.free_throw_pct,
            plus_minus               = EXCLUDED.plus_minus,
            fantasy_points           = EXCLUDED.fantasy_points
        """
    )

    has_team_game_stats = _table_exists(engine, "team_game_stats")
    games_ingested = 0
    player_rows_ingested = 0

    for idx, event in enumerate(events, start=1):
        game_id = str(event.get("id", "")).strip()
        if not game_id:
            continue

        if idx % 50 == 0 or idx == 1:
            log_event(
                "season_ingest_progress",
                season=season_label,
                progress=f"{idx}/{total_games}",
                games_ingested=games_ingested,
                player_rows=player_rows_ingested,
            )

        try:
            # transform_game expects a raw schedule event dict (competitions at root)
            game_row = transform_game(event)
            if game_row is None:
                # Non-final game (future/in-progress) or All-Star event — skip
                continue

            with engine.begin() as conn:
                conn.execute(match_upsert, game_row)

                # Fetch box score for detailed team + player stats
                raw_summary = fetcher.fetch_game_summary(game_id)

                if has_team_game_stats:
                    team_rows = transform_team_game_stats(raw_summary, game_id)
                    if team_rows:
                        conn.execute(team_game_upsert, team_rows)

                player_rows = transform_player_game_stats(raw_summary, game_id)
                if player_rows:
                    conn.execute(player_game_upsert, player_rows)
                    player_rows_ingested += len(player_rows)

            games_ingested += 1

        except Exception as exc:
            log_event(
                "game_ingest_failed",
                level="WARNING",
                season=season_label,
                game_id=game_id,
                progress=f"{idx}/{total_games}",
                error=str(exc),
            )

        # Polite rate-limit — 0.5s between ESPN summary calls
        time.sleep(0.5)

    log_event(
        "season_ingest_complete",
        season=season_label,
        games_ingested=games_ingested,
        player_rows=player_rows_ingested,
        total_events=total_games,
    )
    return {"games": games_ingested, "player_rows": player_rows_ingested}


# ── Incremental ingestion ──────────────────────────────────────────────────────

def ingest_incremental(fetcher: Any, engine: Engine) -> dict[str, int]:
    """Ingest games from yesterday through tomorrow (window = 3 days).

    WHY a 3-day window:
        - Yesterday: catches any late-finishing games that may have landed
          after the previous nightly run.
        - Today: handles games completing during the current day's job.
        - Tomorrow: pre-populates the matches table with scheduled games so
          the pre-game prediction pipeline (schedule_fetcher) has rows to
          attach predictions to.

    Uses the current season label from the most recent SEASONS entry for
    the 'season' column on new rows.

    Returns:
        {"games": int, "player_rows": int}
    """
    today = date.today()
    date_from = today - timedelta(days=1)
    date_to = today + timedelta(days=1)

    log_event(
        "incremental_ingest_start",
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
    )

    # Determine the active season label (latest season in SEASONS list)
    current_season = SEASONS[-1]["label"]

    # fetch_games_in_range doesn't exist — use fetch_scoreboard per day and deduplicate
    seen_ids: set[str] = set()
    events: list[dict] = []
    check_date = date_from
    while check_date <= date_to:
        try:
            day_events = fetcher.fetch_scoreboard(check_date)
            for ev in day_events:
                eid = str(ev.get("id", "")).strip()
                if eid and eid not in seen_ids:
                    seen_ids.add(eid)
                    events.append(ev)
        except Exception as exc:
            log_event(
                "incremental_scoreboard_failed",
                level="WARNING",
                date=check_date.isoformat(),
                error=str(exc),
            )
        check_date += timedelta(days=1)

    log_event("incremental_games_found", count=len(events))

    if not events:
        log_event("incremental_no_games")
        return {"games": 0, "player_rows": 0}

    # Reuse the same upsert SQL as ingest_season (DRY via a helper)
    total = _ingest_events(fetcher, engine, events, current_season, context="incremental")
    log_event("incremental_ingest_complete", **total)
    return total


def _ingest_events(
    fetcher: Any,
    engine: Engine,
    events: list[dict],
    season_label: str,
    context: str = "batch",
) -> dict[str, int]:
    """Shared inner loop: upsert a list of raw ESPN event dicts.

    Extracted so that ingest_incremental does not duplicate the upsert SQL.
    Each event is a raw ESPN event dict (competitions at root, as returned by
    fetch_scoreboard or fetch_season_games). We call transform_game on the
    event, then fetch_game_summary for the boxscore stats.
    """
    from src.data.espn_transformer import (
        transform_game,
        transform_player_game_stats,
        transform_team_game_stats,
    )

    match_upsert = text(
        """
        INSERT INTO matches (
            game_id, game_date, season, home_team_id, away_team_id,
            home_score, away_score, winner_team_id, is_completed
        )
        VALUES (
            :game_id, :game_date, :season, :home_team_id, :away_team_id,
            :home_score, :away_score, :winner_team_id, :is_completed
        )
        ON CONFLICT (game_id) DO UPDATE SET
            game_date      = EXCLUDED.game_date,
            season         = EXCLUDED.season,
            home_team_id   = EXCLUDED.home_team_id,
            away_team_id   = EXCLUDED.away_team_id,
            home_score     = EXCLUDED.home_score,
            away_score     = EXCLUDED.away_score,
            winner_team_id = EXCLUDED.winner_team_id,
            is_completed   = EXCLUDED.is_completed
        """
    )

    team_game_upsert = text(
        """
        INSERT INTO team_game_stats (
            game_id, team_id,
            points, rebounds, assists, steals, blocks, turnovers,
            field_goal_pct, three_point_pct, free_throw_pct,
            offensive_rating, defensive_rating, pace,
            effective_fg_pct, true_shooting_pct
        )
        VALUES (
            :game_id, :team_id,
            :points, :rebounds, :assists, :steals, :blocks, :turnovers,
            :field_goal_pct, :three_point_pct, :free_throw_pct,
            :offensive_rating, :defensive_rating, :pace,
            :effective_fg_pct, :true_shooting_pct
        )
        ON CONFLICT (game_id, team_id) DO UPDATE SET
            points           = EXCLUDED.points,
            rebounds         = EXCLUDED.rebounds,
            assists          = EXCLUDED.assists,
            steals           = EXCLUDED.steals,
            blocks           = EXCLUDED.blocks,
            turnovers        = EXCLUDED.turnovers,
            field_goal_pct   = EXCLUDED.field_goal_pct,
            three_point_pct  = EXCLUDED.three_point_pct,
            free_throw_pct   = EXCLUDED.free_throw_pct,
            offensive_rating = EXCLUDED.offensive_rating,
            defensive_rating = EXCLUDED.defensive_rating,
            pace             = EXCLUDED.pace,
            effective_fg_pct = EXCLUDED.effective_fg_pct,
            true_shooting_pct = EXCLUDED.true_shooting_pct
        """
    )

    player_game_upsert = text(
        """
        INSERT INTO player_game_stats (
            game_id, player_id, team_id,
            minutes, points, rebounds, assists, steals, blocks, turnovers,
            personal_fouls, field_goals_made, field_goals_attempted, field_goal_pct,
            three_points_made, three_points_attempted, three_point_pct,
            free_throws_made, free_throws_attempted, free_throw_pct,
            plus_minus, fantasy_points
        )
        VALUES (
            :game_id, :player_id, :team_id,
            :minutes, :points, :rebounds, :assists, :steals, :blocks, :turnovers,
            :personal_fouls, :field_goals_made, :field_goals_attempted, :field_goal_pct,
            :three_points_made, :three_points_attempted, :three_point_pct,
            :free_throws_made, :free_throws_attempted, :free_throw_pct,
            :plus_minus, :fantasy_points
        )
        ON CONFLICT (game_id, player_id) DO UPDATE SET
            team_id                  = EXCLUDED.team_id,
            minutes                  = EXCLUDED.minutes,
            points                   = EXCLUDED.points,
            rebounds                 = EXCLUDED.rebounds,
            assists                  = EXCLUDED.assists,
            steals                   = EXCLUDED.steals,
            blocks                   = EXCLUDED.blocks,
            turnovers                = EXCLUDED.turnovers,
            personal_fouls           = EXCLUDED.personal_fouls,
            field_goals_made         = EXCLUDED.field_goals_made,
            field_goals_attempted    = EXCLUDED.field_goals_attempted,
            field_goal_pct           = EXCLUDED.field_goal_pct,
            three_points_made        = EXCLUDED.three_points_made,
            three_points_attempted   = EXCLUDED.three_points_attempted,
            three_point_pct          = EXCLUDED.three_point_pct,
            free_throws_made         = EXCLUDED.free_throws_made,
            free_throws_attempted    = EXCLUDED.free_throws_attempted,
            free_throw_pct           = EXCLUDED.free_throw_pct,
            plus_minus               = EXCLUDED.plus_minus,
            fantasy_points           = EXCLUDED.fantasy_points
        """
    )

    has_team_game_stats = _table_exists(engine, "team_game_stats")
    games_ingested = 0
    player_rows_ingested = 0
    total = len(events)

    for idx, event in enumerate(events, start=1):
        game_id = str(event.get("id", "")).strip()
        if not game_id:
            continue

        log_event(
            "game_ingest_start",
            context=context,
            progress=f"{idx}/{total}",
            game_id=game_id,
        )
        try:
            # transform_game expects a raw schedule/scoreboard event dict
            game_row = transform_game(event)
            if game_row is None:
                log_event("game_skip_not_final", game_id=game_id, context=context)
                continue

            # Fetch full boxscore for team + player stats
            raw_summary = fetcher.fetch_game_summary(game_id)

            with engine.begin() as conn:
                conn.execute(match_upsert, game_row)

                if has_team_game_stats:
                    team_rows = transform_team_game_stats(raw_summary, game_id)
                    if team_rows:
                        conn.execute(team_game_upsert, team_rows)

                player_rows = transform_player_game_stats(raw_summary, game_id)
                if player_rows:
                    conn.execute(player_game_upsert, player_rows)
                    player_rows_ingested += len(player_rows)

            games_ingested += 1

        except Exception as exc:
            log_event(
                "game_ingest_failed",
                level="WARNING",
                context=context,
                game_id=game_id,
                progress=f"{idx}/{total}",
                error=str(exc),
            )

        time.sleep(0.5)

    return {"games": games_ingested, "player_rows": player_rows_ingested}


# ── Player season stats rollup ────────────────────────────────────────────────

def _upsert_player_season_stats(engine: Engine, season_rows: list[dict]) -> int:
    """Upsert aggregated per-player-per-season stats into player_season_stats.

    Called after flush/backfill completes to materialise the season averages
    that the API's /players endpoint and ML feature store read from.

    ON CONFLICT key: (player_id, season)
    """
    if not season_rows:
        return 0

    if not _table_exists(engine, "player_season_stats"):
        log_event(
            "player_season_stats_table_missing",
            level="WARNING",
            note="Skipping rollup — run migrations first.",
        )
        return 0

    upsert_sql = text(
        """
        INSERT INTO player_season_stats (
            player_id, season, team_id,
            games_played, wins, losses, win_pct,
            minutes, points, rebounds, assists,
            steals, blocks, turnovers,
            field_goal_pct, three_point_pct, free_throw_pct,
            plus_minus, fantasy_points
        )
        VALUES (
            :player_id, :season, :team_id,
            :games_played, :wins, :losses, :win_pct,
            :minutes, :points, :rebounds, :assists,
            :steals, :blocks, :turnovers,
            :field_goal_pct, :three_point_pct, :free_throw_pct,
            :plus_minus, :fantasy_points
        )
        ON CONFLICT (player_id, season) DO UPDATE SET
            team_id         = EXCLUDED.team_id,
            games_played    = EXCLUDED.games_played,
            wins            = EXCLUDED.wins,
            losses          = EXCLUDED.losses,
            win_pct         = EXCLUDED.win_pct,
            minutes         = EXCLUDED.minutes,
            points          = EXCLUDED.points,
            rebounds        = EXCLUDED.rebounds,
            assists         = EXCLUDED.assists,
            steals          = EXCLUDED.steals,
            blocks          = EXCLUDED.blocks,
            turnovers       = EXCLUDED.turnovers,
            field_goal_pct  = EXCLUDED.field_goal_pct,
            three_point_pct = EXCLUDED.three_point_pct,
            free_throw_pct  = EXCLUDED.free_throw_pct,
            plus_minus      = EXCLUDED.plus_minus,
            fantasy_points  = EXCLUDED.fantasy_points
        """
    )

    with engine.begin() as conn:
        conn.execute(upsert_sql, season_rows)

    return len(season_rows)


# ── Main entry point ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ESPN-based NBA ingestion pipeline (SCR-332)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["flush", "backfill", "incremental"],
        default="incremental",
        help=(
            "flush: truncate all tables then full reload; "
            "backfill: full reload without truncating; "
            "incremental: yesterday→tomorrow window only (default)"
        ),
    )
    args = parser.parse_args()

    started_at = datetime.now(timezone.utc)
    run_id = started_at.strftime("%Y%m%d_%H%M%S")

    log_event(
        "espn_pipeline_start",
        run_id=run_id,
        mode=args.mode,
        seasons=[s["label"] for s in SEASONS],
    )

    database_url = _resolve_database_url()
    engine = _build_engine(database_url)

    exit_code = 0

    try:
        from src.data.espn_fetcher import EspnFetcher

        fetcher = EspnFetcher()

        if args.mode == "flush":
            flush_tables(engine)
            # Fall through to backfill logic
            _run_full_load(fetcher, engine, run_id)

        elif args.mode == "backfill":
            _run_full_load(fetcher, engine, run_id)

        elif args.mode == "incremental":
            _run_incremental(fetcher, engine, run_id)

        log_event(
            "espn_pipeline_success",
            run_id=run_id,
            mode=args.mode,
            duration_seconds=(datetime.now(timezone.utc) - started_at).total_seconds(),
        )

    except Exception as exc:
        log_event(
            "espn_pipeline_failed",
            level="ERROR",
            run_id=run_id,
            mode=args.mode,
            error=str(exc),
            traceback=traceback.format_exc(),
        )
        exit_code = 1

    finally:
        engine.dispose()

    raise SystemExit(exit_code)


def _run_full_load(fetcher: Any, engine: Engine, run_id: str) -> None:
    """Shared full-load logic used by both flush and backfill modes.

    Sequence:
        1. Ingest all 30 teams (dimension table — no season loop needed).
        2. Ingest rosters for all teams (players with positions).
        3. For each season: ingest all completed game boxscores.
        4. Roll up player_game_stats → player_season_stats averages.
        5. Optionally trigger upcoming-game pre-game predictions.
    """
    team_count = ingest_teams(fetcher, engine)
    player_count = ingest_rosters(fetcher, engine)

    log_event(
        "dimension_load_complete",
        run_id=run_id,
        teams=team_count,
        players=player_count,
    )

    total_games = 0
    total_player_rows = 0

    for season in SEASONS:
        result = ingest_season(fetcher, engine, season["label"], season["year"])
        total_games += result["games"]
        total_player_rows += result["player_rows"]

    log_event(
        "full_load_games_complete",
        run_id=run_id,
        total_games=total_games,
        total_player_rows=total_player_rows,
    )

    # Materialise season averages from raw game stats (one pass per season)
    try:
        from src.data.espn_transformer import compute_player_season_stats

        all_season_rows: list[dict] = []
        with engine.connect() as conn:
            for season in SEASONS:
                rows = compute_player_season_stats(season["label"], conn)
                all_season_rows.extend(rows)
        upserted = _upsert_player_season_stats(engine, all_season_rows)
        log_event("player_season_stats_upserted", run_id=run_id, rows=upserted)
    except Exception as exc:
        log_event(
            "player_season_stats_failed",
            level="WARNING",
            run_id=run_id,
            error=str(exc),
        )

    # Run upcoming-game pre-game predictions (best-effort — non-fatal)
    try:
        from src.data.schedule_fetcher import fetch_and_predict_upcoming
        from src import config as app_config

        upcoming_summary = fetch_and_predict_upcoming(
            engine,
            season=app_config.CURRENT_SEASON,
            days_ahead=1,
        )
        log_event("upcoming_schedule_fetched", run_id=run_id, **upcoming_summary)
    except Exception as sched_exc:
        log_event(
            "upcoming_schedule_fetch_failed",
            level="WARNING",
            run_id=run_id,
            error=str(sched_exc),
        )


def _run_incremental(fetcher: Any, engine: Engine, run_id: str) -> None:
    """Execute the daily incremental window (yesterday → tomorrow).

    Also refreshes rosters so mid-season position changes, trades, and
    waiver pickups are reflected in the players table without a full
    backfill.
    """
    # Refresh rosters to capture any trades / waiver moves since last run
    ingest_rosters(fetcher, engine)

    result = ingest_incremental(fetcher, engine)
    log_event("incremental_done", run_id=run_id, **result)

    # Re-roll season stats for the current season only if new games landed
    if result["games"] > 0:
        try:
            from src.data.espn_transformer import compute_player_season_stats

            current_season = SEASONS[-1]["label"]
            season_rows = compute_player_season_stats(engine, season=current_season)
            upserted = _upsert_player_season_stats(engine, season_rows)
            log_event(
                "player_season_stats_incremental_upserted",
                run_id=run_id,
                season=current_season,
                rows=upserted,
            )
        except Exception as exc:
            log_event(
                "player_season_stats_incremental_failed",
                level="WARNING",
                run_id=run_id,
                error=str(exc),
            )

    # Upcoming game predictions (best-effort)
    try:
        from src.data.schedule_fetcher import fetch_and_predict_upcoming
        from src import config as app_config

        upcoming_summary = fetch_and_predict_upcoming(
            engine,
            season=app_config.CURRENT_SEASON,
            days_ahead=1,
        )
        log_event("upcoming_schedule_fetched", run_id=run_id, **upcoming_summary)
    except Exception as sched_exc:
        log_event(
            "upcoming_schedule_fetch_failed",
            level="WARNING",
            run_id=run_id,
            error=str(sched_exc),
        )


if __name__ == "__main__":
    main()
