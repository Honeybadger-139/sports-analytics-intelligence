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
                    run_details JSONB,
                    error TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        # Backfill schema for existing tables created in earlier sessions.
        conn.execute(text("ALTER TABLE retrain_jobs ADD COLUMN IF NOT EXISTS run_details JSONB"))
        conn.execute(text("ALTER TABLE retrain_jobs ADD COLUMN IF NOT EXISTS error TEXT"))
        conn.execute(text("ALTER TABLE retrain_jobs ADD COLUMN IF NOT EXISTS started_at TIMESTAMP"))
        conn.execute(text("ALTER TABLE retrain_jobs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP"))
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
    attempts = 0
    while attempts < 2:
        try:
            rows = db.execute(
                text(
                    """
                    SELECT
                        id, season, status, trigger_source,
                        created_at, updated_at, started_at, completed_at,
                        reasons, metrics, thresholds,
                        artifact_snapshot, rollback_plan,
                        run_details, error
                    FROM retrain_jobs
                    WHERE season = :season
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"season": season, "limit": limit},
            ).fetchall()
            return [dict(row._mapping) for row in rows]
        except Exception as exc:
            if attempts == 0 and _is_missing_retrain_jobs_error(exc):
                ensure_retrain_jobs_table(db.get_bind())
                attempts += 1
                continue
            raise


def claim_next_retrain_job(engine, *, season: Optional[str] = None) -> Optional[Dict[str, Any]]:
    attempts = 0
    while attempts < 2:
        try:
            with engine.begin() as conn:
                row = conn.execute(
                    text(
                        """
                        WITH next_job AS (
                            SELECT id
                            FROM retrain_jobs
                            WHERE status = 'queued'
                              AND (:season IS NULL OR season = :season)
                            ORDER BY created_at ASC
                            LIMIT 1
                            FOR UPDATE SKIP LOCKED
                        )
                        UPDATE retrain_jobs
                        SET status = 'running',
                            started_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id IN (SELECT id FROM next_job)
                        RETURNING id, season, status, created_at, started_at
                        """
                    ),
                    {"season": season},
                ).fetchone()
            if not row:
                return None
            return dict(row._mapping)
        except Exception as exc:
            if attempts == 0 and _is_missing_retrain_jobs_error(exc):
                ensure_retrain_jobs_table(engine)
                attempts += 1
                continue
            raise


def finalize_retrain_job(
    engine,
    *,
    job_id: int,
    status: str,
    run_details: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    attempts = 0
    while attempts < 2:
        try:
            with engine.begin() as conn:
                row = conn.execute(
                    text(
                        """
                        UPDATE retrain_jobs
                        SET status = :status,
                            run_details = CAST(:run_details AS JSONB),
                            error = :error,
                            completed_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP,
                            artifact_snapshot = CAST(:artifact_snapshot AS JSONB)
                        WHERE id = :job_id
                        RETURNING id, season, status, started_at, completed_at, error
                        """
                    ),
                    {
                        "job_id": job_id,
                        "status": status,
                        "run_details": json.dumps(run_details or {}),
                        "error": error,
                        "artifact_snapshot": json.dumps(_artifact_snapshot()),
                    },
                ).fetchone()
            if not row:
                raise RuntimeError(f"Retrain job {job_id} not found")
            return dict(row._mapping)
        except Exception as exc:
            if attempts == 0 and _is_missing_retrain_jobs_error(exc):
                ensure_retrain_jobs_table(engine)
                attempts += 1
                continue
            raise
