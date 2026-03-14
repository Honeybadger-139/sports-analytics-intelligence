"""
FastAPI Routes for Sports Analytics Intelligence Platform
=========================================================

All API endpoints for predictions, explanations, bet sizing,
and historical data access.
"""

import logging
import json
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text
import pandas as pd

from src.data.db import get_db
from src.data.audit_store import is_missing_pipeline_audit_error
from src.data.bet_store import create_bet, get_bets_summary, list_bets, settle_bet
from src.data.prediction_store import (
    persist_game_predictions,
    sync_prediction_outcomes,
)
from src import config
from src.intelligence.vector_store import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["predictions"])


# Lazy-load predictor (loaded once at first request)
_predictor = None


RAW_TABLES: Dict[str, Dict[str, str]] = {
    "matches": {
        "label": "Matches",
        "description": "Raw schedule and game result rows.",
    },
    "teams": {
        "label": "Teams",
        "description": "NBA team dimension rows.",
    },
    "players": {
        "label": "Players",
        "description": "Player master rows and roster mapping.",
    },
    "team_game_stats": {
        "label": "Team Game Stats",
        "description": "Raw per-game team stat rows.",
    },
    "player_game_stats": {
        "label": "Player Game Stats",
        "description": "Raw per-game player stat rows.",
    },
    "player_season_stats": {
        "label": "Player Season Stats",
        "description": "Raw player season aggregate rows.",
    },
}

SEASON_FILTER_TABLES = {"matches", "team_game_stats", "player_game_stats", "player_season_stats"}

def get_predictor():
    global _predictor
    if _predictor is None:
        from src.models.predictor import Predictor
        _predictor = Predictor()
    return _predictor


def _persist_predictions_for_games(db: Session, games: list) -> int:
    """
    Persist predictions for a list of game payloads and return rows written.
    """
    persisted = 0
    for game in games:
        persisted += persist_game_predictions(
            db,
            game_id=str(game["game_id"]),
            predictions=game.get("predictions", {}),
            shap_factors_by_model=game.get("shap_factors"),
        )
    return persisted


def _bootstrap_predictions_from_completed_games(
    db: Session,
    season: str,
    max_games: int = 1500,
) -> Dict[str, int]:
    """
    Backfill prediction rows for completed games when performance history is empty.
    """
    predictor = get_predictor()
    feature_cols = predictor.feature_columns or []
    if not feature_cols:
        return {
            "scanned_games": 0,
            "games_bootstrapped": 0,
            "persisted_rows": 0,
            "errors": 0,
        }

    query = text(
        """
        SELECT
            m.game_id,
            m.game_date,
            ht.abbreviation as home_team,
            ht.full_name as home_team_name,
            at.abbreviation as away_team,
            at.full_name as away_team_name,
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
        WHERE m.season = :season
          AND m.is_completed = TRUE
          AND NOT EXISTS (
              SELECT 1
              FROM predictions p
              WHERE p.game_id = m.game_id
          )
        ORDER BY m.game_date DESC, m.game_id DESC
        LIMIT :max_games
        """
    )

    with db.get_bind().connect() as conn:
        df = pd.read_sql(query, conn, params={"season": season, "max_games": max_games})

    if df.empty:
        return {
            "scanned_games": 0,
            "games_bootstrapped": 0,
            "persisted_rows": 0,
            "errors": 0,
        }

    persisted_rows = 0
    games_bootstrapped = 0
    errors = 0

    for _, row in df.iterrows():
        game_id = str(row.get("game_id"))
        try:
            # Build one-row numeric feature frame deterministically to avoid noisy
            # dtype downcasting warnings during large bootstrap loops.
            feature_payload = {
                col: float(row.get(col, 0) or 0)
                for col in feature_cols
            }
            features = pd.DataFrame([feature_payload], columns=feature_cols)
            predictions = predictor.predict_game(features)
            shap_factors = predictor.explain_game(features, top_n=5)

            predicted_at = None
            game_date = row.get("game_date")
            if game_date is not None and pd.notna(game_date):
                if isinstance(game_date, datetime):
                    predicted_at = game_date
                else:
                    parsed = pd.to_datetime(game_date)
                    predicted_at = datetime.combine(parsed.date(), datetime.min.time())

            persisted_rows += persist_game_predictions(
                db,
                game_id=game_id,
                predictions=predictions,
                shap_factors_by_model=shap_factors,
                predicted_at=predicted_at,
            )
            games_bootstrapped += 1
        except Exception as exc:
            errors += 1
            logger.warning(
                "Skipped prediction bootstrap for game_id=%s season=%s: %s",
                game_id,
                season,
                exc,
            )

    if persisted_rows > 0:
        sync_prediction_outcomes(db, season=season)

    return {
        "scanned_games": int(len(df)),
        "games_bootstrapped": int(games_bootstrapped),
        "persisted_rows": int(persisted_rows),
        "errors": int(errors),
    }


class BetCreateRequest(BaseModel):
    game_id: str = Field(min_length=1, max_length=20)
    bet_type: str = Field(default="match_winner", min_length=1, max_length=50)
    selection: str = Field(min_length=1, max_length=100)
    odds: float = Field(gt=1.0, description="Decimal odds (e.g., 1.91, 2.25)")
    stake: float = Field(gt=0)
    kelly_fraction: Optional[float] = Field(default=None, ge=0, le=1)
    model_probability: Optional[float] = Field(default=None, ge=0, le=1)
    placed_at: Optional[datetime] = None


class BetSettleRequest(BaseModel):
    result: Literal["win", "loss", "push"]
    settled_at: Optional[datetime] = None


