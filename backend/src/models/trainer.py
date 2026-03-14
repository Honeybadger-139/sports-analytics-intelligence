"""
Model Training Module
=====================

🎓 WHAT THIS MODULE DOES:
    Trains ML models to predict NBA game outcomes (win/loss) using the
    engineered features from our feature store.

🧠 THE MODEL PROGRESSION (WHY THIS ORDER):
    1. Logistic Regression → Baseline. Simple, interpretable, fast.
       If this beats 50%, we know our features have signal.
    2. XGBoost → Gradient-boosted trees. Handles non-linear relationships
       and feature interactions automatically. The industry standard.
    3. LightGBM → Microsoft's faster, more memory-efficient alternative
       to XGBoost. Often wins Kaggle competitions.
    4. Ensemble → Combine all three with weighted averaging. Different
       models capture different patterns — ensembles are almost always better.

💡 INTERVIEW ANGLE:
    Junior: "I used XGBoost because it's the best model"
    Senior: "I started with Logistic Regression as a baseline to establish
    that our features have predictive signal. Then I trained XGBoost and
    LightGBM to capture non-linear patterns. I ensembled them with weights
    proportional to their cross-validation AUC-ROC. The ensemble improved
    accuracy by 2.3% over the best individual model."

    Awe moment: "I time-series split the data chronologically instead of
    random k-fold because sports outcomes have temporal dependencies. Using
    random splits would leak future information into training."

Architecture Decision: See docs/decisions/decision-log.md
    We use time-series cross-validation instead of random k-fold because:
    - Sports data has temporal dependencies (momentum, streaks)
    - Random splits would leak future information
    - TimeSeriesSplit mimics how we'd deploy in production
"""

import os
import json
import logging
import joblib
from datetime import datetime
from typing import Dict, Tuple, Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    roc_auc_score,
    log_loss,
    brier_score_loss,
)
from sklearn.pipeline import Pipeline
import xgboost as xgb
import lightgbm as lgb
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from src import config

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Directory to save trained model artifacts
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")
os.makedirs(MODEL_DIR, exist_ok=True)

# Feature columns used for prediction
FEATURE_COLUMNS = [
    "win_pct_last_5",
    "win_pct_last_10",
    "avg_point_diff_last_5",
    "avg_point_diff_last_10",
    "is_home",
    "days_rest",
    "is_back_to_back",
    "avg_off_rating_last_5",
    "avg_def_rating_last_5",
    "avg_pace_last_5",
    "avg_efg_last_5",
    "h2h_win_pct",
    "h2h_avg_margin",
    "current_streak",
    # Opponent features (prefixed with opp_)
    "opp_win_pct_last_5",
    "opp_win_pct_last_10",
    "opp_avg_point_diff_last_5",
    "opp_avg_point_diff_last_10",
    "opp_days_rest",
    "opp_is_back_to_back",
    "opp_avg_off_rating_last_5",
    "opp_avg_def_rating_last_5",
    "opp_avg_pace_last_5",
    "opp_avg_efg_last_5",
]


def get_engine():
    """Create SQLAlchemy engine."""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://analyst:analytics2026@localhost:5432/sports_analytics",
    )
    return create_engine(database_url)


