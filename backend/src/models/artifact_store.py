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


def _latest_path(pattern: str) -> Optional[str]:
    files = sorted(glob.glob(pattern))
    if not files:
        return None
    return files[-1]


def _gcs_project_id() -> Optional[str]:
    return os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")


def _gcs_bucket_name(bucket_name: Optional[str] = None) -> Optional[str]:
    return bucket_name or os.getenv("GCS_MODELS_BUCKET")


def upload_artifact_to_gcs(
    local_path: str,
    model_name: str,
    timestamp: str,
    bucket_name: Optional[str] = None,
) -> Optional[str]:
    """
    Upload a local artifact to GCS using the standard model artifact layout.
    """
    if not local_path or not os.path.exists(local_path):
        logger.warning("[artifact_store] Local artifact missing, cannot upload: %s", local_path)
        return None

    bucket_name = _gcs_bucket_name(bucket_name)
    if not bucket_name:
        logger.warning("[artifact_store] GCS_MODELS_BUCKET not set; skipping upload for %s", local_path)
        return None

    try:
        from google.cloud import storage

        client = storage.Client(project=_gcs_project_id())
        object_name = f"models/{model_name}/{timestamp}/{os.path.basename(local_path)}"
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        blob.upload_from_filename(local_path)
        gcs_uri = f"gs://{bucket_name}/{object_name}"
        logger.info("[artifact_store] Uploaded %s → %s", local_path, gcs_uri)
        return gcs_uri
    except Exception as exc:
        logger.warning(
            "[artifact_store] Skipping GCS upload for %s (%s): %s",
            model_name,
            local_path,
            exc,
        )
        return None


def download_artifact_from_gcs(
    model_name: str,
    bucket_name: Optional[str],
    local_dir: str,
) -> Optional[str]:
    """
    Download the latest timestamped artifact bundle for a model from GCS.
    """
    bucket_name = _gcs_bucket_name(bucket_name)
    if not bucket_name:
        logger.warning("[artifact_store] GCS_MODELS_BUCKET not set; cannot download %s", model_name)
        return None

    try:
        from google.cloud import storage

        client = storage.Client(project=_gcs_project_id())
        prefix = f"models/{model_name}/"
        blobs = list(client.list_blobs(bucket_name, prefix=prefix))
        if not blobs:
            logger.warning("[artifact_store] No GCS artifacts found for %s in gs://%s", model_name, bucket_name)
            return None

        timestamps: Dict[str, List[Any]] = {}
        for blob in blobs:
            parts = blob.name.split("/")
            if len(parts) < 4:
                continue
            timestamp = parts[2]
            timestamps.setdefault(timestamp, []).append(blob)

        if not timestamps:
            logger.warning("[artifact_store] No timestamped GCS artifacts found for %s", model_name)
            return None

        latest_timestamp = max(timestamps.keys())
        os.makedirs(local_dir, exist_ok=True)
        downloaded_paths: List[str] = []
        for blob in sorted(timestamps[latest_timestamp], key=lambda item: item.name):
            local_path = os.path.join(local_dir, os.path.basename(blob.name))
            blob.download_to_filename(local_path)
            downloaded_paths.append(local_path)

        preferred_path = next((path for path in downloaded_paths if path.endswith(".pkl")), None)
        if preferred_path is None:
            preferred_path = next((path for path in downloaded_paths if path.endswith(".json")), None)
        if preferred_path is None and downloaded_paths:
            preferred_path = downloaded_paths[0]

        logger.info(
            "[artifact_store] Downloaded %d artifacts for %s from gs://%s/%s",
            len(downloaded_paths),
            model_name,
            bucket_name,
            latest_timestamp,
        )
        return preferred_path
    except Exception as exc:
        logger.warning(
            "[artifact_store] Skipping GCS download for %s from gs://%s: %s",
            model_name,
            bucket_name,
            exc,
        )
        return None


def get_latest_artifact_path(model_name: str, model_dir: str) -> Optional[str]:
    """Return the newest saved pickle path for a model name."""
    return _latest_path(os.path.join(model_dir, f"{model_name}_*.pkl"))


def get_latest_version_info_path(model_dir: str) -> Optional[str]:
    """Return the newest version-info JSON path."""
    return _latest_path(os.path.join(model_dir, "version_info_*.json"))


def export_to_onnx(model: Any, model_name: str, model_dir: str, timestamp: str) -> Optional[str]:
    """
    Best-effort export of a trained model to ONNX-compatible artifact storage.

    This is intentionally non-blocking: if conversion fails or the dependency
    stack is unavailable, we log a warning and continue training/serving.
    """
    if model_name.endswith("_calibrator") or model_name == "ensemble_weights":
        return None

    os.makedirs(model_dir, exist_ok=True)
    target_path = os.path.join(model_dir, f"{model_name}_{timestamp}.onnx")

    try:
        if model_name == "xgboost" and hasattr(model, "save_model"):
            model.save_model(target_path)
            logger.info("📦 [artifact_store] Exported %s → %s", model_name, target_path)
            return target_path

        if model_name == "lightgbm":
            booster = getattr(model, "booster_", None) or getattr(model, "booster", None)
            if booster is not None and hasattr(booster, "save_model"):
                booster.save_model(target_path)
                logger.info("📦 [artifact_store] Exported %s → %s", model_name, target_path)
                return target_path
            if hasattr(model, "save_model"):
                model.save_model(target_path)
                logger.info("📦 [artifact_store] Exported %s → %s", model_name, target_path)
                return target_path

        try:
            from skl2onnx import convert_sklearn
            from skl2onnx.common.data_types import FloatTensorType
        except Exception as exc:
            raise RuntimeError(f"skl2onnx unavailable: {exc}") from exc

        if hasattr(model, "named_steps"):
            n_features = getattr(model, "n_features_in_", None)
            if not n_features:
                try:
                    n_features = len(getattr(model, "feature_names_in_", [])) or None
                except Exception:
                    n_features = None
            if not n_features:
                n_features = 1
            initial_types = [("input", FloatTensorType([None, int(n_features)]))]
            onnx_model = convert_sklearn(model, initial_types=initial_types)
            with open(target_path, "wb") as handle:
                handle.write(onnx_model.SerializeToString())
            logger.info("📦 [artifact_store] Exported %s → %s", model_name, target_path)
            return target_path
    except Exception as exc:
        logger.warning(
            "[artifact_store] ONNX export skipped for %s (%s): %s",
            model_name,
            type(model).__name__,
            exc,
        )
        return None

    logger.warning(
        "[artifact_store] ONNX export not supported for %s (%s)",
        model_name,
        type(model).__name__,
    )
    return None


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
    upload_artifact_to_gcs(filepath, model_name, timestamp, os.getenv("GCS_MODELS_BUCKET"))
    export_to_onnx(model, model_name, model_dir, timestamp)
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
