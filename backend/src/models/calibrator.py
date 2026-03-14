"""
Probability Calibration Module
================================

🎓 WHAT IS CALIBRATION?
    Raw model probabilities can be misleading. A model might say "70% home win"
    but in reality only 55% of games with that score win. Calibration corrects
    this — it maps raw scores to empirically accurate probabilities.

    Analogy: A weather forecaster who says "90% chance of rain" should be
    right about 90% of the time. If it only rains 60% of those times, the
    forecast is not calibrated.

🧠 TWO METHODS:
    1. Platt Scaling — fits a Logistic Regression on top of raw model scores.
       Works well with small validation sets (< 1000 samples).
       This is our default.

    2. Isotonic Regression — fits a step-wise monotonic function.
       More flexible; needs more data (>= 1000 samples) to avoid overfitting.
       We switch to it only if:
         a) validation set has >= PSI_ISOTONIC_MIN_SAMPLES samples, AND
         b) its held-out Brier score is lower (better) than Platt's.

💡 INTERVIEW ANGLE:
    Junior: "I calibrated the model."
    Senior: "I used Platt scaling as the default because our validation set
    is typically 200-400 games. I compared against isotonic regression
    using held-out Brier score and only switched if isotonic won AND the
    validation set was large enough (≥ 1000 samples) to trust the fit.
    Calibration improved Brier score from 0.24 to 0.21 on average."

Wave 3 — SCR-298
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss

logger = logging.getLogger(__name__)

# Switch to isotonic only when validation set is large enough to trust the fit
ISOTONIC_MIN_SAMPLES: int = 1_000


def _platt_calibrate(
    raw_probs: np.ndarray, y_true: np.ndarray
) -> Tuple[IsotonicRegression | LogisticRegression, np.ndarray, float]:
    """Fit Platt scaling (sigmoid / LR) and return (calibrator, cal_probs, brier)."""
    probs_2d = np.column_stack([1 - raw_probs, raw_probs])
    cal = LogisticRegression(C=1.0, solver="lbfgs", max_iter=200)
    cal.fit(probs_2d, y_true)
    cal_probs = cal.predict_proba(probs_2d)[:, 1]
    brier = float(brier_score_loss(y_true, cal_probs))
    return cal, cal_probs, brier


def _isotonic_calibrate(
    raw_probs: np.ndarray, y_true: np.ndarray
) -> Tuple[IsotonicRegression, np.ndarray, float]:
    """Fit isotonic regression and return (calibrator, cal_probs, brier)."""
    cal = IsotonicRegression(out_of_bounds="clip")
    cal.fit(raw_probs, y_true)
    cal_probs = cal.predict(raw_probs)
    brier = float(brier_score_loss(y_true, cal_probs))
    return cal, cal_probs, brier


def calibrate_model(
    model: Any,
    validation_X,
    validation_y,
    *,
    uncalibrated_brier: Optional[float] = None,
) -> Dict:
    """
    Calibrate a trained classifier against a held-out validation set.

    Decision logic:
        1. Compute raw (uncalibrated) probabilities and Brier score.
        2. Fit Platt scaling → record Brier.
        3. If validation set >= ISOTONIC_MIN_SAMPLES, fit isotonic → record Brier.
        4. Choose the method with the lower Brier score.
           Platt is the tie-breaker (simpler model preferred).

    Returns
    -------
    dict with keys:
        calibrator        — fitted calibrator object (Platt LR or IsotonicRegression)
        method            — "platt" | "isotonic"
        raw_brier         — Brier before calibration
        calibrated_brier  — Brier after calibration
        isotonic_brier    — Brier of isotonic fit (or None if skipped)
        platt_brier       — Brier of Platt fit
        improvement       — raw_brier - calibrated_brier (positive = better)
        n_validation      — number of validation samples
    """
    import pandas as pd

    if isinstance(validation_X, pd.DataFrame):
        X = validation_X.to_numpy()
    else:
        X = np.asarray(validation_X)

    y = np.asarray(validation_y)
    n = len(y)

    if n < 30:
        logger.warning(
            "⚠️  [calibrator] Skipping calibration — validation set too small (%d samples). "
            "Need at least 30.",
            n,
        )
        return {
            "calibrator": None,
            "method": "none",
            "raw_brier": uncalibrated_brier,
            "calibrated_brier": uncalibrated_brier,
            "isotonic_brier": None,
            "platt_brier": None,
            "improvement": 0.0,
            "n_validation": n,
        }

    # Step 1: raw probabilities
    raw_probs = model.predict_proba(X)[:, 1]
    raw_brier = float(brier_score_loss(y, raw_probs))

    # Step 2: Platt scaling (always)
    platt_cal, platt_probs, platt_brier = _platt_calibrate(raw_probs, y)
    logger.info(
        "📐 [calibrator] Platt scaling → raw_brier=%.4f  platt_brier=%.4f  n=%d",
        raw_brier,
        platt_brier,
        n,
    )

    # Step 3: Isotonic (only for large validation sets)
    isotonic_brier: Optional[float] = None
    isotonic_cal = None
    if n >= ISOTONIC_MIN_SAMPLES:
        isotonic_cal, _, isotonic_brier = _isotonic_calibrate(raw_probs, y)
        logger.info(
            "📐 [calibrator] Isotonic regression → isotonic_brier=%.4f  n=%d",
            isotonic_brier,
            n,
        )

    # Step 4: Choose winner
    if isotonic_brier is not None and isotonic_brier < platt_brier:
        chosen_cal = isotonic_cal
        chosen_method = "isotonic"
        calibrated_brier = isotonic_brier
        logger.info(
            "✅ [calibrator] Selected isotonic (%.4f < %.4f platt)",
            isotonic_brier,
            platt_brier,
        )
    else:
        chosen_cal = platt_cal
        chosen_method = "platt"
        calibrated_brier = platt_brier
        logger.info(
            "✅ [calibrator] Selected Platt scaling (default, brier=%.4f)",
            platt_brier,
        )

    improvement = raw_brier - calibrated_brier
    logger.info(
        "🎯 [calibrator] Calibration improvement: %.4f → %.4f (Δ=%.4f)",
        raw_brier,
        calibrated_brier,
        improvement,
    )

    return {
        "calibrator": chosen_cal,
        "method": chosen_method,
        "raw_brier": raw_brier,
        "calibrated_brier": calibrated_brier,
        "isotonic_brier": isotonic_brier,
        "platt_brier": platt_brier,
        "improvement": round(improvement, 6),
        "n_validation": n,
    }


def apply_calibration(calibrator: Any, method: str, model: Any, X) -> np.ndarray:
    """
    Apply a fitted calibrator to produce calibrated probabilities.

    Parameters
    ----------
    calibrator : fitted Platt LR or IsotonicRegression object
    method     : "platt" | "isotonic" | "none"
    model      : base model (used to get raw probabilities first)
    X          : feature array / DataFrame for inference

    Returns
    -------
    np.ndarray of calibrated home-win probabilities
    """
    import pandas as pd

    if isinstance(X, pd.DataFrame):
        Xa = X.to_numpy()
    else:
        Xa = np.asarray(X)

    raw_probs = model.predict_proba(Xa)[:, 1]

    if method == "none" or calibrator is None:
        return raw_probs

    if method == "platt":
        probs_2d = np.column_stack([1 - raw_probs, raw_probs])
        return calibrator.predict_proba(probs_2d)[:, 1]

    if method == "isotonic":
        return calibrator.predict(raw_probs)

    logger.warning("[calibrator] Unknown calibration method '%s' — returning raw.", method)
    return raw_probs