def load_training_dataset(
    engine,
    season: Optional[str] = "2024-25",
    *,
    cutoff_date: Optional[str] = None,
    validation_season: Optional[str] = None,
) -> Dict[str, object]:
    """
    Load features + target from PostgreSQL, combining home and away team features.

    🎓 KEY DESIGN DECISION:
        Each game has TWO feature rows (one per team). For ML, we need ONE
        row per game with features from BOTH teams' perspectives.

        We join home team features with away team features, creating a
        single row with both sets of features. The target is: did the home
        team win? (1=yes, 0=no)

        This framing means our model predicts: "Given home team's form vs
        away team's form, will the home team win?"

    """
    validation_season = validation_season or config.CURRENT_SEASON
    logger.info("📥 Loading training data | season=%s | cutoff_date=%s | validation_season=%s", season, cutoff_date, validation_season)

    query = text("""
        SELECT
            m.game_id,
            m.game_date,
            m.season,
            m.home_team_id,
            m.away_team_id,
            CASE WHEN m.winner_team_id = m.home_team_id THEN 1 ELSE 0 END as home_win,
            -- Home team features
            hf.win_pct_last_5,
            hf.win_pct_last_10,
            hf.avg_point_diff_last_5,
            hf.avg_point_diff_last_10,
            1 as is_home,
            hf.days_rest,
            CASE WHEN hf.is_back_to_back THEN 1 ELSE 0 END as is_back_to_back,
            hf.avg_off_rating_last_5,
            hf.avg_def_rating_last_5,
            hf.avg_pace_last_5,
            hf.avg_efg_last_5,
            hf.h2h_win_pct,
            hf.h2h_avg_margin,
            hf.current_streak,
            -- Away team features (prefixed opp_)
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
        JOIN match_features hf ON m.game_id = hf.game_id AND m.home_team_id = hf.team_id
        JOIN match_features af ON m.game_id = af.game_id AND m.away_team_id = af.team_id
        WHERE m.is_completed = TRUE
          AND (
            :season IS NULL
            OR m.season = :season
            OR (:validation_season IS NOT NULL AND m.season = :validation_season)
          )
        ORDER BY m.game_date ASC
    """)

    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"season": season, "validation_season": validation_season})

    logger.info(f"   Loaded {len(df)} games with features")

    # Handle NaN values
    df = df.fillna(0)

    # Convert numeric columns
    for col in FEATURE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if not df.empty:
        df["game_date"] = pd.to_datetime(df["game_date"])

    train_mask = pd.Series([True] * len(df), index=df.index)
    validation_mask = pd.Series([False] * len(df), index=df.index)
    cutoff_timestamp = pd.to_datetime(cutoff_date) if cutoff_date else None
    if cutoff_timestamp is not None:
        train_mask = df["game_date"] < cutoff_timestamp
        validation_mask = (df["season"] == validation_season) & (df["game_date"] >= cutoff_timestamp)
    elif validation_season:
        validation_mask = df["season"] == validation_season
        train_mask = ~validation_mask

    train_df = df.loc[train_mask].copy()
    validation_df = df.loc[validation_mask].copy()

    X = train_df[FEATURE_COLUMNS].astype(float)
    y = train_df["home_win"].astype(int)
    validation_X = validation_df[FEATURE_COLUMNS].astype(float) if not validation_df.empty else pd.DataFrame(columns=FEATURE_COLUMNS)
    validation_y = validation_df["home_win"].astype(int) if not validation_df.empty else pd.Series(dtype=int)

    logger.info(f"   Features shape: {X.shape}")
    logger.info(f"   Home win rate: {y.mean():.3f}")
    logger.info("   Validation shape: %s", validation_X.shape)

    return {
        "train_X": X,
        "train_y": y,
        "validation_X": validation_X,
        "validation_y": validation_y,
        "metadata": {
            "season": season,
            "cutoff_date": cutoff_timestamp.date().isoformat() if cutoff_timestamp is not None else None,
            "validation_season": validation_season,
            "training_games": int(len(train_df)),
            "validation_games": int(len(validation_df)),
        },
    }


def load_training_data(engine, season: str = "2024-25") -> Tuple[pd.DataFrame, pd.Series]:
    dataset = load_training_dataset(engine, season=season)
    return dataset["train_X"], dataset["train_y"]


