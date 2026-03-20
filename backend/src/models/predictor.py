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

        logger.info("📦 Loading trained models from: %s", active_dir)

        for model_name in ["logistic_regression", "xgboost", "lightgbm"]:
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

        return predictions

    def explain_game(self, features: pd.DataFrame, top_n: int = 5) -> Dict[str, List[Dict]]:
        from src.models.explainability import top_shap_factors

        explanations: Dict[str, List[Dict]] = {}
        for name, model in self.models.items():
            explanations[name] = top_shap_factors(model, features, name, top_n=top_n)
        return explanations
    
    def predict_today(self, engine) -> List[Dict]:
        """
        Generate predictions for all games scheduled today.
        
        Returns list of dicts with game info + predictions.
        """
        from datetime import date
        today = date.today()
        
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
            WHERE m.game_date = :today
                AND m.is_completed = FALSE
            ORDER BY m.game_date
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"today": today})
        
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
