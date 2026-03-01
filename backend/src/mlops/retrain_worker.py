"""
Worker utilities for executing queued retrain jobs.
"""

from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy.orm import Session

from src.data.intelligence_audit_store import record_intelligence_audit
from src.data.retrain_store import claim_next_retrain_job, finalize_retrain_job


def _summarize_training_output(payload: Dict) -> Dict:
    summary = {}
    for key in ("logistic_regression", "xgboost", "lightgbm"):
        model_payload = payload.get(key) or {}
        summary[key] = {
            "cv_accuracy": model_payload.get("cv_accuracy"),
            "cv_auc": model_payload.get("cv_auc"),
            "train_accuracy": model_payload.get("train_accuracy"),
            "brier_score": model_payload.get("brier_score"),
        }
    ensemble_payload = payload.get("ensemble") or {}
    summary["ensemble"] = {
        "train_accuracy": ensemble_payload.get("train_accuracy"),
        "train_auc": ensemble_payload.get("train_auc"),
        "brier_score": ensemble_payload.get("brier_score"),
    }
    return summary


def process_next_retrain_job(db: Session, *, season: Optional[str] = None, execute: bool = False) -> Dict:
    """
    Claim and process the oldest queued retrain job.

    execute=False keeps this safe for first-run validation by completing with
    a simulation marker. execute=True runs the actual training pipeline.
    """
    engine = db.get_bind() if hasattr(db, "get_bind") else None
    if engine is None:
        raise RuntimeError("Database engine unavailable")

    job = claim_next_retrain_job(engine, season=season)
    if not job:
        return {
            "status": "noop",
            "message": "No queued retrain jobs available.",
            "job": None,
        }

    try:
        if execute:
            from src.models.trainer import run_training_pipeline

            training_output = run_training_pipeline(season=job["season"])
            if not training_output:
                raise RuntimeError("Training pipeline returned no output")
            run_details = {
                "mode": "execute",
                "training_summary": _summarize_training_output(training_output),
            }
        else:
            run_details = {
                "mode": "simulate",
                "note": "Training execution skipped; this run validates lifecycle behavior.",
            }

        finalized = finalize_retrain_job(
            engine,
            job_id=job["id"],
            status="completed",
            run_details=run_details,
        )
        record_intelligence_audit(
            engine,
            module="mlops_retrain_worker",
            status="success",
            records_processed=1,
            details={
                "job_id": finalized["id"],
                "season": finalized["season"],
                "execute": execute,
                "mode": run_details.get("mode"),
            },
        )
        return {
            "status": "completed",
            "message": "Retrain job processed successfully.",
            "job": finalized,
            "run_details": run_details,
        }
    except Exception as exc:
        failed = finalize_retrain_job(
            engine,
            job_id=job["id"],
            status="failed",
            run_details={"mode": "execute" if execute else "simulate"},
            error=str(exc),
        )
        record_intelligence_audit(
            engine,
            module="mlops_retrain_worker",
            status="failed",
            records_processed=1,
            errors=str(exc),
            details={
                "job_id": failed["id"],
                "season": failed["season"],
                "execute": execute,
            },
        )
        return {
            "status": "failed",
            "message": f"Retrain job failed: {exc}",
            "job": failed,
        }
