"""
Prediction persistence and outcome synchronization utilities.
"""

import json
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def is_missing_predictions_table_error(exc: Exception) -> bool:
    """Detect missing-table errors for predictions relation."""
    message = str(exc).lower()
    return "predictions" in message and (
        "does not exist" in message or "undefinedtable" in message
    )


def ensure_predictions_table(db: Session) -> None:
    """Create predictions table/indexes if absent (legacy volume guardrail)."""
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                id SERIAL PRIMARY KEY,
                game_id VARCHAR(20) REFERENCES matches(game_id),
                model_name VARCHAR(50) NOT NULL,
                home_win_prob DECIMAL(5,4),
                away_win_prob DECIMAL(5,4),
                confidence DECIMAL(5,4),
                shap_factors JSONB,
                predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                was_correct BOOLEAN,
                UNIQUE (game_id, model_name)
            )
            """
        )
    )
    db.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_predictions_game
            ON predictions(game_id)
            """
        )
    )
    db.execute(text("ALTER TABLE predictions ADD COLUMN IF NOT EXISTS shap_factors JSONB"))
    db.commit()


def ensure_pre_game_columns(db: Session) -> None:
    """Idempotently add pre-game prediction and RAG enrichment columns (SCR-331)."""
    for stmt in [
        "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS is_pre_game BOOLEAN DEFAULT FALSE",
        "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS news_context JSONB",
        "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS enriched_at TIMESTAMP",
    ]:
        db.execute(text(stmt))
    db.commit()


def persist_game_predictions(
    db: Session,
    game_id: str,
    predictions: Dict[str, Dict],
    shap_factors_by_model: Optional[Dict[str, list]] = None,
    predicted_at: Optional[datetime] = None,
    is_pre_game: bool = False,
) -> int:
    """
    Persist per-model predictions for one game using idempotent upsert.
    Pass is_pre_game=True for upcoming scheduled games predicted before tip-off.
    """
    if not predictions:
        return 0

    predicted_at = predicted_at or datetime.utcnow()

    attempts = 0
    while attempts < 2:
        try:
            for model_name, payload in predictions.items():
                db.execute(
                    text(
                        """
                        INSERT INTO predictions (
                            game_id, model_name, home_win_prob, away_win_prob,
                            confidence, shap_factors, predicted_at, is_pre_game
                        )
                        VALUES (
                            :game_id, :model_name, :home_win_prob, :away_win_prob,
                            :confidence, CAST(:shap_factors AS JSONB), :predicted_at, :is_pre_game
                        )
                        ON CONFLICT (game_id, model_name) DO UPDATE SET
                            home_win_prob = EXCLUDED.home_win_prob,
                            away_win_prob = EXCLUDED.away_win_prob,
                            confidence = EXCLUDED.confidence,
                            shap_factors = EXCLUDED.shap_factors,
                            predicted_at = EXCLUDED.predicted_at,
                            is_pre_game = EXCLUDED.is_pre_game
                        """
                    ),
                    {
                        "game_id": game_id,
                        "model_name": model_name,
                        "home_win_prob": payload.get("home_win_prob"),
                        "away_win_prob": payload.get("away_win_prob"),
                        "confidence": payload.get("confidence"),
                        "shap_factors": json.dumps((shap_factors_by_model or {}).get(model_name) or []),
                        "predicted_at": predicted_at,
                        "is_pre_game": is_pre_game,
                    },
                )
            db.commit()
            return len(predictions)
        except Exception as exc:
            db.rollback()
            if attempts == 0 and is_missing_predictions_table_error(exc):
                ensure_predictions_table(db)
                attempts += 1
                continue
            raise

    return 0


def persist_news_enrichment(
    db: Session,
    game_id: str,
    model_name: str,
    news_context: dict,
    home_win_prob_adjusted: Optional[float] = None,
) -> None:
    """
    Store RAG-derived news context and optional probability adjustment
    against an existing prediction row. Called from prediction_enricher.py.
    """
    from datetime import datetime as dt
    updates: dict = {
        "game_id": game_id,
        "model_name": model_name,
        "news_context": json.dumps(news_context),
        "enriched_at": dt.utcnow(),
    }
    set_clause = "news_context = CAST(:news_context AS JSONB), enriched_at = :enriched_at"

    if home_win_prob_adjusted is not None:
        away = round(1.0 - home_win_prob_adjusted, 4)
        set_clause += ", home_win_prob = :home_adj, away_win_prob = :away_adj, confidence = :home_adj"
        updates["home_adj"] = round(home_win_prob_adjusted, 4)
        updates["away_adj"] = away

    db.execute(
        text(f"""
            UPDATE predictions
            SET {set_clause}
            WHERE game_id = :game_id AND model_name = :model_name
        """),
        updates,
    )
    db.commit()


def sync_prediction_outcomes(
    db: Session,
    season: Optional[str] = None,
    game_id: Optional[str] = None,
) -> int:
    """
    Update was_correct for completed matches based on predicted winner.
    """
    filters = ["m.is_completed = TRUE"]
    params = {}

    if season:
        filters.append("m.season = :season")
        params["season"] = season

    if game_id:
        filters.append("m.game_id = :game_id")
        params["game_id"] = game_id

    where_clause = " AND ".join(filters)

    result = db.execute(
        text(
            f"""
            UPDATE predictions p
            SET was_correct = CASE
                WHEN m.winner_team_id = m.home_team_id THEN (p.home_win_prob >= p.away_win_prob)
                ELSE (p.away_win_prob > p.home_win_prob)
            END
            FROM matches m
            WHERE p.game_id = m.game_id
              AND {where_clause}
              AND p.home_win_prob IS NOT NULL
              AND p.away_win_prob IS NOT NULL
            """
        ),
        params,
    )
    db.commit()
    return int(result.rowcount or 0)
