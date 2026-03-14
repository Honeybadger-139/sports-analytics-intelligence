"""
Model Artifact Store
====================

🎓 WHAT THIS MODULE DOES:
    Manages versioned model artifacts on disk:
      - Saves models with dated filenames (e.g., xgboost_20260314_143052.pkl)
      - Keeps the newest N artifacts per model type (default: 3)
      - Persists the active artifact directory path in the app_config DB table
      - Loads the active artifact from the DB-configured path, falling back
        to the newest file on disk

🧠 WHY VERSIONED ARTIFACTS?
    Without versioning, every retrain silently overwrites the previous model.
    If a bad model is deployed, there is no rollback path.

    With versioning + keep-N retention:
    - You can roll back by updating the active_model_path config key
    - Disk usage is bounded (not unbounded growth)
    - Audit trail shows exactly when each model was trained

💡 INTERVIEW ANGLE:
    Junior: "I save the model to a file."
    Senior: "I use dated artifact filenames and keep the newest 3 per model
    type. The active artifact path is stored in a DB config table so it can
    be changed via API without redeployment. The predictor reads this path at
    startup — no restart needed to roll back to a previous model."

Wave 3 — SCR-298
"""

from __future__ import annotations

import glob
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import joblib

logger = logging.getLogger(__name__)

# How many artifact versions to retain per model type
ARTIFACT_RETENTION_COUNT: int = 3

MODEL_NAMES = ("logistic_regression", "xgboost", "lightgbm", "ensemble_weights")


def save_artifact(model: Any, model_name: str, model_dir: str, timestamp: str) -> str:
    """
    Save a model artifact with a dated filename.

    Parameters
    ----------
    model       : trained model / weights object
    model_name  : e.g. "xgboost", "logistic_regression", "ensemble_weights"
    model_dir   : directory to save into
    timestamp   : ISO-like string, e.g. "20260314_143052"

    Returns
    -------
    Absolute path to the saved file.
    """
    os.makedirs(model_dir, exist_ok=True)
    filename = f"{model_name}_{timestamp}.pkl"
    filepath = os.path.join(model_dir, filename)
    joblib.dump(model, filepath)
    logger.info("💾 [artifact_store] Saved %s → %s", model_name, filepath)
    return filepath


def purge_old_artifacts(model_name: str, model_dir: str, keep: int = ARTIFACT_RETENTION_COUNT) -> List[str]:
    """
    Delete all but the newest `keep` artifacts for a given model_name.

    Returns list of deleted file paths.
    """
    pattern = os.path.join(model_dir, f"{model_name}_*.pkl")
    files = sorted(glob.glob(pattern))  # lexicographic = chronological for YYYYMMDD_HHMMSS names

    if len(files) <= keep:
        return []

    to_delete = files[: len(files) - keep]
    deleted = []
    for path in to_delete:
        try:
            os.remove(path)
            deleted.append(path)
            logger.info("🗑️  [artifact_store] Purged old artifact: %s", path)
        except OSError as exc:
            logger.warning("[artifact_store] Could not delete %s: %s", path, exc)

    return deleted


def save_all_artifacts(
    training_output: Dict,
    model_dir: str,
    *,
    timestamp: Optional[str] = None,
    keep: int = ARTIFACT_RETENTION_COUNT,
) -> Dict[str, str]:
    """
    Save all model artifacts from a training run and purge old versions.

    Parameters
    ----------
    training_output : dict returned by run_training_pipeline()
    model_dir       : directory to persist artifacts
    timestamp       : override timestamp string (default: now)
    keep            : number of versions to retain per model type

    Returns
    -------
    dict mapping model_name → saved filepath
    """
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    paths: Dict[str, str] = {}

    for name in ("logistic_regression", "xgboost", "lightgbm"):
        model_obj = training_output.get(name, {}).get("model")
        if model_obj is not None:
            path = save_artifact(model_obj, name, model_dir, timestamp)
            paths[name] = path
            purge_old_artifacts(name, model_dir, keep=keep)

    ensemble_weights = training_output.get("ensemble", {}).get("weights")
    if ensemble_weights is not None:
        path = save_artifact(ensemble_weights, "ensemble_weights", model_dir, timestamp)
        paths["ensemble_weights"] = path
        purge_old_artifacts("ensemble_weights", model_dir, keep=keep)

    return paths


def load_latest_artifact(model_name: str, model_dir: str) -> Optional[Any]:
    """
    Load the most recent artifact for `model_name` from `model_dir`.

    Returns None if no matching file exists.
    """
    pattern = os.path.join(model_dir, f"{model_name}_*.pkl")
    files = sorted(glob.glob(pattern))
    if not files:
        logger.warning("[artifact_store] No artifact found for '%s' in %s", model_name, model_dir)
        return None
    latest = files[-1]
    logger.info("📦 [artifact_store] Loading %s from %s", model_name, os.path.basename(latest))
    return joblib.load(latest)


def get_active_model_dir(engine, default_dir: str) -> str:
    """
    Read the active_model_path from app_config table.

    Falls back to `default_dir` if:
    - The DB is unavailable
    - The key is missing or empty
    """
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT value FROM app_config WHERE key = 'active_model_path'")
            ).fetchone()
        if row and row[0] and row[0].strip():
            configured_dir = row[0].strip()
            if os.path.isdir(configured_dir):
                logger.info(
                    "📦 [artifact_store] Using DB-configured model dir: %s", configured_dir
                )
                return configured_dir
            logger.warning(
                "[artifact_store] Configured model dir '%s' does not exist — falling back to default.",
                configured_dir,
            )
    except Exception as exc:
        logger.warning("[artifact_store] Could not read active_model_path from DB: %s", exc)

    return default_dir


def set_active_model_dir(engine, model_dir: str) -> None:
    """Persist the active artifact directory path in app_config."""
    try:
        from sqlalchemy import text

        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO app_config (key, value, description, updated_at)
                    VALUES ('active_model_path', :path,
                            'Path to the active model artifact directory.', NOW())
                    ON CONFLICT (key) DO UPDATE
                        SET value = EXCLUDED.value, updated_at = NOW()
                """),
                {"path": model_dir},
            )
        logger.info("✅ [artifact_store] active_model_path updated to: %s", model_dir)
    except Exception as exc:
        logger.warning("[artifact_store] Could not update active_model_path in DB: %s", exc)