def train_logistic_regression(X: pd.DataFrame, y: pd.Series) -> Dict:
    """
    Train baseline Logistic Regression model.

    🎓 WHY START WITH LOGISTIC REGRESSION?
        1. It's interpretable — you can see which features matter most
           by looking at the coefficients
        2. It's fast — trains in milliseconds
        3. It provides calibrated probabilities out of the box
        4. If LR can't beat 50%, your features might not have signal
        5. It sets the baseline that complex models must beat

    🎓 WHAT IS LOGISTIC REGRESSION?
        Despite the name, it's a CLASSIFICATION model. It predicts the
        probability of a binary outcome using a sigmoid function:
        P(win) = 1 / (1 + e^(-z)) where z = w1*x1 + w2*x2 + ... + b

        The sigmoid squashes any number into [0, 1] — perfect for probabilities.

    🎓 WHY StandardScaler?
        LR is sensitive to feature scale. If "points" ranges 80-130 but
        "fg_pct" ranges 0.3-0.6, the model would overweight points.
        StandardScaler normalizes all features to mean=0, std=1.
    """
    logger.info("🔵 Training Logistic Regression (baseline)...")

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(
            C=1.0,            # Regularization (lower = more regularization)
            max_iter=1000,
            random_state=42,
            solver="lbfgs",   # Best for small-medium datasets
        )),
    ])

    # Time-series cross-validation
    tscv = TimeSeriesSplit(n_splits=5)
    cv_scores = cross_val_score(pipeline, X, y, cv=tscv, scoring="accuracy")
    cv_auc = cross_val_score(pipeline, X, y, cv=tscv, scoring="roc_auc")

    # Train on full dataset for final model
    pipeline.fit(X, y)
    y_pred = pipeline.predict(X)
    y_prob = pipeline.predict_proba(X)[:, 1]

    results = {
        "name": "Logistic Regression",
        "model": pipeline,
        "cv_accuracy": cv_scores.mean(),
        "cv_accuracy_std": cv_scores.std(),
        "cv_auc": cv_auc.mean(),
        "cv_auc_std": cv_auc.std(),
        "train_accuracy": accuracy_score(y, y_pred),
        "train_auc": roc_auc_score(y, y_prob),
        "brier_score": brier_score_loss(y, y_prob),
        "log_loss": log_loss(y, y_prob),
    }

    # Feature importance (coefficients)
    coefs = pipeline.named_steps["model"].coef_[0]
    feature_importance = pd.Series(coefs, index=FEATURE_COLUMNS).abs().sort_values(ascending=False)
    results["feature_importance"] = feature_importance

    logger.info(f"   CV Accuracy: {results['cv_accuracy']:.4f} ± {results['cv_accuracy_std']:.4f}")
    logger.info(f"   CV AUC-ROC:  {results['cv_auc']:.4f} ± {results['cv_auc_std']:.4f}")
    logger.info(f"   Top 5 features: {list(feature_importance.head().index)}")

    return results


