"""
Monitoring metrics for model quality and data freshness.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Dict

from sqlalchemy import text
from sqlalchemy.orm import Session

from src import config
from src.data.intelligence_audit_store import record_intelligence_audit


def _days_since(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if hasattr(value, "tzinfo") and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    now = datetime.now(tz=timezone.utc)
    return max((now - value.astimezone(timezone.utc)).days, 0)


def get_monitoring_overview(db: Session, season: str) -> Dict:
    perf_row = db.execute(
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

    latest_game_date = db.execute(
        text("SELECT MAX(game_date) FROM matches WHERE season = :season"),
        {"season": season},
    ).scalar()

    latest_pipeline_sync = db.execute(
        text("SELECT MAX(sync_time) FROM pipeline_audit"),
    ).scalar()

    alerts = []
    accuracy = float(perf_row.accuracy) if perf_row and perf_row.accuracy is not None else None
    brier = float(perf_row.brier_score) if perf_row and perf_row.brier_score is not None else None

    if accuracy is not None and accuracy < config.MLOPS_ACCURACY_THRESHOLD:
        alerts.append(
            {
                "id": "accuracy_breach",
                "severity": "high",
                "message": f"Accuracy {accuracy:.3f} below threshold {config.MLOPS_ACCURACY_THRESHOLD:.3f}",
            }
        )
    if brier is not None and brier > config.MLOPS_MAX_BRIER:
        alerts.append(
            {
                "id": "brier_breach",
                "severity": "medium",
                "message": f"Brier score {brier:.3f} above threshold {config.MLOPS_MAX_BRIER:.3f}",
            }
        )

    game_freshness_days = _days_since(latest_game_date)
    pipeline_freshness_days = _days_since(latest_pipeline_sync)
    if game_freshness_days is not None and game_freshness_days > config.MLOPS_FRESHNESS_DAYS:
        alerts.append(
            {
                "id": "game_data_stale",
                "severity": "medium",
                "message": f"Latest game data is {game_freshness_days} days old.",
            }
        )
    if pipeline_freshness_days is not None and pipeline_freshness_days > config.MLOPS_FRESHNESS_DAYS:
        alerts.append(
            {
                "id": "pipeline_stale",
                "severity": "medium",
                "message": f"Latest pipeline sync is {pipeline_freshness_days} days old.",
            }
        )

    payload = {
        "season": season,
        "metrics": {
            "evaluated_predictions": int(perf_row.evaluated_predictions or 0) if perf_row else 0,
            "accuracy": accuracy,
            "brier_score": brier,
            "latest_game_date": latest_game_date.isoformat() if latest_game_date is not None else None,
            "latest_pipeline_sync": latest_pipeline_sync.isoformat() if latest_pipeline_sync is not None else None,
            "game_data_freshness_days": game_freshness_days,
            "pipeline_freshness_days": pipeline_freshness_days,
        },
        "thresholds": {
            "accuracy_min": config.MLOPS_ACCURACY_THRESHOLD,
            "brier_max": config.MLOPS_MAX_BRIER,
            "freshness_days_max": config.MLOPS_FRESHNESS_DAYS,
        },
        "alerts": alerts,
    }

    engine = db.get_bind() if hasattr(db, "get_bind") else None
    if engine is not None:
        record_intelligence_audit(
            engine,
            module="mlops_monitoring",
            status="degraded" if alerts else "success",
            records_processed=payload["metrics"]["evaluated_predictions"],
            details={
                "season": season,
                "alerts": alerts,
                "thresholds": payload["thresholds"],
            },
        )

    return payload
