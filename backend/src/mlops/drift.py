"""
PSI Feature Drift Detection
============================

🎓 WHAT IS PSI?
    Population Stability Index measures how much a feature's distribution
    has shifted between a reference period (training data) and the current
    production population (recent inference window).

    Formula:
        PSI = Σ (actual% - expected%) × ln(actual% / expected%)

    Interpretation:
        PSI < 0.10  → No significant drift (model stable)
        PSI < 0.20  → Moderate drift (monitor closely)
        PSI ≥ 0.20  → Significant drift (consider retraining)

    Analogy: If your training data had 60% home-advantage games but
    production now sees 30%, your model's probability estimates for
    home teams will be systematically biased.

🧠 WHY PSI AND NOT JUST ACCURACY?
    Accuracy monitoring is lagged — you only know after the game result.
    PSI is a leading indicator: it fires before accuracy degrades.

    Best practice: monitor both. PSI → early warning. Accuracy drop →
    confirmation that retraining is needed.

💡 INTERVIEW ANGLE:
    Junior: "I check if accuracy drops."
    Senior: "I run PSI drift detection on the top 5 model features at
    inference time. PSI fires 2-4 weeks before accuracy starts degrading
    because feature distributions shift before the model's predictions
    become wrong. This gives the team time to queue a retrain before
    users notice prediction quality issues."

Wave 3 — SCR-298
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Default PSI significance threshold (can be overridden via app_config)
PSI_SIGNIFICANT_THRESHOLD: float = 0.20
PSI_WARNING_THRESHOLD: float = 0.10

# Number of bins for continuous feature discretization
PSI_N_BINS: int = 10

# Clipping epsilon to avoid division by zero / log(0)
_EPS: float = 1e-6


def _compute_psi_for_feature(
    reference: np.ndarray,
    current: np.ndarray,
    n_bins: int = PSI_N_BINS,
) -> float:
    """
    Compute PSI for a single continuous feature.

    Parameters
    ----------
    reference : 1-D array of training-time feature values
    current   : 1-D array of recent inference-time feature values
    n_bins    : number of equal-width bins (computed from reference distribution)

    Returns
    -------
    PSI score (float ≥ 0)
    """
    reference = np.asarray(reference, dtype=float)
    current = np.asarray(current, dtype=float)

    # Compute bin edges from reference
    min_val = reference.min()
    max_val = reference.max()
    if min_val == max_val:
        return 0.0  # No variation → no drift possible

    bins = np.linspace(min_val, max_val, n_bins + 1)
    bins[0] = -np.inf
    bins[-1] = np.inf

    ref_counts, _ = np.histogram(reference, bins=bins)
    cur_counts, _ = np.histogram(current, bins=bins)

    ref_pct = ref_counts / max(len(reference), 1)
    cur_pct = cur_counts / max(len(current), 1)

    # Clip to avoid division by zero and log(0)
    ref_pct = np.clip(ref_pct, _EPS, None)
    cur_pct = np.clip(cur_pct, _EPS, None)

    psi = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
    return round(psi, 6)


def compute_psi_report(
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    feature_columns: List[str],
    *,
    n_bins: int = PSI_N_BINS,
    top_n: int = 5,
) -> Dict:
    """
    Compute PSI for each feature and summarise drift.

    Parameters
    ----------
    reference_df     : DataFrame of training feature values
    current_df       : DataFrame of recent inference feature values
    feature_columns  : list of feature column names to evaluate
    n_bins           : histogram bins for PSI computation
    top_n            : number of top features to include in drift_features

    Returns
    -------
    dict:
        psi_per_feature : dict[feature_name → psi_score]
        drift_features  : list of features with PSI ≥ WARNING threshold, sorted desc
        max_psi         : highest PSI across all features
        mean_psi        : average PSI
        status          : "stable" | "warning" | "significant"
        n_reference     : reference sample count
        n_current       : current sample count
    """
    psi_scores: Dict[str, float] = {}

    for col in feature_columns:
        if col not in reference_df.columns or col not in current_df.columns:
            logger.debug("[drift] Skipping column not in both DataFrames: %s", col)
            continue
        ref_vals = reference_df[col].dropna().to_numpy()
        cur_vals = current_df[col].dropna().to_numpy()
        if len(ref_vals) == 0 or len(cur_vals) == 0:
            psi_scores[col] = 0.0
            continue
        psi_scores[col] = _compute_psi_for_feature(ref_vals, cur_vals, n_bins=n_bins)

    if not psi_scores:
        return {
            "psi_per_feature": {},
            "drift_features": [],
            "max_psi": 0.0,
            "mean_psi": 0.0,
            "status": "stable",
            "n_reference": len(reference_df),
            "n_current": len(current_df),
        }

    max_psi = max(psi_scores.values())
    mean_psi = float(np.mean(list(psi_scores.values())))

    # Status
    if max_psi >= PSI_SIGNIFICANT_THRESHOLD:
        status = "significant"
    elif max_psi >= PSI_WARNING_THRESHOLD:
        status = "warning"
    else:
        status = "stable"

    # Drifted features (≥ warning threshold), sorted by PSI descending
    drift_features = [
        {"feature": k, "psi": v}
        for k, v in sorted(psi_scores.items(), key=lambda x: x[1], reverse=True)
        if v >= PSI_WARNING_THRESHOLD
    ][:top_n]

    logger.info(
        "📊 [drift] PSI report | status=%s max_psi=%.4f mean_psi=%.4f n_ref=%d n_cur=%d",
        status,
        max_psi,
        mean_psi,
        len(reference_df),
        len(current_df),
    )
    if drift_features:
        logger.warning(
            "⚠️  [drift] Drifted features (≥ %.2f): %s",
            PSI_WARNING_THRESHOLD,
            [(d["feature"], d["psi"]) for d in drift_features],
        )

    return {
        "psi_per_feature": psi_scores,
        "drift_features": drift_features,
        "max_psi": round(max_psi, 6),
        "mean_psi": round(mean_psi, 6),
        "status": status,
        "n_reference": len(reference_df),
        "n_current": len(current_df),
    }


def load_reference_distribution(engine, feature_columns: List[str], season: str) -> pd.DataFrame:
    """
    Load training-period feature values from match_features for a given season.
    Used as the reference distribution for PSI computation.
    """
    from sqlalchemy import text

    cols_sql = ", ".join(f"mf.{c}" for c in feature_columns if c != "is_home" and c != "is_back_to_back")
    # is_home and is_back_to_back are boolean — cast to int for PSI
    query = text(f"""
        SELECT
            {cols_sql},
            CASE WHEN mf.is_home THEN 1 ELSE 0 END AS is_home,
            CASE WHEN mf.is_back_to_back THEN 1 ELSE 0 END AS is_back_to_back
        FROM match_features mf
        JOIN matches m ON mf.game_id = m.game_id
        WHERE m.season = :season
          AND m.is_completed = TRUE
        ORDER BY m.game_date ASC
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"season": season})
    logger.info("[drift] Loaded %d reference rows for season %s", len(df), season)
    return df[feature_columns] if set(feature_columns).issubset(df.columns) else df


def load_recent_distribution(
    engine, feature_columns: List[str], *, recent_n: int = 100
) -> pd.DataFrame:
    """
    Load the most recent N feature rows from match_features regardless of season.
    Used as the current distribution for PSI computation.
    """
    from sqlalchemy import text

    cols_sql = ", ".join(f"mf.{c}" for c in feature_columns if c != "is_home" and c != "is_back_to_back")
    query = text(f"""
        SELECT
            {cols_sql},
            CASE WHEN mf.is_home THEN 1 ELSE 0 END AS is_home,
            CASE WHEN mf.is_back_to_back THEN 1 ELSE 0 END AS is_back_to_back
        FROM match_features mf
        JOIN matches m ON mf.game_id = m.game_id
        ORDER BY m.game_date DESC
        LIMIT :n
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"n": recent_n})
    logger.info("[drift] Loaded %d recent rows for drift comparison", len(df))
    return df[feature_columns] if set(feature_columns).issubset(df.columns) else df
