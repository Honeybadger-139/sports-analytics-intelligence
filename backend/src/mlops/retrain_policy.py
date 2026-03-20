"""
Retrain policy evaluator for dry-run automation decisions.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src import config
from src.data.intelligence_audit_store import record_intelligence_audit


def _vertex_project_id() -> Optional[str]:
    return (os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT_ID") or "").strip() or None


def _vertex_location() -> str:
    return (
        os.getenv("VERTEX_AI_LOCATION")
        or os.getenv("GOOGLE_CLOUD_REGION")
        or os.getenv("REGION")
        or "us-central1"
    )


def _vertex_pipeline_template_path() -> str:
    return (
        os.getenv("VERTEX_RETRAIN_PIPELINE_TEMPLATE")
        or "gs://gamethread-models/pipelines/retrain_pipeline.json"
    )


def _vertex_pipeline_root() -> str:
    return os.getenv("VERTEX_PIPELINE_ROOT") or "gs://gamethread-models/pipelines"


def _submit_vertex_pipeline_job(
    *,
    season: str,
    trigger_reason: str,
    metrics: Dict[str, Any],
    should_retrain: bool,
) -> Dict[str, Any]:
    project_id = _vertex_project_id()
    if not project_id:
        return {
            "submitted": False,
            "reason": "vertex_project_not_configured",
            "project_id": None,
        }

    try:
        from google.cloud import aiplatform
    except Exception as exc:
        return {
            "submitted": False,
            "reason": "vertex_sdk_unavailable",
            "error": str(exc),
            "project_id": project_id,
        }

    location = _vertex_location()
    display_name = f"retrain-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    parameter_values = {
        "season": season,
        "trigger_reason": trigger_reason,
        "database_url": os.getenv("DATABASE_URL", ""),
        "project_id": project_id,
        "min_improvement": float(os.getenv("VERTEX_MIN_IMPROVEMENT", "0.01")),
    }

    try:
        aiplatform.init(project=project_id, location=location)
        pipeline_job = aiplatform.PipelineJob(
            display_name=display_name,
            template_path=_vertex_pipeline_template_path(),
            pipeline_root=_vertex_pipeline_root(),
            parameter_values=parameter_values,
            enable_caching=True,
        )
        pipeline_job.submit()
        return {
            "submitted": True,
            "resource_name": getattr(pipeline_job, "resource_name", None),
            "display_name": display_name,
            "project_id": project_id,
            "location": location,
            "template_path": _vertex_pipeline_template_path(),
            "pipeline_root": _vertex_pipeline_root(),
            "parameter_values": parameter_values,
            "should_retrain": should_retrain,
        }
    except Exception as exc:
        return {
            "submitted": False,
            "reason": "vertex_submission_failed",
            "error": str(exc),
            "project_id": project_id,
            "location": location,
            "template_path": _vertex_pipeline_template_path(),
            "pipeline_root": _vertex_pipeline_root(),
            "parameter_values": parameter_values,
            "should_retrain": should_retrain,
        }


def evaluate_retrain_need(db: Session, season: str, *, dry_run: bool = True) -> Dict[str, Any]:
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
    submission: Optional[Dict[str, Any]] = None

    if not dry_run and should_retrain:
        submission = _submit_vertex_pipeline_job(
            season=season,
            trigger_reason="policy",
            metrics={
                "completed_games": completed_games,
                "evaluated_predictions": evaluated_predictions,
                "new_labels_pending": new_labels_pending,
                "accuracy": accuracy,
                "brier_score": brier,
            },
            should_retrain=should_retrain,
        )
        action = "queue-retrain"

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
        "execution": {
            "pipeline_job": submission,
            "rollback_strategy": "revert_to_previous_model_artifact_on_post_retrain_regression",
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
                "pipeline_job": submission,
            },
        )

    return payload
