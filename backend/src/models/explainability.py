"""
SHAP Explainability Module
==========================

🎓 WHAT IS SHAP?
    SHAP (SHapley Additive exPlanations) answers the question:
    "WHY did the model predict a 65% probability for the home team?"

    It borrows from game theory — specifically Shapley values, which
    fairly distribute a "payout" (prediction) among "players" (features).

    For each prediction, SHAP gives every feature a positive or negative
    contribution. For example:
    - Home advantage: +5% (helps home team)
    - Rolling win %: +8% (home team is on a winning streak)
    - Opponent's defense: -3% (away team has strong defense)
    = Net prediction: 60% home win

🧠 WHY SHAP OVER OTHER METHODS?
    - Feature importance shows global averages → SHAP shows per-prediction
    - Permutation importance is computationally expensive
    - LIME is good but less theoretically grounded
    - SHAP has mathematical guarantees (additive + consistent)

💡 INTERVIEW ANGLE:
    Junior: "I used feature_importances_ from XGBoost"
    Senior: "I used SHAP values because they provide per-prediction
    explanations, not just global feature rankings. This lets me show
    a user exactly WHY the model favors the Lakers tonight — maybe
    it's their recent hot streak and the opponent being on a back-to-back."

    Awe moment: "I found that the model overweighs home advantage for
    cross-conference games, suggesting there's a venue-familiarity effect
    beyond just home-court noise."
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import shap

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# Human-readable feature name mapping
FEATURE_DISPLAY_NAMES = {
    "win_pct_last_5": "5-Game Win %",
    "win_pct_last_10": "10-Game Win %",
    "avg_point_diff_last_5": "5-Game Avg Margin",
    "avg_point_diff_last_10": "10-Game Avg Margin",
    "is_home": "Home Court",
    "days_rest": "Rest Days",
    "is_back_to_back": "Back-to-Back",
    "avg_off_rating_last_5": "Offensive Rating",
    "avg_def_rating_last_5": "Defensive Rating",
    "avg_pace_last_5": "Pace (Last 5)",
    "avg_efg_last_5": "Effective FG%",
    "h2h_win_pct": "H2H Win %",
    "h2h_avg_margin": "H2H Avg Margin",
    "current_streak": "Current Streak",
    "opp_win_pct_last_5": "Opp 5-Game Win %",
    "opp_win_pct_last_10": "Opp 10-Game Win %",
    "opp_avg_point_diff_last_5": "Opp 5-Game Avg Margin",
    "opp_avg_point_diff_last_10": "Opp 10-Game Avg Margin",
    "opp_days_rest": "Opp Rest Days",
    "opp_is_back_to_back": "Opp Back-to-Back",
    "opp_avg_off_rating_last_5": "Opp Off Rating",
    "opp_avg_def_rating_last_5": "Opp Def Rating",
    "opp_avg_pace_last_5": "Opp Pace",
    "opp_avg_efg_last_5": "Opp Effective FG%",
}


def explain_prediction(model, features: pd.DataFrame, model_name: str = "xgboost") -> Dict:
    """
    Generate SHAP explanations for a single game prediction.

    🎓 HOW SHAP WORKS (intuition):
        Imagine you're explaining to your friend why you think Lakers
        will win tonight. You'd say:
        "They've won 4 of their last 5, the opponent is on a back-to-back,
        and they're playing at home."

        SHAP does exactly this but mathematically — it computes the
        marginal contribution of each feature to the prediction.

    Returns:
        Dict with feature contributions sorted by impact.
    """
    try:
        # Choose appropriate SHAP explainer based on model type
        if model_name == "logistic_regression":
            # Use LinearExplainer for linear models
            if hasattr(model, "named_steps"):
                # Pipeline: need to transform first
                scaler = model.named_steps["scaler"]
                lr_model = model.named_steps["model"]
                X_scaled = scaler.transform(features)
                explainer = shap.LinearExplainer(lr_model, X_scaled)
                shap_values = explainer.shap_values(X_scaled)
            else:
                explainer = shap.LinearExplainer(model, features)
                shap_values = explainer.shap_values(features)
        else:
            # Use TreeExplainer for tree-based models (XGBoost, LightGBM)
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(features)

        # Handle different SHAP value shapes
        if isinstance(shap_values, list):
            # Binary classification: use positive class values
            sv = shap_values[1][0] if len(shap_values) > 1 else shap_values[0][0]
        elif len(shap_values.shape) > 1:
            sv = shap_values[0]
        else:
            sv = shap_values

        # Create explanation dict
        feature_names = features.columns.tolist()
        contributions = []

        for i, (name, value) in enumerate(zip(feature_names, sv)):
            display_name = FEATURE_DISPLAY_NAMES.get(name, name)
            feature_value = float(features.iloc[0][name])

            contributions.append({
                "feature": name,
                "display_name": display_name,
                "shap_value": round(float(value), 4),
                "feature_value": round(feature_value, 4),
                "direction": "favors_home" if value > 0 else "favors_away",
                "impact": round(abs(float(value)), 4),
            })

        # Sort by absolute impact (most important first)
        contributions.sort(key=lambda x: x["impact"], reverse=True)

        # Get base value (expected prediction without any features)
        base_value = float(explainer.expected_value)
        if isinstance(explainer.expected_value, np.ndarray):
            base_value = float(explainer.expected_value[1]) if len(explainer.expected_value) > 1 else float(explainer.expected_value[0])

        return {
            "base_value": round(base_value, 4),
            "model_name": model_name,
            "top_factors": contributions[:8],  # Top 8 most impactful features
            "all_factors": contributions,
        }

    except Exception as e:
        logger.error(f"SHAP explanation failed: {e}")
        return {
            "base_value": 0.5,
            "model_name": model_name,
            "top_factors": [],
            "all_factors": [],
            "error": str(e),
        }