def train_xgboost(X: pd.DataFrame, y: pd.Series) -> Dict:
    """
    Train XGBoost model.

    🎓 WHAT IS XGBoost?
        Extreme Gradient Boosting. It builds an ensemble of decision trees
        sequentially — each tree corrects the errors of the previous one.

        Analogy: Imagine you're taking an exam. Tree 1 gets 60% right.
        Tree 2 focuses on the 40% Tree 1 got wrong and gets some right.
        Tree 3 focuses on what Trees 1+2 got wrong. Together, they get 85%.

    🎓 KEY HYPERPARAMETERS:
        - n_estimators: Number of trees (100-1000). More = better but slower.
        - max_depth: How deep each tree grows (3-8). Deeper = more complex.
        - learning_rate: How much each tree contributes (0.01-0.3). Lower = more trees needed.
        - subsample: % of data used per tree (0.5-1.0). Lower = less overfitting.
        - colsample_bytree: % of features per tree (0.5-1.0). Introduces diversity.

    🎓 WHY XGBoost OVER RANDOM FOREST?
        - Boosting (sequential) vs Bagging (parallel): Boosting corrects errors
        - Better handling of imbalanced data
        - Built-in regularization (L1 + L2)
        - Feature importance via gain (information-theoretic)
    """
    logger.info("🟢 Training XGBoost...")

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        gamma=0.1,             # Minimum loss reduction for split
        reg_alpha=0.1,         # L1 regularization
        reg_lambda=1.0,        # L2 regularization
        random_state=42,
        eval_metric="logloss",
        use_label_encoder=False,
        n_jobs=-1,
    )

    tscv = TimeSeriesSplit(n_splits=5)
    cv_scores = cross_val_score(model, X, y, cv=tscv, scoring="accuracy")
    cv_auc = cross_val_score(model, X, y, cv=tscv, scoring="roc_auc")

    model.fit(X, y)
    y_pred = model.predict(X)
    y_prob = model.predict_proba(X)[:, 1]

    results = {
        "name": "XGBoost",
        "model": model,
        "cv_accuracy": cv_scores.mean(),
        "cv_accuracy_std": cv_scores.std(),
        "cv_auc": cv_auc.mean(),
        "cv_auc_std": cv_auc.std(),
        "train_accuracy": accuracy_score(y, y_pred),
        "train_auc": roc_auc_score(y, y_prob),
        "brier_score": brier_score_loss(y, y_prob),
        "log_loss": log_loss(y, y_prob),
    }

    # Feature importance (gain-based)
    feature_importance = pd.Series(
        model.feature_importances_, index=FEATURE_COLUMNS
    ).sort_values(ascending=False)
    results["feature_importance"] = feature_importance

    logger.info(f"   CV Accuracy: {results['cv_accuracy']:.4f} ± {results['cv_accuracy_std']:.4f}")
    logger.info(f"   CV AUC-ROC:  {results['cv_auc']:.4f} ± {results['cv_auc_std']:.4f}")
    logger.info(f"   Top 5 features: {list(feature_importance.head().index)}")

    return results


def train_lightgbm(X: pd.DataFrame, y: pd.Series) -> Dict:
    """
    Train LightGBM model.

    🎓 WHAT IS LightGBM?
        Microsoft's gradient boosting framework. Same idea as XGBoost but:
        - Uses histogram-based splits (faster than exact splits)
        - Grows trees leaf-wise (vs. level-wise in XGBoost)
        - 10-20x faster training on large datasets
        - Better handling of categorical features

    🎓 WHEN TO USE LightGBM vs XGBoost?
        - LightGBM: Large datasets (>100K rows), many features, speed matters
        - XGBoost: Small-medium datasets, need very fine control
        - In practice: try both, ensemble if possible

    🎓 KEY DIFFERENCE — Leaf-wise vs Level-wise:
        XGBoost: Grows all leaves at each level evenly (balanced tree)
        LightGBM: Grows the leaf with the most loss reduction (asymmetric tree)
        Result: LightGBM can fit more complex patterns with fewer trees
    """
    logger.info("🟡 Training LightGBM...")

    model = lgb.LGBMClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_samples=20,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )

    tscv = TimeSeriesSplit(n_splits=5)
    cv_scores = cross_val_score(model, X, y, cv=tscv, scoring="accuracy")
    cv_auc = cross_val_score(model, X, y, cv=tscv, scoring="roc_auc")

    model.fit(X, y)
    y_pred = model.predict(X)
    y_prob = model.predict_proba(X)[:, 1]

    results = {
        "name": "LightGBM",
        "model": model,
        "cv_accuracy": cv_scores.mean(),
        "cv_accuracy_std": cv_scores.std(),
        "cv_auc": cv_auc.mean(),
        "cv_auc_std": cv_auc.std(),
        "train_accuracy": accuracy_score(y, y_pred),
        "train_auc": roc_auc_score(y, y_prob),
        "brier_score": brier_score_loss(y, y_prob),
        "log_loss": log_loss(y, y_prob),
    }

    feature_importance = pd.Series(
        model.feature_importances_, index=FEATURE_COLUMNS
    ).sort_values(ascending=False)
    results["feature_importance"] = feature_importance

    logger.info(f"   CV Accuracy: {results['cv_accuracy']:.4f} ± {results['cv_accuracy_std']:.4f}")
    logger.info(f"   CV AUC-ROC:  {results['cv_auc']:.4f} ± {results['cv_auc_std']:.4f}")
    logger.info(f"   Top 5 features: {list(feature_importance.head().index)}")

    return results


