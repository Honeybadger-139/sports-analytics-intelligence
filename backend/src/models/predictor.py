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
import glob
import logging
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
        from src.models.artifact_store import load_latest_artifact, get_active_model_dir

        # Resolve the active model directory from DB config (falls back to disk default)
        if self._engine is not None:
            active_dir = get_active_model_dir(self._engine, MODEL_DIR)
        else:
            active_dir = MODEL_DIR

        logger.info("📦 Loading trained models from: %s", active_dir)

        for model_name in ["logistic_regression", "xgboost", "lightgbm"]:
            model = load_latest_artifact(model_name, active_dir)
            if model is not None:
                self.models[model_name] = model
                logger.info("   ✅ Loaded %s", model_name)

            # Load calibrator if available (Wave 3)
            cal_name = f"{model_name}_calibrator"
            cal = load_latest_artifact(cal_name, active_dir)
            if cal is not None:
                self.calibrators[model_name] = cal
                # Infer method from object type
                from sklearn.linear_model import LogisticRegression
                from sklearn.isotonic import IsotonicRegression
                if isinstance(cal, IsotonicRegression):
                    self.calibration_methods[model_name] = "isotonic"
                else:
                    self.calibration_methods[model_name] = "platt"
                logger.info("   📐 Loaded calibrator for %s (method=%s)", model_name, self.calibration_methods[model_name])

        # Load ensemble weights
        weights = load_latest_artifact("ensemble_weights", active_dir)
        if weights is not None:
            self.ensemble_weights = weights
            logger.info("   ✅ Loaded ensemble weights: %s", self.ensemble_weights)

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
                hf.h2h_win_pct, hf.h2h_avg_margin, hf.current_streak,
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
