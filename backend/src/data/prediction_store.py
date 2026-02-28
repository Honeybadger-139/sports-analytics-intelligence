"""
Prediction persistence and outcome synchronization utilities.
"""

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
    db.commit()


def persist_game_predictions(
    db: Session,
    game_id: str,
    predictions: Dict[str, Dict],
    predicted_at: Optional[datetime] = None,
) -> int:
    """
    Persist per-model predictions for one game using idempotent upsert.
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
                            game_id, model_name, home_win_prob, away_win_prob, confidence, predicted_at
                        )
                        VALUES (
                            :game_id, :model_name, :home_win_prob, :away_win_prob, :confidence, :predicted_at
                        )
                        ON CONFLICT (game_id, model_name) DO UPDATE SET
                            home_win_prob = EXCLUDED.home_win_prob,
                            away_win_prob = EXCLUDED.away_win_prob,
                            confidence = EXCLUDED.confidence,
                            predicted_at = EXCLUDED.predicted_at
                        """
                    ),
                    {
                        "game_id": game_id,
                        "model_name": model_name,
                        "home_win_prob": payload.get("home_win_prob"),
                        "away_win_prob": payload.get("away_win_prob"),
                        "confidence": payload.get("confidence"),
                        "predicted_at": predicted_at,
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