def create_ensemble(models: list, X: pd.DataFrame, y: pd.Series) -> Dict:
    """
    Create a weighted ensemble of all models.

    🎓 WHY ENSEMBLE?
        Different models capture different patterns:
        - LR finds linear relationships
        - XGBoost finds non-linear interactions
        - LightGBM finds leaf-wise patterns

        By combining them, we get a model that's more robust and accurate
        than any individual model. In Kaggle competitions, ensembles
        almost always win.

    🎓 HOW WE WEIGHT:
        We weight each model proportional to its cross-validation AUC.
        Better CV performance = higher weight in the ensemble.

        Alternative approaches:
        - Equal weighting (simple but suboptimal)
        - Stacking (train a meta-model on predictions — more complex)
        - Bayesian model averaging (theoretical but impractical)
    """
    logger.info("🟣 Creating weighted ensemble...")

    # Weight proportional to CV AUC
    total_auc = sum(m["cv_auc"] for m in models)
    weights = [m["cv_auc"] / total_auc for m in models]

    for m, w in zip(models, weights):
        logger.info(f"   {m['name']}: weight = {w:.3f} (CV AUC = {m['cv_auc']:.4f})")

    # Ensemble prediction: weighted average of probabilities
    y_probs = []
    for m in models:
        model = m["model"]
        if hasattr(model, "predict_proba"):
            y_probs.append(model.predict_proba(X)[:, 1])
        else:
            y_probs.append(model.predict(X).astype(float))

    ensemble_prob = np.average(y_probs, axis=0, weights=weights)
    ensemble_pred = (ensemble_prob >= 0.5).astype(int)

    results = {
        "name": "Ensemble",
        "weights": dict(zip([m["name"] for m in models], weights)),
        "train_accuracy": accuracy_score(y, ensemble_pred),
        "train_auc": roc_auc_score(y, ensemble_prob),
        "brier_score": brier_score_loss(y, ensemble_prob),
        "log_loss": log_loss(y, ensemble_prob),
    }

    logger.info(f"   Ensemble Accuracy: {results['train_accuracy']:.4f}")
    logger.info(f"   Ensemble AUC-ROC:  {results['train_auc']:.4f}")
    logger.info(f"   Ensemble Brier:    {results['brier_score']:.4f}")

    return results


def _validation_summary(models: list, ensemble_results: Dict, validation_X: pd.DataFrame, validation_y: pd.Series) -> Dict:
    if validation_X.empty or validation_y.empty:
        return {
            "games": 0,
            "models": {},
            "ensemble": {},
        }

    summary: Dict[str, Dict] = {"games": int(len(validation_X)), "models": {}, "ensemble": {}}
    y_true = validation_y.to_numpy()
    probs = []
    weights = []
    for model_result in models:
        model = model_result["model"]
        prob = model.predict_proba(validation_X)[:, 1]
        pred = (prob >= 0.5).astype(int)
        key = model_result["name"].lower().replace(" ", "_")
        summary["models"][key] = {
            "accuracy": round(float(accuracy_score(y_true, pred)), 4),
            "brier_score": round(float(brier_score_loss(y_true, prob)), 4),
        }
        probs.append(prob)
        weights.append(ensemble_results["weights"][model_result["name"]])

    ensemble_prob = np.average(probs, axis=0, weights=weights)
    ensemble_pred = (ensemble_prob >= 0.5).astype(int)
    summary["ensemble"] = {
        "accuracy": round(float(accuracy_score(y_true, ensemble_pred)), 4),
        "brier_score": round(float(brier_score_loss(y_true, ensemble_prob)), 4),
    }
    return summary


