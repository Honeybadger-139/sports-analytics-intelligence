"""
Retrain policy evaluator for dry-run automation decisions.
"""

from __future__ import annotations

from typing import Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from src import config
from src.data.intelligence_audit_store import record_intelligence_audit


def evaluate_retrain_need(db: Session, season: str, *, dry_run: bool = True) -> Dict:
    reasons: List[str] = []

    metrics = db.execute(
        text(
            """
            SELECT
                COUNT(*) AS evaluated_predictions,
                ROUND(AVG(CASE WHEN p.was_correct THEN 1.0 ELSE 0.0 END)::numeric, 4) AS accuracy,
                ROUND(AVG(POWER(
                    p.home_win_prob::numeric - (CASE WHEN m.winner_team_id = m.home_team_id THEN 1 ELSE 0 END), 2
                ))::numeric, 4) AS brier_score
            FROM predictions p
            JOIN matches m ON p.game_id = m.game_id
            WHERE m.season = :season
              AND m.is_completed = TRUE
              AND p.was_correct IS NOT NULL
            """
        ),
        {"season": season},
    ).fetchone()

    completed_games = int(
        db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM matches
                WHERE season = :season
                  AND is_completed = TRUE
                """
            ),
            {"season": season},
        ).scalar()
        or 0
    )
    evaluated_predictions = int(metrics.evaluated_predictions or 0) if metrics else 0
    new_labels_pending = max(completed_games - evaluated_predictions, 0)

    accuracy = float(metrics.accuracy) if metrics and metrics.accuracy is not None else None
    brier = float(metrics.brier_score) if metrics and metrics.brier_score is not None else None

    if accuracy is not None and accuracy < config.MLOPS_ACCURACY_THRESHOLD:
        reasons.append(
            f"accuracy_breach: {accuracy:.3f} < {config.MLOPS_ACCURACY_THRESHOLD:.3f}"
        )
    if brier is not None and brier > config.MLOPS_MAX_BRIER:
        reasons.append(f"brier_breach: {brier:.3f} > {config.MLOPS_MAX_BRIER:.3f}")
    if new_labels_pending >= config.MLOPS_NEW_LABEL_MIN:
        reasons.append(
            f"new_labels_threshold: {new_labels_pending} >= {config.MLOPS_NEW_LABEL_MIN}"
        )

    should_retrain = len(reasons) > 0
    action = "dry-run-noop" if dry_run else ("queue-retrain" if should_retrain else "noop")

    payload = {
        "season": season,
        "dry_run": dry_run,
        "should_retrain": should_retrain,
        "action": action,
        "reasons": reasons,
        "metrics": {
            "completed_games": completed_games,
            "evaluated_predictions": evaluated_predictions,
            "new_labels_pending": new_labels_pending,
            "accuracy": accuracy,
            "brier_score": brier,
        },
        "thresholds": {
            "accuracy_min": config.MLOPS_ACCURACY_THRESHOLD,
            "brier_max": config.MLOPS_MAX_BRIER,
            "new_labels_min": config.MLOPS_NEW_LABEL_MIN,
        },
    }

    engine = db.get_bind() if hasattr(db, "get_bind") else None
    if engine is not None:
        record_intelligence_audit(
            engine,
            module="mlops_retrain_policy",
            status="degraded" if should_retrain else "success",
            records_processed=payload["metrics"]["new_labels_pending"],
            details={
                "season": season,
                "dry_run": dry_run,
                "action": action,
                "reasons": reasons,
                "thresholds": payload["thresholds"],
            },
        )

    return payload
