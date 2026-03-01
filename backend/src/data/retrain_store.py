"""
Persistence helpers for retrain job queue.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from src import config


def _is_missing_retrain_jobs_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "retrain_jobs" in message and ("does not exist" in message or "undefinedtable" in message)


def ensure_retrain_jobs_table(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS retrain_jobs (
                    id SERIAL PRIMARY KEY,
                    season VARCHAR(10) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'queued',
                    trigger_source VARCHAR(40) NOT NULL DEFAULT 'policy',
                    reasons JSONB,
                    metrics JSONB,
                    thresholds JSONB,
                    artifact_snapshot JSONB,
                    rollback_plan JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_retrain_jobs_season_status_time
                ON retrain_jobs(season, status, created_at DESC)
                """
            )
        )


def _artifact_snapshot() -> Dict[str, Any]:
    model_dir = Path(config.MODEL_DIR)
    if not model_dir.exists():
        return {"available": False, "artifacts": []}
    artifacts = sorted(
        [
            {
                "name": path.name,
                "size_bytes": path.stat().st_size,
                "updated_at": path.stat().st_mtime,
            }
            for path in model_dir.glob("*")
            if path.is_file()
        ],
        key=lambda item: item["updated_at"],
        reverse=True,
    )
    return {"available": True, "artifacts": artifacts[:10]}


def find_recent_active_retrain_job(engine, *, season: str, window_hours: int = 12) -> Optional[Dict[str, Any]]:
    rows = None
    attempts = 0
    while attempts < 2:
        try:
            with engine.begin() as conn:
                rows = conn.execute(
                    text(
                        """
                        SELECT id, season, status, created_at
                        FROM retrain_jobs
                        WHERE season = :season
                          AND status IN ('queued', 'running')
                          AND created_at >= (CURRENT_TIMESTAMP - (:window_hours || ' hours')::interval)
                        ORDER BY created_at DESC
                        LIMIT 1
                        """
                    ),
                    {"season": season, "window_hours": window_hours},
                ).fetchone()
            break
        except Exception as exc:
            if attempts == 0 and _is_missing_retrain_jobs_error(exc):
                ensure_retrain_jobs_table(engine)
                attempts += 1
                continue
            raise
    if not rows:
        return None
    return dict(rows._mapping)


def create_retrain_job(
    engine,
    *,
    season: str,
    reasons: List[str],
    metrics: Dict[str, Any],
    thresholds: Dict[str, Any],
    trigger_source: str = "policy",
) -> Dict[str, Any]:
    rollback_plan = {
        "strategy": "revert_to_previous_model_artifact",
        "criteria": [
            "post-retrain accuracy below prior baseline by > 0.03",
            "post-retrain brier worsens by > 0.02",
        ],
    }
    attempts = 0
    while attempts < 2:
        try:
            with engine.begin() as conn:
                row = conn.execute(
                    text(
                        """
                        INSERT INTO retrain_jobs (
                            season,
                            status,
                            trigger_source,
                            reasons,
                            metrics,
                            thresholds,
                            artifact_snapshot,
                            rollback_plan
                        )
                        VALUES (
                            :season,
                            'queued',
                            :trigger_source,
                            CAST(:reasons AS JSONB),
                            CAST(:metrics AS JSONB),
                            CAST(:thresholds AS JSONB),
                            CAST(:artifact_snapshot AS JSONB),
                            CAST(:rollback_plan AS JSONB)
                        )
                        RETURNING id, season, status, created_at
                        """
                    ),
                    {
                        "season": season,
                        "trigger_source": trigger_source,
                        "reasons": json.dumps(reasons),
                        "metrics": json.dumps(metrics),
                        "thresholds": json.dumps(thresholds),
                        "artifact_snapshot": json.dumps(_artifact_snapshot()),
                        "rollback_plan": json.dumps(rollback_plan),
                    },
                ).fetchone()
            return dict(row._mapping)
        except Exception as exc:
            if attempts == 0 and _is_missing_retrain_jobs_error(exc):
                ensure_retrain_jobs_table(engine)
                attempts += 1
                continue
            raise


def list_retrain_jobs(db, *, season: str, limit: int = 20) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT id, season, status, trigger_source, created_at, updated_at, reasons, metrics, thresholds
            FROM retrain_jobs
            WHERE season = :season
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"season": season, "limit": limit},
    ).fetchall()
    return [dict(row._mapping) for row in rows]