def run_training_pipeline(
    season: Optional[str] = "2024-25",
    *,
    cutoff_date: Optional[str] = None,
    validation_season: Optional[str] = None,
):
    """
    Run the full model training pipeline.

    🎓 PIPELINE STEPS:
        1. Load features from PostgreSQL
        2. Train Logistic Regression (baseline)
        3. Train XGBoost
        4. Train LightGBM
        5. Create weighted ensemble
        6. Save all models to disk
        7. Print comparison report

    🎓 WHY SAVE MODELS?
        In production, you train once and serve many times. We serialize
        the trained models using joblib (faster than pickle for numpy arrays).
        The FastAPI endpoint loads the saved model at startup and uses it
        for inference.
    """
    engine = get_engine()

    logger.info("=" * 60)
    logger.info("🚀 STARTING MODEL TRAINING PIPELINE")
    logger.info("=" * 60)

    # Step 1: Load data
    dataset = load_training_dataset(
        engine,
        season=season,
        cutoff_date=cutoff_date,
        validation_season=validation_season,
    )
    X = dataset["train_X"]
    y = dataset["train_y"]
    validation_X = dataset["validation_X"]
    validation_y = dataset["validation_y"]
    metadata = dict(dataset["metadata"])

    if len(X) < 50:
        logger.error("❌ Not enough data for training. Need at least 50 games.")
        return

    # Step 2: Train models
    lr_results = train_logistic_regression(X, y)
    xgb_results = train_xgboost(X, y)
    lgb_results = train_lightgbm(X, y)

    # Step 3: Ensemble
    all_models = [lr_results, xgb_results, lgb_results]
    ensemble_results = create_ensemble(all_models, X, y)
    metadata["validation_summary"] = _validation_summary(all_models, ensemble_results, validation_X, validation_y)

    # Step 4: Save models
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for model_result in all_models:
        model_name = model_result["name"].lower().replace(" ", "_")
        filepath = os.path.join(MODEL_DIR, f"{model_name}_{timestamp}.pkl")
        joblib.dump(model_result["model"], filepath)
        logger.info(f"   💾 Saved {model_result['name']} → {filepath}")

    # Save ensemble weights
    ensemble_filepath = os.path.join(MODEL_DIR, f"ensemble_weights_{timestamp}.pkl")
    joblib.dump(ensemble_results["weights"], ensemble_filepath)
    metadata_path = os.path.join(MODEL_DIR, f"training_metadata_{timestamp}.json")
    with open(metadata_path, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
    logger.info("   🧾 Saved training metadata → %s", metadata_path)

    # Step 5: Comparison report
    logger.info("\n" + "=" * 60)
    logger.info("📊 MODEL COMPARISON REPORT")
    logger.info("=" * 60)
    logger.info(f"{'Model':<25} {'CV Acc':>10} {'CV AUC':>10} {'Brier':>10}")
    logger.info("-" * 60)

    for result in all_models:
        logger.info(
            f"{result['name']:<25} "
            f"{result['cv_accuracy']:.4f}    "
            f"{result['cv_auc']:.4f}    "
            f"{result['brier_score']:.4f}"
        )

    logger.info(
        f"{'Ensemble':<25} "
        f"{'N/A':>10} "
        f"{ensemble_results['train_auc']:.4f}    "
        f"{ensemble_results['brier_score']:.4f}"
    )
    logger.info("=" * 60)

    return {
        "logistic_regression": lr_results,
        "xgboost": xgb_results,
        "lightgbm": lgb_results,
        "ensemble": ensemble_results,
        "feature_columns": FEATURE_COLUMNS,
        "metadata": metadata,
    }


if __name__ == "__main__":
    run_training_pipeline()