def _normalize_json_field(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def _as_dict_rows(rows):
    return [dict(row._mapping) for row in rows]


def _model_artifact_snapshot() -> Dict:
    model_dir = Path(config.MODEL_DIR)
    if not model_dir.exists():
        return {"active_artifact": None, "artifacts": []}

    artifacts = []
    for file_path in sorted(model_dir.glob("*.pkl")):
        try:
            stat = file_path.stat()
            artifacts.append(
                {
                    "name": file_path.name,
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )
        except Exception:
            continue

    active = artifacts[-1]["name"] if artifacts else None
    return {"active_artifact": active, "artifacts": artifacts}


def _load_persisted_shap_factors(db: Session, game_id: str) -> Dict[str, list]:
    try:
        rows = db.execute(
            text(
                """
                SELECT model_name, shap_factors
                FROM predictions
                WHERE game_id = :game_id
                """
            ),
            {"game_id": game_id},
        ).fetchall()
    except Exception:
        return {}

    payload: Dict[str, list] = {}
    for row in rows:
        factors = _normalize_json_field(row.shap_factors)
        payload[row.model_name] = factors if isinstance(factors, list) else []
    return payload


def _db_health_payload(db: Session) -> Dict:
    db.execute(text("SELECT 1"))
    match_count = int(db.execute(text("SELECT COUNT(*) FROM matches")).scalar() or 0)
    return {
        "status": "ok",
        "match_count": match_count,
    }


def _ml_health_payload() -> Dict:
    snapshot = _model_artifact_snapshot()
    active_name = snapshot.get("active_artifact")
    last_trained_at = None
    if active_name:
        active = next((item for item in snapshot["artifacts"] if item["name"] == active_name), None)
        if active:
            last_trained_at = active.get("modified_at")
    status = "ok" if active_name else "missing"
    return {
        "status": status,
        "active_artifact": active_name,
        "last_trained_at": last_trained_at,
        "artifact_count": len(snapshot.get("artifacts", [])),
    }


def _rag_health_payload() -> Dict:
    store = VectorStore()
    count = store.count()
    status = "ok" if count > 0 else "empty"
    return {
        "status": status,
        "collection": config.RAG_COLLECTION,
        "document_count": count,
    }


@router.get("/raw/tables")
async def get_raw_tables(
    season: str = Query(default=config.CURRENT_SEASON),
    db: Session = Depends(get_db),
):
    """
    List raw Postgres tables available for exploration (excludes feature tables).
    """
    items = []
    for table_name, meta in RAW_TABLES.items():
        if table_name == "matches":
            count = db.execute(
                text("SELECT COUNT(*) FROM matches WHERE season = :season"),
                {"season": season},
            ).scalar()
        elif table_name in {"team_game_stats", "player_game_stats"}:
            count = db.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM {table_name} t
                    JOIN matches m ON t.game_id = m.game_id
                    WHERE m.season = :season
                    """
                ),
                {"season": season},
            ).scalar()
        elif table_name == "player_season_stats":
            count = db.execute(
                text("SELECT COUNT(*) FROM player_season_stats WHERE season = :season"),
                {"season": season},
            ).scalar()
        else:
            count = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()

        items.append(
            {
                "table": table_name,
                "label": meta["label"],
                "description": meta["description"],
                "season_filter_supported": table_name in SEASON_FILTER_TABLES,
                "row_count": int(count or 0),
            }
        )

    return {"season": season, "tables": items}


@router.get("/raw/{table_name}")
async def get_raw_table_rows(
    table_name: str,
    season: Optional[str] = Query(default=config.CURRENT_SEASON),
    search: Optional[str] = Query(default=None, description="Global text filter (applied before pagination)"),
    limit: int = Query(default=50, ge=1, le=300),
    offset: int = Query(default=0, ge=0, le=50000),
    db: Session = Depends(get_db),
):
    """
    Fetch paginated rows from whitelisted raw tables (feature table intentionally excluded).
    """
    if table_name not in RAW_TABLES:
        raise HTTPException(status_code=404, detail=f"Unsupported raw table: {table_name}")
    normalized_search = search.strip() if search else None
    search_param = f"%{normalized_search}%" if normalized_search else None

    if table_name == "matches":
        params = {"season": season, "search": search_param, "limit": limit, "offset": offset}
        rows = db.execute(
            text(
                """
                WITH base AS (
                    SELECT
                        m.*,
                        ht.abbreviation AS home_team,
                        at.abbreviation AS away_team
                    FROM matches m
                    JOIN teams ht ON m.home_team_id = ht.team_id
                    JOIN teams at ON m.away_team_id = at.team_id
                    WHERE (:season IS NULL OR m.season = :season)
                )
                SELECT *
                FROM base
                WHERE (:search IS NULL OR home_team ILIKE :search OR away_team ILIKE :search OR CAST(game_id AS TEXT) ILIKE :search)
                ORDER BY game_date DESC, game_id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).fetchall()
        total = db.execute(
            text(
                """
                WITH base AS (
                    SELECT
                        m.*,
                        ht.abbreviation AS home_team,
                        at.abbreviation AS away_team
                    FROM matches m
                    JOIN teams ht ON m.home_team_id = ht.team_id
                    JOIN teams at ON m.away_team_id = at.team_id
                    WHERE (:season IS NULL OR m.season = :season)
                )
                SELECT COUNT(*)
                FROM base
                WHERE (:search IS NULL OR home_team ILIKE :search OR away_team ILIKE :search OR CAST(game_id AS TEXT) ILIKE :search)
                """
            ),
            {"season": season, "search": search_param},
        ).scalar()
    elif table_name == "teams":
        params = {"search": search_param, "limit": limit, "offset": offset}
        rows = db.execute(
            text(
                """
                WITH base AS (
                    SELECT *
                    FROM teams
                )
                SELECT *
                FROM base
                WHERE (:search IS NULL OR abbreviation ILIKE :search OR full_name ILIKE :search OR city ILIKE :search)
                ORDER BY abbreviation
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).fetchall()
        total = db.execute(
            text(
                """
                WITH base AS (
                    SELECT *
                    FROM teams
                )
                SELECT COUNT(*)
                FROM base
                WHERE (:search IS NULL OR abbreviation ILIKE :search OR full_name ILIKE :search OR city ILIKE :search)
                """
            ),
            {"search": search_param},
        ).scalar()
    elif table_name == "players":
        params = {"search": search_param, "limit": limit, "offset": offset}
        rows = db.execute(
            text(
                """
                WITH base AS (
                    SELECT p.*, t.abbreviation AS team_abbreviation
                    FROM players p
                    LEFT JOIN teams t ON p.team_id = t.team_id
                )
                SELECT *
                FROM base
                WHERE (:search IS NULL OR full_name ILIKE :search OR team_abbreviation ILIKE :search)
                ORDER BY player_id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).fetchall()
        total = db.execute(
            text(
                """
                WITH base AS (
                    SELECT p.*, t.abbreviation AS team_abbreviation
                    FROM players p
                    LEFT JOIN teams t ON p.team_id = t.team_id
                )
                SELECT COUNT(*)
                FROM base
                WHERE (:search IS NULL OR full_name ILIKE :search OR team_abbreviation ILIKE :search)
                """
            ),
            {"search": search_param},
        ).scalar()
    elif table_name == "team_game_stats":
        params = {"season": season, "search": search_param, "limit": limit, "offset": offset}
        rows = db.execute(
            text(
                """
                WITH base AS (
                    SELECT
                        tgs.*,
                        m.game_date,
                        m.season,
                        tm.abbreviation AS team_abbreviation
                    FROM team_game_stats tgs
                    JOIN matches m ON tgs.game_id = m.game_id
                    JOIN teams tm ON tgs.team_id = tm.team_id
                    WHERE (:season IS NULL OR m.season = :season)
                )
                SELECT *
                FROM base
                WHERE (:search IS NULL OR team_abbreviation ILIKE :search)
                ORDER BY game_date DESC, game_id DESC, team_id
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).fetchall()
        total = db.execute(
            text(
                """
                WITH base AS (
                    SELECT
                        tgs.*,
                        m.game_date,
                        m.season,
                        tm.abbreviation AS team_abbreviation
                    FROM team_game_stats tgs
                    JOIN matches m ON tgs.game_id = m.game_id
                    JOIN teams tm ON tgs.team_id = tm.team_id
                    WHERE (:season IS NULL OR m.season = :season)
                )
                SELECT COUNT(*)
                FROM base
                WHERE (:search IS NULL OR team_abbreviation ILIKE :search)
                """
            ),
            {"season": season, "search": search_param},
        ).scalar()
    elif table_name == "player_game_stats":
        params = {"season": season, "search": search_param, "limit": limit, "offset": offset}
        rows = db.execute(
            text(
                """
                WITH base AS (
                    SELECT
                        pgs.*,
                        m.game_date,
                        m.season,
                        pl.full_name AS player_name,
                        tm.abbreviation AS team_abbreviation
                    FROM player_game_stats pgs
                    JOIN matches m ON pgs.game_id = m.game_id
                    LEFT JOIN players pl ON pgs.player_id = pl.player_id
                    LEFT JOIN teams tm ON pgs.team_id = tm.team_id
                    WHERE (:season IS NULL OR m.season = :season)
                )
                SELECT *
                FROM base
                WHERE (:search IS NULL OR player_name ILIKE :search OR team_abbreviation ILIKE :search)
                ORDER BY game_date DESC, game_id DESC, player_id
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).fetchall()
        total = db.execute(
            text(
                """
                WITH base AS (
                    SELECT
                        pgs.*,
                        m.game_date,
                        m.season,
                        pl.full_name AS player_name,
                        tm.abbreviation AS team_abbreviation
                    FROM player_game_stats pgs
                    JOIN matches m ON pgs.game_id = m.game_id
                    LEFT JOIN players pl ON pgs.player_id = pl.player_id
                    LEFT JOIN teams tm ON pgs.team_id = tm.team_id
                    WHERE (:season IS NULL OR m.season = :season)
                )
                SELECT COUNT(*)
                FROM base
                WHERE (:search IS NULL OR player_name ILIKE :search OR team_abbreviation ILIKE :search)
                """
            ),
            {"season": season, "search": search_param},
        ).scalar()
    else:  # player_season_stats
        params = {"season": season, "search": search_param, "limit": limit, "offset": offset}
        rows = db.execute(
            text(
                """
                WITH base AS (
                    SELECT
                        pss.*,
                        pl.full_name AS player_name,
                        tm.abbreviation AS team_abbreviation
                    FROM player_season_stats pss
                    LEFT JOIN players pl ON pss.player_id = pl.player_id
                    LEFT JOIN teams tm ON pss.team_id = tm.team_id
                    WHERE (:season IS NULL OR pss.season = :season)
                )
                SELECT *
                FROM base
                WHERE (:search IS NULL OR player_name ILIKE :search OR team_abbreviation ILIKE :search)
                ORDER BY season DESC, player_id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).fetchall()
        total = db.execute(
            text(
                """
                WITH base AS (
                    SELECT
                        pss.*,
                        pl.full_name AS player_name,
                        tm.abbreviation AS team_abbreviation
                    FROM player_season_stats pss
                    LEFT JOIN players pl ON pss.player_id = pl.player_id
                    LEFT JOIN teams tm ON pss.team_id = tm.team_id
                    WHERE (:season IS NULL OR pss.season = :season)
                )
                SELECT COUNT(*)
                FROM base
                WHERE (:search IS NULL OR player_name ILIKE :search OR team_abbreviation ILIKE :search)
                """
            ),
            {"season": season, "search": search_param},
        ).scalar()

    return {
        "table": table_name,
        "season": season,
        "search": normalized_search,
        "limit": limit,
        "offset": offset,
        "total": int(total or 0),
        "rows": _as_dict_rows(rows),
    }


@router.get("/quality/overview")
async def get_quality_overview(
    season: str = Query(default=config.CURRENT_SEASON),
    recent_limit: int = Query(default=20, ge=5, le=100),
    db: Session = Depends(get_db),
):
    """
    Return operational quality and pipeline metrics for monitoring tab.
    """
    row_counts = {
        "matches": int(
            db.execute(text("SELECT COUNT(*) FROM matches WHERE season = :season"), {"season": season}).scalar() or 0
        ),
        "teams": int(db.execute(text("SELECT COUNT(*) FROM teams")).scalar() or 0),
        "players": int(db.execute(text("SELECT COUNT(*) FROM players WHERE is_active = TRUE")).scalar() or 0),
        "team_game_stats": int(
            db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM team_game_stats tgs
                    JOIN matches m ON tgs.game_id = m.game_id
                    WHERE m.season = :season
                    """
                ),
                {"season": season},
            ).scalar()
            or 0
        ),
        "player_game_stats": int(
            db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM player_game_stats pgs
                    JOIN matches m ON pgs.game_id = m.game_id
                    WHERE m.season = :season
                    """
                ),
                {"season": season},
            ).scalar()
            or 0
        ),
    }

    quality_row = db.execute(
        text(
            """
            SELECT details, sync_time
            FROM pipeline_audit
            WHERE module = 'ingestion'
            ORDER BY sync_time DESC
            LIMIT 1
            """
        )
    ).fetchone()

    quality_checks = {}
    if quality_row:
        details = _normalize_json_field(quality_row.details)
        if isinstance(details, dict):
            quality_checks = details.get("audit_violations") or {}

    timing_row = db.execute(
        text(
            """
            SELECT
                ROUND(AVG((details->>'elapsed_seconds')::numeric) FILTER (
                    WHERE module = 'ingestion' AND status = 'success' AND details ? 'elapsed_seconds'
                ), 2) AS avg_ingestion_seconds,
                ROUND(AVG((details->>'elapsed_seconds')::numeric) FILTER (
                    WHERE module = 'feature_store' AND status = 'success' AND details ? 'elapsed_seconds'
                ), 2) AS avg_feature_seconds
            FROM pipeline_audit
            """
        )
    ).fetchone()

    latest_ingestion_elapsed = db.execute(
        text(
            """
            SELECT (details->>'elapsed_seconds')::numeric
            FROM pipeline_audit
            WHERE module = 'ingestion' AND details ? 'elapsed_seconds'
            ORDER BY sync_time DESC
            LIMIT 1
            """
        )
    ).scalar()
    latest_feature_elapsed = db.execute(
        text(
            """
            SELECT (details->>'elapsed_seconds')::numeric
            FROM pipeline_audit
            WHERE module = 'feature_store' AND details ? 'elapsed_seconds'
            ORDER BY sync_time DESC
            LIMIT 1
            """
        )
    ).scalar()

    top_teams = _as_dict_rows(
        db.execute(
            text(
                """
                WITH team_records AS (
                    SELECT
                        t.team_id,
                        t.abbreviation,
                        COUNT(*) AS games_played,
                        SUM(CASE WHEN m.winner_team_id = t.team_id THEN 1 ELSE 0 END) AS wins,
                        SUM(CASE WHEN m.winner_team_id != t.team_id THEN 1 ELSE 0 END) AS losses
                    FROM teams t
                    JOIN (
                        SELECT home_team_id AS team_id, winner_team_id, season FROM matches
                        UNION ALL
                        SELECT away_team_id AS team_id, winner_team_id, season FROM matches
                    ) m ON m.team_id = t.team_id
                    WHERE m.season = :season
                    GROUP BY t.team_id, t.abbreviation
                )
                SELECT
                    abbreviation,
                    games_played,
                    wins,
                    losses,
                    ROUND(wins::numeric / NULLIF(games_played, 0), 3) AS win_pct
                FROM team_records
                ORDER BY win_pct DESC, wins DESC
                LIMIT 10
                """
            ),
            {"season": season},
        ).fetchall()
    )

    recent_rows = db.execute(
        text(
            """
            SELECT sync_time, module, status, records_processed, records_inserted, errors, details
            FROM pipeline_audit
            ORDER BY sync_time DESC
            LIMIT :recent_limit
            """
        ),
        {"recent_limit": recent_limit},
    ).fetchall()

    recent_runs = []
    for row in recent_rows:
        details = _normalize_json_field(row.details)
        recent_runs.append(
            {
                "sync_time": row.sync_time.isoformat(),
                "module": row.module,
                "status": row.status,
                "records_processed": row.records_processed,
                "records_inserted": row.records_inserted,
                "errors": row.errors,
                "elapsed_seconds": details.get("elapsed_seconds") if isinstance(details, dict) else None,
            }
        )

    return {
        "season": season,
        "row_counts": row_counts,
        "quality_checks": quality_checks,
        "pipeline_timing": {
            "avg_ingestion_seconds": float(timing_row.avg_ingestion_seconds) if timing_row and timing_row.avg_ingestion_seconds is not None else None,
            "avg_feature_seconds": float(timing_row.avg_feature_seconds) if timing_row and timing_row.avg_feature_seconds is not None else None,
            "latest_ingestion_seconds": float(latest_ingestion_elapsed) if latest_ingestion_elapsed is not None else None,
            "latest_feature_seconds": float(latest_feature_elapsed) if latest_feature_elapsed is not None else None,
        },
        "top_teams": top_teams,
        "recent_runs": recent_runs,
    }


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@router.get("/health/db")
async def db_health(db: Session = Depends(get_db)):
    try:
        return _db_health_payload(db)
    except Exception as exc:
        logger.error("DB health check failed: %s", exc)
        raise HTTPException(status_code=500, detail="DB health check failed") from exc


@router.get("/health/ml")
async def ml_health():
    return _ml_health_payload()


@router.get("/health/rag")
async def rag_health():
    try:
        return _rag_health_payload()
    except Exception as exc:
        logger.error("RAG health check failed: %s", exc)
        raise HTTPException(status_code=500, detail="RAG health check failed") from exc


@router.get("/health/all")
async def all_health(db: Session = Depends(get_db)):
    checks = {
        "db": _db_health_payload(db),
        "ml": _ml_health_payload(),
        "rag": _rag_health_payload(),
    }
    overall = "ok"
    if any(item["status"] == "missing" for item in checks.values()):
        overall = "degraded"
    if any(item["status"] == "empty" for item in checks.values()):
        overall = "degraded"
    return {"status": overall, "checks": checks, "timestamp": datetime.now().isoformat()}


@router.get("/teams")
async def get_teams(db: Session = Depends(get_db)):
    """Get all NBA teams."""
    result = db.execute(text("SELECT team_id, abbreviation, full_name, city FROM teams ORDER BY abbreviation"))
    teams = [dict(row._mapping) for row in result]
    return {"teams": teams, "count": len(teams)}


@router.get("/matches/{game_id}/stats")
async def get_game_stats(game_id: str, db: Session = Depends(get_db)):
    """
    Get full box score (team stats + player stats) for a specific game.
    Returns both team-level and individual player-level statistics.
    """
    # ── Match metadata ──────────────────────────────────────────────────────
    match_row = db.execute(
        text("""
            SELECT
                m.game_id, m.game_date, m.season,
                ht.team_id  AS home_team_id,  ht.abbreviation AS home_team,  ht.full_name AS home_team_name,
                at.team_id  AS away_team_id,  at.abbreviation AS away_team,  at.full_name AS away_team_name,
                m.winner_team_id,
                ht_stats.points  AS home_score, at_stats.points  AS away_score,
                ht_stats.rebounds AS home_reb,  at_stats.rebounds AS away_reb,
                ht_stats.assists  AS home_ast,  at_stats.assists  AS away_ast
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            LEFT JOIN team_game_stats ht_stats ON m.game_id = ht_stats.game_id AND m.home_team_id = ht_stats.team_id
            LEFT JOIN team_game_stats at_stats ON m.game_id = at_stats.game_id AND m.away_team_id = at_stats.team_id
            WHERE m.game_id = :game_id
        """),
        {"game_id": game_id},
    ).fetchone()

    if not match_row:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

    match_data = dict(match_row._mapping)

    # ── Team box scores ─────────────────────────────────────────────────────
    team_stats_rows = db.execute(
        text("""
            SELECT
                tgs.team_id, t.abbreviation AS team, t.full_name AS team_name,
                tgs.points, tgs.rebounds, tgs.assists, tgs.steals, tgs.blocks, tgs.turnovers,
                tgs.field_goal_pct, tgs.three_point_pct, tgs.free_throw_pct,
                tgs.offensive_rating, tgs.defensive_rating, tgs.pace,
                tgs.effective_fg_pct, tgs.true_shooting_pct
            FROM team_game_stats tgs
            JOIN teams t ON tgs.team_id = t.team_id
            WHERE tgs.game_id = :game_id
        """),
        {"game_id": game_id},
    ).fetchall()
    team_stats = [dict(r._mapping) for r in team_stats_rows]

    # ── Player box scores ───────────────────────────────────────────────────
    player_stats_rows = db.execute(
        text("""
            SELECT
                pgs.player_id, p.full_name AS player_name,
                t.abbreviation AS team, t.team_id,
                pgs.minutes, pgs.points, pgs.rebounds, pgs.assists,
                pgs.steals, pgs.blocks, pgs.turnovers, pgs.personal_fouls,
                pgs.field_goals_made, pgs.field_goals_attempted, pgs.field_goal_pct,
                pgs.three_points_made, pgs.three_points_attempted, pgs.three_point_pct,
                pgs.free_throws_made, pgs.free_throws_attempted, pgs.free_throw_pct,
                pgs.plus_minus, pgs.fantasy_points
            FROM player_game_stats pgs
            JOIN players p ON pgs.player_id = p.player_id
            JOIN teams t ON pgs.team_id = t.team_id
            WHERE pgs.game_id = :game_id
            ORDER BY pgs.points DESC, pgs.fantasy_points DESC
        """),
        {"game_id": game_id},
    ).fetchall()
    player_stats = [dict(r._mapping) for r in player_stats_rows]

    # Split players by home/away team
    home_players = [p for p in player_stats if p["team_id"] == match_data["home_team_id"]]
    away_players = [p for p in player_stats if p["team_id"] == match_data["away_team_id"]]

    # Get team stats split
    home_team_stats = next((t for t in team_stats if t["team_id"] == match_data["home_team_id"]), None)
    away_team_stats = next((t for t in team_stats if t["team_id"] == match_data["away_team_id"]), None)

    return {
        "game_id": game_id,
        "game_date": str(match_data["game_date"]),
        "season": match_data["season"],
        "home_team": match_data["home_team"],
        "home_team_name": match_data["home_team_name"],
        "away_team": match_data["away_team"],
        "away_team_name": match_data["away_team_name"],
        "home_score": match_data["home_score"],
        "away_score": match_data["away_score"],
        "winner_team_id": match_data["winner_team_id"],
        "team_stats": {
            "home": home_team_stats,
            "away": away_team_stats,
        },
        "player_stats": {
            "home": home_players,
            "away": away_players,
        },
    }


@router.get("/matches")
async def get_matches_by_date(
    season: str = Query(default="2025-26"),
    team: Optional[str] = Query(default=None, description="Exact team abbreviation"),
    team_search: Optional[str] = Query(default=None, description="Team name/city search"),
    limit: int = Query(default=20, le=100),
    date: Optional[str] = Query(default=None, description="Exact date YYYY-MM-DD"),
    date_from: Optional[str] = Query(default=None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(default=None, description="End date YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """Get recent matches with optional date range filter."""
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
    params: dict = {"season": season, "limit": limit}

    if team:
        query += " AND (ht.abbreviation = :team OR at.abbreviation = :team)"
        params["team"] = team.upper()
    if team_search:
        query += """ AND (
            ht.abbreviation ILIKE :ts OR ht.full_name ILIKE :ts OR ht.city ILIKE :ts OR
            at.abbreviation ILIKE :ts OR at.full_name ILIKE :ts OR at.city ILIKE :ts
        )"""
        params["ts"] = f"%{team_search}%"
    if date:
        query += " AND m.game_date = :date"
        params["date"] = date
    if date_from:
        query += " AND m.game_date >= :date_from"
        params["date_from"] = date_from
    if date_to:
        query += " AND m.game_date <= :date_to"
        params["date_to"] = date_to

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
    shap_factors_by_model = _load_persisted_shap_factors(db, game_id)
    if not shap_factors_by_model:
        shap_factors_by_model = predictor.explain_game(features, top_n=5)
        persist_game_predictions(
            db,
            game_id=game_id,
            predictions=predictions,
            shap_factors_by_model=shap_factors_by_model,
        )
        shap_factors_by_model = _load_persisted_shap_factors(db, game_id) or shap_factors_by_model

    return {
        "game_id": game_id,
        "home_team": row_dict["home_team"],
        "home_team_name": row_dict["home_team_name"],
        "away_team": row_dict["away_team"],
        "away_team_name": row_dict["away_team_name"],
        "predictions": predictions,
        "explanation": shap_factors_by_model,
    }


@router.get("/predictions/today")
async def predict_today(
    persist: bool = Query(default=True, description="Persist predictions to DB"),
    db: Session = Depends(get_db),
):
    """
    Get predictions for all games scheduled today.
    """
    predictor = get_predictor()
    engine = db.get_bind()
    games = predictor.predict_today(engine)

    persisted_rows = 0
    if persist and games:
        persisted_rows = _persist_predictions_for_games(db, games)

    return {
        "date": date.today().isoformat(),
        "count": len(games),
        "persisted_rows": persisted_rows,
        "games": games,
    }


@router.get("/predictions/performance")
async def get_prediction_performance(
    season: str = Query(default=config.CURRENT_SEASON),
    model_name: Optional[str] = Query(default=None, description="Specific model name"),
    min_games: int = Query(default=1, ge=1, le=5000),
    bootstrap_if_empty: bool = Query(
        default=True,
        description="Backfill historical predictions for completed games when summary is empty.",
    ),
    bootstrap_limit: int = Query(default=1500, ge=50, le=5000),
    db: Session = Depends(get_db),
):
    """
    Return historical prediction performance metrics from persisted predictions.
    """
    sync_prediction_outcomes(db, season=season)

    summary_query = text("""
        SELECT
            p.model_name,
            COUNT(*) AS evaluated_games,
            SUM(CASE WHEN p.was_correct THEN 1 ELSE 0 END) AS correct_games,
            ROUND(AVG(CASE WHEN p.was_correct THEN 1.0 ELSE 0.0 END)::numeric, 4) AS accuracy,
            ROUND(AVG(p.confidence)::numeric, 4) AS avg_confidence,
            ROUND(AVG(POWER(
                p.home_win_prob::numeric - (CASE WHEN m.winner_team_id = m.home_team_id THEN 1 ELSE 0 END), 2
            ))::numeric, 4) AS brier_score,
            MIN(p.predicted_at) AS first_prediction_at,
            MAX(p.predicted_at) AS last_prediction_at
        FROM predictions p
        JOIN matches m ON p.game_id = m.game_id
        WHERE m.season = :season
          AND m.is_completed = TRUE
          AND p.was_correct IS NOT NULL
          AND (:model_name IS NULL OR p.model_name = :model_name)
        GROUP BY p.model_name
        HAVING COUNT(*) >= :min_games
        ORDER BY accuracy DESC, evaluated_games DESC
    """)

    pending_query = text("""
        SELECT COUNT(*)
        FROM predictions p
        JOIN matches m ON p.game_id = m.game_id
        WHERE m.season = :season
          AND m.is_completed = FALSE
          AND (:model_name IS NULL OR p.model_name = :model_name)
    """)

    params = {"season": season, "model_name": model_name, "min_games": min_games}
    rows = db.execute(summary_query, params).fetchall()
    pending_count = db.execute(
        pending_query, {"season": season, "model_name": model_name}
    ).scalar()

    bootstrap = {
        "attempted": False,
        "scanned_games": 0,
        "games_bootstrapped": 0,
        "persisted_rows": 0,
        "errors": 0,
    }
    if bootstrap_if_empty and len(rows) == 0:
        bootstrap["attempted"] = True
        result = _bootstrap_predictions_from_completed_games(
            db,
            season=season,
            max_games=bootstrap_limit,
        )
        bootstrap.update(result)
        if bootstrap["persisted_rows"] > 0:
            rows = db.execute(summary_query, params).fetchall()
            pending_count = db.execute(
                pending_query, {"season": season, "model_name": model_name}
            ).scalar()

    performance = []
    for row in rows:
        item = dict(row._mapping)
        if item.get("first_prediction_at") is not None:
            item["first_prediction_at"] = item["first_prediction_at"].isoformat()
        if item.get("last_prediction_at") is not None:
            item["last_prediction_at"] = item["last_prediction_at"].isoformat()
        performance.append(item)

    return {
        "season": season,
        "model_filter": model_name,
        "pending_games": int(pending_count or 0),
        "evaluated_models": len(performance),
        "performance": performance,
        "bootstrap": bootstrap,
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


@router.post("/bets")
async def add_bet(payload: BetCreateRequest, db: Session = Depends(get_db)):
    """Create a new pending bet ledger entry."""
    try:
        created = create_bet(
            db,
            game_id=payload.game_id,
            bet_type=payload.bet_type,
            selection=payload.selection,
            odds=payload.odds,
            stake=payload.stake,
            kelly_fraction=payload.kelly_fraction,
            model_probability=payload.model_probability,
            placed_at=payload.placed_at,
        )
        return {"bet": created}
    except Exception as exc:
        logger.error("Failed to create bet: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create bet") from exc


@router.get("/bets")
async def get_bets(
    season: Optional[str] = Query(default=None),
    result: Optional[str] = Query(default=None, description="open|settled|pending|win|loss|push"),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Get bet ledger history with optional filters."""
    bets = list_bets(db, season=season, result=result, limit=limit)
    return {"count": len(bets), "bets": bets}


@router.post("/bets/{bet_id}/settle")
async def settle_bet_by_id(
    bet_id: int,
    payload: BetSettleRequest,
    db: Session = Depends(get_db),
):
    """Settle a pending bet and compute PnL."""
    try:
        updated = settle_bet(
            db, bet_id=bet_id, result=payload.result, settled_at=payload.settled_at
        )
        return {"bet": updated}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Failed to settle bet %s: %s", bet_id, exc)
        raise HTTPException(status_code=500, detail="Failed to settle bet") from exc


@router.get("/bets/summary")
async def get_bankroll_summary(
    season: Optional[str] = Query(default=None),
    initial_bankroll: float = Query(default=1000.0, gt=0),
    db: Session = Depends(get_db),
):
    """Get aggregate bankroll KPIs from bet ledger."""
    summary = get_bets_summary(db, season=season, initial_bankroll=initial_bankroll)
    return {"summary": summary}


@router.get("/standings")
async def get_standings(
    season: str = Query(default="2025-26"),
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
# DEEP DIVE — PLAYER & TEAM STATS ROUTES
# ==========================================

@router.get("/players")
async def list_players(
    search: Optional[str] = Query(default=None, description="Search by player name (substring match)"),
    team: Optional[str] = Query(default=None, description="Filter by team abbreviation"),
    active_only: bool = Query(default=True, description="Only include active players"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List or search NBA players with optional team and active filters."""
    normalized_search = " ".join(search.split()) if search else None
    query = """
        SELECT p.player_id, p.full_name, p.is_active,
               t.abbreviation AS team_abbreviation, t.full_name AS team_name
        FROM players p
        LEFT JOIN teams t ON p.team_id = t.team_id
        WHERE 1=1
    """
    params: dict = {"limit": limit}

    if active_only:
        query += " AND p.is_active = TRUE"
    if normalized_search:
        query += " AND LOWER(p.full_name) LIKE LOWER(:search)"
        params["search"] = f"%{normalized_search}%"
    if team:
        query += " AND t.abbreviation = :team"
        params["team"] = team.strip().upper()

    query += " ORDER BY p.full_name LIMIT :limit"

    rows = db.execute(text(query), params).fetchall()
    players = [dict(r._mapping) for r in rows]
    return {"players": players, "count": len(players)}


@router.get("/players/{player_id}/game-stats")
async def get_player_game_stats(
    player_id: int,
    season: str = Query(default=config.CURRENT_SEASON),
    opponent: Optional[str] = Query(default=None, description="Opponent team abbreviation"),
    date_from: Optional[date] = Query(default=None, description="Start date YYYY-MM-DD"),
    date_to: Optional[date] = Query(default=None, description="End date YYYY-MM-DD"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Get a player's game-by-game stat line for a given season.
    Returns the player's info plus their game log.
    """
    # Player info
    player_row = db.execute(
        text("""
            SELECT p.player_id, p.full_name, p.is_active,
                   t.abbreviation AS team_abbreviation, t.full_name AS team_name
            FROM players p
            LEFT JOIN teams t ON p.team_id = t.team_id
            WHERE p.player_id = :player_id
        """),
        {"player_id": player_id},
    ).fetchone()

    if not player_row:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    player_info = dict(player_row._mapping)

    normalized_from = date_from
    normalized_to = date_to
    if normalized_from and normalized_to and normalized_from > normalized_to:
        normalized_from, normalized_to = normalized_to, normalized_from

    opponent_abbr = opponent.upper().strip() if opponent else None

    # Game log (filtered)
    game_rows = db.execute(
        text("""
            SELECT
                pgs.game_id, m.game_date, m.season,
                pgs_team.abbreviation AS team,
                CASE
                    WHEN pgs.team_id = m.home_team_id THEN opp.abbreviation
                    ELSE opp_h.abbreviation
                END AS opponent,
                CASE
                    WHEN pgs.team_id = m.home_team_id THEN 'vs'
                    ELSE '@'
                END AS location,
                CASE
                    WHEN m.winner_team_id IS NULL THEN NULL
                    WHEN m.winner_team_id = pgs.team_id THEN 'W'
                    ELSE 'L'
                END AS result,
                pgs.minutes, pgs.points, pgs.rebounds, pgs.assists,
                pgs.steals, pgs.blocks, pgs.turnovers, pgs.personal_fouls,
                pgs.field_goals_made, pgs.field_goals_attempted, pgs.field_goal_pct,
                pgs.three_points_made, pgs.three_points_attempted, pgs.three_point_pct,
                pgs.free_throws_made, pgs.free_throws_attempted, pgs.free_throw_pct,
                pgs.plus_minus, pgs.fantasy_points
            FROM player_game_stats pgs
            JOIN matches m ON pgs.game_id = m.game_id
            JOIN teams pgs_team ON pgs.team_id = pgs_team.team_id
            LEFT JOIN teams opp ON m.away_team_id = opp.team_id
            LEFT JOIN teams opp_h ON m.home_team_id = opp_h.team_id
            WHERE pgs.player_id = :player_id
              AND m.season = :season
              AND (
                    :opponent IS NULL OR
                    (
                        CASE
                            WHEN pgs.team_id = m.home_team_id THEN opp.abbreviation
                            ELSE opp_h.abbreviation
                        END
                    ) = :opponent
              )
              AND (:date_from IS NULL OR m.game_date >= :date_from)
              AND (:date_to IS NULL OR m.game_date <= :date_to)
            ORDER BY m.game_date DESC
        """),
        {
            "player_id": player_id,
            "season": season,
            "opponent": opponent_abbr,
            "date_from": normalized_from,
            "date_to": normalized_to,
        },
    ).fetchall()

    filtered_games = [dict(r._mapping) for r in game_rows]
    games = filtered_games[:limit]

    # Compute averages over the full filtered set (not just the limited table rows)
    if filtered_games:
        stat_keys = ["points", "rebounds", "assists", "steals", "blocks", "turnovers"]
        n = len(filtered_games)
        averages = {k: round(sum(g.get(k, 0) or 0 for g in filtered_games) / n, 1) for k in stat_keys}
        averages["games_played"] = n
    else:
        averages = {}

    return {
        "player": player_info,
        "season": season,
        "averages": averages,
        "games": games,
    }


@router.get("/teams/{abbreviation}/game-stats")
async def get_team_game_stats(
    abbreviation: str,
    season: str = Query(default=config.CURRENT_SEASON),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Get a team's game-by-game stats for a given season.
    Returns the team info plus their game log.
    """
    abbr = abbreviation.upper()

    team_row = db.execute(
        text("SELECT team_id, abbreviation, full_name, city FROM teams WHERE abbreviation = :abbr"),
        {"abbr": abbr},
    ).fetchone()

    if not team_row:
        raise HTTPException(status_code=404, detail=f"Team {abbr} not found")

    team_info = dict(team_row._mapping)
    tid = team_info["team_id"]

    game_rows = db.execute(
        text("""
            SELECT
                tgs.game_id, m.game_date, m.season,
                CASE
                    WHEN tgs.team_id = m.home_team_id THEN opp.abbreviation
                    ELSE opp_h.abbreviation
                END AS opponent,
                CASE
                    WHEN tgs.team_id = m.home_team_id THEN 'vs'
                    ELSE '@'
                END AS location,
                CASE
                    WHEN m.winner_team_id IS NULL THEN NULL
                    WHEN m.winner_team_id = tgs.team_id THEN 'W'
                    ELSE 'L'
                END AS result,
                tgs.points,
                CASE
                    WHEN tgs.team_id = m.home_team_id THEN opp_stats.points
                    ELSE home_stats.points
                END AS opponent_points,
                tgs.rebounds, tgs.assists, tgs.steals, tgs.blocks, tgs.turnovers,
                tgs.field_goal_pct, tgs.three_point_pct, tgs.free_throw_pct,
                tgs.offensive_rating, tgs.defensive_rating, tgs.pace,
                tgs.effective_fg_pct, tgs.true_shooting_pct
            FROM team_game_stats tgs
            JOIN matches m ON tgs.game_id = m.game_id
            LEFT JOIN teams opp ON m.away_team_id = opp.team_id
            LEFT JOIN teams opp_h ON m.home_team_id = opp_h.team_id
            LEFT JOIN team_game_stats opp_stats
                ON m.game_id = opp_stats.game_id AND opp_stats.team_id = m.away_team_id
                AND tgs.team_id = m.home_team_id
            LEFT JOIN team_game_stats home_stats
                ON m.game_id = home_stats.game_id AND home_stats.team_id = m.home_team_id
                AND tgs.team_id = m.away_team_id
            WHERE tgs.team_id = :tid
              AND m.season = :season
            ORDER BY m.game_date DESC
            LIMIT :limit
        """),
        {"tid": tid, "season": season, "limit": limit},
    ).fetchall()

    games = [dict(r._mapping) for r in game_rows]

    # Record summary
    wins = sum(1 for g in games if g.get("result") == "W")
    losses = sum(1 for g in games if g.get("result") == "L")

    return {
        "team": team_info,
        "season": season,
        "record": {"wins": wins, "losses": losses, "games": len(games)},
        "games": games,
    }


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
        try:
            audit_logs = db.execute(text("""
                SELECT id, sync_time, module, status, records_processed, records_inserted, errors, details
                FROM pipeline_audit
                ORDER BY sync_time DESC
                LIMIT 10
            """)).fetchall()
        except Exception as audit_err:
            if is_missing_pipeline_audit_error(audit_err):
                logger.warning("pipeline_audit table missing; returning empty audit history")
                audit_logs = []
            else:
                raise
        
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

        audit_violations = None
        latest_ingestion = next((entry for entry in logs if entry.get("module") == "ingestion"), None)
        if latest_ingestion:
            details = latest_ingestion.get("details")
            if isinstance(details, str):
                try:
                    details = json.loads(details)
                except json.JSONDecodeError:
                    details = None
            if isinstance(details, dict):
                audit_violations = details.get("audit_violations")

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
                "last_status": logs[0]["status"] if logs else "unknown",
                "audit_violations": audit_violations,
            },
            "stats": {
                "season": season,
                "matches": matches_count,
                "features": features_count,
                "active_players": players_count
            },
            "models": _model_artifact_snapshot(),
            "audit_history": logs
        }
    except Exception as e:
        logger.error(f"Error fetching system status: {e}")
        return {"status": "error", "message": str(e)}
