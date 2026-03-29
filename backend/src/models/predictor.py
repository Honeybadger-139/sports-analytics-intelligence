"""
Prediction Serving Module
=========================

🎓 WHAT THIS MODULE DOES:
    Loads trained ML models and generates predictions for upcoming games.
    This is the "inference" side — training happens once, prediction happens
    many times per day.

🧠 DESIGN DECISION:
    We load models at startup (not per-request) to avoid I/O latency.
    In production, you'd use a model registry (MLflow, Weights & Biases)
    to track model versions. For our project, we use file-based versioning.

💡 INTERVIEW ANGLE:
    "I separated training from inference — models are trained in batch and
    served via a stateless prediction API. This lets us scale horizontally
    by adding more API instances behind a load balancer."
"""

import os
import json
import logging
import re
from datetime import date as calendar_date
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import joblib
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")


def _major_version(version: Optional[str]) -> Optional[int]:
    if not version:
        return None
    try:
        return int(str(version).split(".")[0])
    except (TypeError, ValueError):
        return None


def _vertex_project_id() -> Optional[str]:
    return os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT_ID")


def _vertex_location() -> str:
    return os.getenv("VERTEX_MODEL_LOCATION") or "us-central1"


def _parse_gcs_uri(gcs_uri: str) -> tuple[str, str]:
    match = re.match(r"^gs://([^/]+)/(.*)$", gcs_uri.rstrip("/"))
    if not match:
        raise ValueError(f"Unsupported GCS URI: {gcs_uri}")
    return match.group(1), match.group(2)


