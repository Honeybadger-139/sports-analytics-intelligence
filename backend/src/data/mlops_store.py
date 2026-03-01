"""
Persistence helpers for MLOps monitoring snapshots.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from sqlalchemy import text


def _is_missing_snapshot_table_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "mlops_monitoring_snapshot" in message and (
        "does not exist" in message or "undefinedtable" in message
    )


def ensure_mlops_snapshot_table(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS mlops_monitoring_snapshot (
                    id SERIAL PRIMARY KEY,
                    snapshot_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    season VARCHAR(10) NOT NULL,
                    evaluated_predictions INTEGER DEFAULT 0,
                    accuracy DECIMAL(6,4),
                    brier_score DECIMAL(6,4),
                    game_data_freshness_days INTEGER,
                    pipeline_freshness_days INTEGER,
                    alert_count INTEGER DEFAULT 0,
                    details JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_mlops_snapshot_season_time
                ON mlops_monitoring_snapshot(season, snapshot_time DESC)
                """
            )
        )


def record_monitoring_snapshot(engine, *, season: str, payload: Dict[str, Any]) -> None:
    metrics = payload.get("metrics") or {}
    alerts = payload.get("alerts") or []
    details_json = json.dumps(
        {
            "thresholds": payload.get("thresholds") or {},
            "alerts": alerts,
        }
    )

    attempts = 0
    while attempts < 2:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO mlops_monitoring_snapshot (
                            season,
                            evaluated_predictions,
                            accuracy,
                            brier_score,
                            game_data_freshness_days,
                            pipeline_freshness_days,
                            alert_count,
                            details
                        )
                        VALUES (
                            :season,
                            :evaluated_predictions,
                            :accuracy,
                            :brier_score,
                            :game_data_freshness_days,
                            :pipeline_freshness_days,
                            :alert_count,
                            CAST(:details AS JSONB)
                        )
                        """
                    ),
                    {
                        "season": season,
                        "evaluated_predictions": int(metrics.get("evaluated_predictions") or 0),
                        "accuracy": metrics.get("accuracy"),
                        "brier_score": metrics.get("brier_score"),
                        "game_data_freshness_days": metrics.get("game_data_freshness_days"),
                        "pipeline_freshness_days": metrics.get("pipeline_freshness_days"),
                        "alert_count": len(alerts),
                        "details": details_json,
                    },
                )
            return
        except Exception as exc:
            if attempts == 0 and _is_missing_snapshot_table_error(exc):
                ensure_mlops_snapshot_table(engine)
                attempts += 1
                continue
            raise


def fetch_monitoring_trend(db, *, season: str, days: int, limit: int) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT
                snapshot_time,
                evaluated_predictions,
                accuracy,
                brier_score,
                game_data_freshness_days,
                pipeline_freshness_days,
                alert_count
            FROM mlops_monitoring_snapshot
            WHERE season = :season
              AND snapshot_time >= (CURRENT_TIMESTAMP - (:days || ' days')::interval)
            ORDER BY snapshot_time DESC
            LIMIT :limit
            """
        ),
        {"season": season, "days": days, "limit": limit},
    ).fetchall()
    return [dict(row._mapping) for row in rows]