def _download_gcs_prefix(gcs_uri: str, local_dir: str) -> Optional[str]:
    try:
        from google.cloud import storage
    except Exception as exc:
        logger.warning("[predictor] GCS download unavailable: %s", exc)
        return None

    try:
        bucket_name, prefix = _parse_gcs_uri(gcs_uri)
        client = storage.Client(project=_vertex_project_id())
        bucket = client.bucket(bucket_name)
        blobs = list(client.list_blobs(bucket_name, prefix=prefix))
        if not blobs:
            blob = bucket.blob(prefix)
            if blob.exists(client):
                blobs = [blob]
        if not blobs:
            logger.warning("[predictor] No blobs found under %s", gcs_uri)
            return None

        os.makedirs(local_dir, exist_ok=True)
        for blob in blobs:
            relative_name = blob.name[len(prefix):].lstrip("/") if blob.name.startswith(prefix) else os.path.basename(blob.name)
            if not relative_name:
                relative_name = os.path.basename(blob.name)
            local_path = os.path.join(local_dir, relative_name)
            parent_dir = os.path.dirname(local_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            blob.download_to_filename(local_path)

        artifact_candidates = sorted(Path(local_dir).rglob("*.joblib")) + sorted(Path(local_dir).rglob("*.pkl"))
        if not artifact_candidates:
            logger.warning("[predictor] No model artifact found after downloading %s", gcs_uri)
            return None
        return str(artifact_candidates[-1])
    except Exception as exc:
        logger.warning("[predictor] Failed to download Vertex artifact from %s: %s", gcs_uri, exc)
        return None


def _version_info_path_for_model(
    model_path: Optional[str],
    active_dir: str,
    bucket_name: Optional[str] = None,
) -> Optional[str]:
    if not model_path:
        return None

    base = os.path.basename(model_path)
    match = re.match(r"^(?P<name>.+)_(?P<date>\d{8})_(?P<time>\d{6})\.pkl$", base)
    if not match:
        return None

    timestamp = f"{match.group('date')}_{match.group('time')}"
    candidate = os.path.join(active_dir, f"version_info_{timestamp}.json")
    if os.path.exists(candidate):
        return candidate
    if bucket_name:
        from src.models.artifact_store import download_artifact_from_gcs

        downloaded = download_artifact_from_gcs("version_info", bucket_name, active_dir)
        if downloaded and os.path.exists(downloaded):
            return downloaded
    return None


def _load_model_from_vertex_alias(
    model_name: str,
    alias: str,
    active_dir: str,
) -> tuple[Optional[object], Optional[str], Optional[str]]:
    project_id = _vertex_project_id()
    if not project_id:
        logger.warning("[predictor] Vertex alias lookup skipped because GOOGLE_CLOUD_PROJECT is unset")
        return None, None, None

    try:
        from google.cloud import aiplatform
    except Exception as exc:
        logger.warning("[predictor] Vertex SDK unavailable for alias loading: %s", exc)
        return None, None, None

    try:
        aiplatform.init(project=project_id, location=_vertex_location())
        candidates = aiplatform.Model.list(
            filter=f'display_name="{model_name}"',
            order_by="update_time desc",
            project=project_id,
            location=_vertex_location(),
        )
        if not candidates:
            raise RuntimeError(f"No Vertex models found for display_name={model_name}")

        vertex_model = None
        for candidate in candidates:
            candidate_aliases = getattr(candidate, "version_aliases", None)
            if candidate_aliases is None and getattr(candidate, "gca_resource", None) is not None:
                candidate_aliases = getattr(candidate.gca_resource, "version_aliases", None)
            if alias in (candidate_aliases or []):
                vertex_model = candidate
                break
        if vertex_model is None:
            raise RuntimeError(f"No Vertex model version found for {model_name} with alias={alias}")

        artifact_uri = (
            getattr(vertex_model, "uri", None)
            or getattr(vertex_model, "artifact_uri", None)
            or getattr(getattr(vertex_model, "gca_resource", None), "artifact_uri", None)
        )
        if not artifact_uri:
            raise RuntimeError(f"No artifact URI found for Vertex model {model_name}@{alias}")

        cache_dir = os.path.join(active_dir, "_vertex", model_name, alias)
        local_model_path = _download_gcs_prefix(artifact_uri, cache_dir)
        if not local_model_path:
            raise RuntimeError(f"Failed to download Vertex artifact from {artifact_uri}")

        return joblib.load(local_model_path), local_model_path, artifact_uri
    except Exception as exc:
        logger.warning("[predictor] Vertex alias load failed for %s@%s: %s", model_name, alias, exc)
        return None, None, None


def _load_artifact_with_fallback(
    model_name: str,
    active_dir: str,
    bucket_name: Optional[str],
    *,
    required: bool = True,
):
    from src.models.artifact_store import download_artifact_from_gcs, get_latest_artifact_path

    local_path = get_latest_artifact_path(model_name, active_dir)
    if local_path and os.path.exists(local_path):
        return joblib.load(local_path), local_path, "local"

    if bucket_name:
        downloaded_path = download_artifact_from_gcs(model_name, bucket_name, active_dir)
        if downloaded_path and os.path.exists(downloaded_path):
            return joblib.load(downloaded_path), downloaded_path, "gcs"

    if required:
        raise FileNotFoundError(
            f"No artifact found for {model_name} in {active_dir}"
            + (f" or gs://{bucket_name}" if bucket_name else "")
        )
    return None, None, None


def _check_model_versions(version_info: Dict[str, object]) -> None:
    import sklearn
    import xgboost as xgb

    checks = (
        ("sklearn", sklearn.__version__, version_info.get("sklearn")),
        ("xgboost", xgb.__version__, version_info.get("xgboost")),
    )
    for lib_name, current_version, loaded_version in checks:
        current_major = _major_version(current_version)
        loaded_major = _major_version(str(loaded_version) if loaded_version is not None else None)
        if current_major is None or loaded_major is None:
            continue
        if current_major != loaded_major:
            delta = abs(current_major - loaded_major)
            message = (
                "[predictor] %s major version mismatch: loaded=%s current=%s"
                % (lib_name, loaded_version, current_version)
            )
            logger.warning("%s", message)
            if delta > 1:
                raise RuntimeError(message)


def _emit_prediction_confidence_metric(confidence: float, model_name: str, prediction_count: int = 1) -> None:
    """
    Best-effort Cloud Monitoring hook for prediction confidence.

    The metric is intentionally non-blocking so serving remains resilient when
    GCP credentials or the monitoring SDK are unavailable.
    """
    project_id = _vertex_project_id()
    if not project_id:
        return

    try:
        from src.mlops.gcp_metrics import write_metric
    except Exception as exc:
        logger.debug("[predictor] Cloud Monitoring helper unavailable: %s", exc)
        return

    try:
        write_metric(
            "prediction_confidence",
            float(confidence),
            labels={
                "model_name": model_name,
                "prediction_count": str(prediction_count),
            },
            project_id=project_id,
        )
    except Exception as exc:
        logger.warning("[predictor] Failed to record prediction confidence metric: %s", exc)


class Predictor:
    """
    Loads trained models and generates predictions.

    🎓 DESIGN PATTERN: Singleton-ish / Service Pattern
        We create one Predictor instance at FastAPI startup and reuse it
        for all requests. Models are loaded into memory once.

    Wave 3: Uses artifact_store for versioned loading and applies calibrators
    when available so probabilities are empirically accurate.
    """

    def __init__(self, engine=None):
        self.models = {}
        self.calibrators: Dict[str, object] = {}
        self.calibration_methods: Dict[str, str] = {}
        self.ensemble_weights = {}
        self.feature_columns = None
        self._engine = engine
        self._load_latest_models()

    def _load_latest_models(self):
        """Load the most recently saved models from disk using the artifact store."""
        from src.models.artifact_store import (
            get_active_model_dir,
        )

        # Resolve the active model directory from DB config (falls back to disk default)
        if self._engine is not None:
            active_dir = get_active_model_dir(self._engine, MODEL_DIR)
        else:
            active_dir = MODEL_DIR

        bucket_name = os.getenv("GCS_MODELS_BUCKET")
        vertex_model_name = os.getenv("VERTEX_MODEL_NAME")
        vertex_model_alias = os.getenv("VERTEX_MODEL_ALIAS")
        preloaded_models: set[str] = set()

        logger.info("📦 Loading trained models from: %s", active_dir)

        if vertex_model_name and vertex_model_alias:
            vertex_obj, vertex_path, vertex_source = _load_model_from_vertex_alias(
                vertex_model_name,
                vertex_model_alias,
                active_dir,
            )
            if isinstance(vertex_obj, dict):
                bundle_models = {
                    key: vertex_obj.get(key)
                    for key in ("logistic_regression", "xgboost", "lightgbm")
                    if vertex_obj.get(key) is not None
                }
                if len(bundle_models) == 3:
                    self.models.update(bundle_models)
                    preloaded_models.update(bundle_models.keys())
                    if isinstance(vertex_obj.get("weights"), dict):
                        self.ensemble_weights = vertex_obj["weights"]
                    if isinstance(vertex_obj.get("feature_columns"), list):
                        self.feature_columns = vertex_obj["feature_columns"]
                    logger.info(
                        "   ✅ Loaded bundled Vertex alias model %s@%s (%s)",
                        vertex_model_name,
                        vertex_model_alias,
                        vertex_source,
                    )
                    version_info_path = _version_info_path_for_model(vertex_path, active_dir, bucket_name)
                    if version_info_path:
                        try:
                            with open(version_info_path, "r", encoding="utf-8") as handle:
                                version_info = json.load(handle)
                            _check_model_versions(version_info)
                        except Exception as exc:
                            logger.warning("[predictor] Could not validate bundle version info: %s", exc)
            elif vertex_obj is not None and vertex_model_name in {"logistic_regression", "xgboost", "lightgbm"}:
                self.models[vertex_model_name] = vertex_obj
                preloaded_models.add(vertex_model_name)
                logger.info("   ✅ Loaded %s from Vertex alias %s", vertex_model_name, vertex_model_alias)

        for model_name in ["logistic_regression", "xgboost", "lightgbm"]:
            if model_name in preloaded_models:
                continue
            model, model_path, source = _load_artifact_with_fallback(model_name, active_dir, bucket_name)
            self.models[model_name] = model
            logger.info("   ✅ Loaded %s (%s)", model_name, source)

            version_info_path = _version_info_path_for_model(model_path, active_dir, bucket_name)
            if version_info_path:
                try:
                    with open(version_info_path, "r", encoding="utf-8") as handle:
                        version_info = json.load(handle)
                except Exception as exc:
                    logger.warning(
                        "[predictor] Could not validate version info for %s: %s",
                        model_name,
                        exc,
                    )
                else:
                    _check_model_versions(version_info)
            else:
                logger.warning(
                    "[predictor] No version_info JSON found for %s in %s",
                    model_name,
                    active_dir,
                )

            # Load calibrator if available (Wave 3)
            cal_name = f"{model_name}_calibrator"
            cal, _, cal_source = _load_artifact_with_fallback(cal_name, active_dir, bucket_name, required=False)
            if cal is not None:
                self.calibrators[model_name] = cal
                # Infer method from object type
                from sklearn.linear_model import LogisticRegression
                from sklearn.isotonic import IsotonicRegression
                if isinstance(cal, IsotonicRegression):
                    self.calibration_methods[model_name] = "isotonic"
                else:
                    self.calibration_methods[model_name] = "platt"
                logger.info(
                    "   📐 Loaded calibrator for %s (method=%s, source=%s)",
                    model_name,
                    self.calibration_methods[model_name],
                    cal_source,
                )

        # Load ensemble weights
        weights, _, weights_source = _load_artifact_with_fallback("ensemble_weights", active_dir, bucket_name, required=False)
        if weights is not None:
            self.ensemble_weights = weights
            logger.info("   ✅ Loaded ensemble weights (%s): %s", weights_source, self.ensemble_weights)

        # Import feature columns from trainer
        from src.models.trainer import FEATURE_COLUMNS
        self.feature_columns = FEATURE_COLUMNS

        logger.info("   Total models loaded: %d | calibrators: %d", len(self.models), len(self.calibrators))
    
    def _get_prob(self, model_name: str, model, features: pd.DataFrame) -> float:
        """Get probability for one model, applying calibration if available."""
        from src.models.calibrator import apply_calibration

        cal = self.calibrators.get(model_name)
        method = self.calibration_methods.get(model_name, "none")
        if cal is not None:
            probs = apply_calibration(cal, method, model, features)
            return float(probs[0])
        return float(model.predict_proba(features)[:, 1][0])

    def predict_game(self, features: pd.DataFrame) -> Dict:
        """
        Generate predictions for a single game.

        Args:
            features: DataFrame with home + away team features (1 row)

        Returns:
            Dict with predictions from each model and the ensemble.
            Probabilities are calibrated when a calibrator is loaded (Wave 3).
        """
        predictions = {}

        for name, model in self.models.items():
            prob = self._get_prob(name, model, features)
            predictions[name] = {
                "home_win_prob": round(prob, 4),
                "away_win_prob": round(float(1 - prob), 4),
                "prediction": "home" if prob >= 0.5 else "away",
                "confidence": round(float(max(prob, 1 - prob)), 4),
                "calibrated": name in self.calibrators,
            }

        # Ensemble prediction
        if self.ensemble_weights and len(predictions) > 0:
            probs = []
            weights = []
            for name, weight in self.ensemble_weights.items():
                model_key = name.lower().replace(" ", "_")
                if model_key in predictions:
                    probs.append(predictions[model_key]["home_win_prob"])
                    weights.append(weight)

            if probs:
                ensemble_prob = float(np.average(probs, weights=weights))
                predictions["ensemble"] = {
                    "home_win_prob": round(ensemble_prob, 4),
                    "away_win_prob": round(1 - ensemble_prob, 4),
                    "prediction": "home" if ensemble_prob >= 0.5 else "away",
                    "confidence": round(max(ensemble_prob, 1 - ensemble_prob), 4),
                    "calibrated": len(self.calibrators) > 0,
                }

        if predictions:
            ensemble_prediction = predictions.get("ensemble")
            if ensemble_prediction is not None:
                metric_confidence = ensemble_prediction["confidence"]
                metric_model_name = "ensemble"
            else:
                metric_confidence = max(item["confidence"] for item in predictions.values())
                metric_model_name = max(predictions.items(), key=lambda item: item[1]["confidence"])[0]
            _emit_prediction_confidence_metric(metric_confidence, metric_model_name)

        return predictions

    def explain_game(self, features: pd.DataFrame, top_n: int = 5) -> Dict[str, List[Dict]]:
        from src.models.explainability import top_shap_factors

        explanations: Dict[str, List[Dict]] = {}
        for name, model in self.models.items():
            explanations[name] = top_shap_factors(model, features, name, top_n=top_n)
        return explanations
    
    def predict_for_date(self, engine, target_date: Optional[calendar_date] = None) -> List[Dict]:
        """
        Generate predictions for all uncompleted games scheduled on a target date.

        Defaults to the current date when no explicit target date is provided.
        """
        target_date = target_date or calendar_date.today()

        query = text("""
            SELECT 
                m.game_id,
                m.game_date,
                ht.abbreviation as home_team,
                ht.full_name as home_team_name,
                at.abbreviation as away_team,
                at.full_name as away_team_name,
                -- Home team features
                hf.win_pct_last_5, hf.win_pct_last_10,
                hf.avg_point_diff_last_5, hf.avg_point_diff_last_10,
                1 as is_home, hf.days_rest,
                CASE WHEN hf.is_back_to_back THEN 1 ELSE 0 END as is_back_to_back,
                hf.avg_off_rating_last_5, hf.avg_def_rating_last_5,
                hf.avg_pace_last_5, hf.avg_efg_last_5,
                hf.h2h_win_pct, hf.h2h_avg_margin,
                CASE WHEN hf.h2h_win_pct IS NOT NULL THEN 1 ELSE 0 END as h2h_data_available,
                hf.current_streak,
                -- Away team features
                af.win_pct_last_5 as opp_win_pct_last_5,
                af.win_pct_last_10 as opp_win_pct_last_10,
                af.avg_point_diff_last_5 as opp_avg_point_diff_last_5,
                af.avg_point_diff_last_10 as opp_avg_point_diff_last_10,
                af.days_rest as opp_days_rest,
                CASE WHEN af.is_back_to_back THEN 1 ELSE 0 END as opp_is_back_to_back,
                af.avg_off_rating_last_5 as opp_avg_off_rating_last_5,
                af.avg_def_rating_last_5 as opp_avg_def_rating_last_5,
                af.avg_pace_last_5 as opp_avg_pace_last_5,
                af.avg_efg_last_5 as opp_avg_efg_last_5
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            LEFT JOIN match_features hf ON m.game_id = hf.game_id AND m.home_team_id = hf.team_id
            LEFT JOIN match_features af ON m.game_id = af.game_id AND m.away_team_id = af.team_id
            WHERE m.game_date = :target_date
                AND m.is_completed = FALSE
            ORDER BY m.game_date
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"target_date": target_date})
        
        if df.empty:
            return []
        
        results = []
        for _, row in df.iterrows():
            features = row[self.feature_columns].fillna(0).to_frame().T.astype(float)
            predictions = self.predict_game(features)
            shap_factors = self.explain_game(features, top_n=5)
            
            results.append({
                "game_id": row["game_id"],
                "game_date": str(row["game_date"]),
                "home_team": row["home_team"],
                "home_team_name": row["home_team_name"],
                "away_team": row["away_team"],
                "away_team_name": row["away_team_name"],
                "predictions": predictions,
                "shap_factors": shap_factors,
            })
        
        return results

    def predict_today(self, engine) -> List[Dict]:
        """Backward-compatible helper for same-day predictions."""
        return self.predict_for_date(engine, calendar_date.today())
