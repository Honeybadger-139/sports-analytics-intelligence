"""
Tests for Wave 3 Probability Calibration
==========================================
Tests: Platt scaling, isotonic selection logic, Brier improvement,
       apply_calibration routing, small-set skip guard.
"""

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression

from src.models.calibrator import (
    ISOTONIC_MIN_SAMPLES,
    calibrate_model,
    apply_calibration,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_fake_model(n_features: int = 5):
    """Logistic Regression fitted on random data — just needs predict_proba."""
    rng = np.random.default_rng(42)
    X = rng.standard_normal((200, n_features))
    y = (X[:, 0] > 0).astype(int)
    model = LogisticRegression(max_iter=200)
    model.fit(X, y)
    return model, X, y


# ── calibrate_model ───────────────────────────────────────────────────────────

class TestCalibrateModel:
    def test_platt_selected_for_small_validation(self):
        """Platt scaling should be selected when n < ISOTONIC_MIN_SAMPLES."""
        model, X, y = _make_fake_model()
        # Use a small validation set (50 samples)
        val_X = X[:50]
        val_y = y[:50]
        result = calibrate_model(model, val_X, val_y)

        assert result["method"] == "platt"
        assert result["isotonic_brier"] is None  # not attempted
        assert result["n_validation"] == 50

    def test_returns_none_calibrator_for_tiny_validation(self):
        """If validation set < 30, calibration should be skipped."""
        model, X, y = _make_fake_model()
        result = calibrate_model(model, X[:20], y[:20])

        assert result["method"] == "none"
        assert result["calibrator"] is None
        assert result["improvement"] == 0.0

    def test_calibrated_brier_is_finite(self):
        """calibrated_brier must be a finite float."""
        model, X, y = _make_fake_model()
        result = calibrate_model(model, X[:100], y[:100])

        assert result["calibrated_brier"] is not None
        assert np.isfinite(result["calibrated_brier"])

    def test_raw_brier_is_computed(self):
        """raw_brier should differ from zero when model is not perfect."""
        model, X, y = _make_fake_model()
        result = calibrate_model(model, X[:100], y[:100])

        assert result["raw_brier"] is not None
        assert result["raw_brier"] > 0.0

    def test_platt_calibrator_is_logistic_regression(self):
        """Platt calibrator must be a LogisticRegression instance."""
        model, X, y = _make_fake_model()
        result = calibrate_model(model, X[:100], y[:100])

        if result["method"] == "platt":
            assert isinstance(result["calibrator"], LogisticRegression)

    def test_isotonic_selected_when_large_and_better(self, monkeypatch):
        """
        When validation set >= ISOTONIC_MIN_SAMPLES AND isotonic Brier < Platt Brier,
        isotonic should be selected.
        """
        import src.models.calibrator as cal_mod

        model, X, y = _make_fake_model()

        # Patch _isotonic_calibrate to always return a better Brier than Platt
        original_platt = cal_mod._platt_calibrate
        original_isotonic = cal_mod._isotonic_calibrate

        def fake_platt(raw_probs, y_true):
            cal = LogisticRegression(max_iter=1)
            cal.fit(raw_probs.reshape(-1, 1), y_true)
            return cal, raw_probs, 0.30  # fixed Brier = 0.30

        iso_reg = IsotonicRegression(out_of_bounds="clip")

        def fake_isotonic(raw_probs, y_true):
            iso_reg.fit(raw_probs, y_true)
            return iso_reg, iso_reg.predict(raw_probs), 0.20  # better Brier = 0.20

        monkeypatch.setattr(cal_mod, "_platt_calibrate", fake_platt)
        monkeypatch.setattr(cal_mod, "_isotonic_calibrate", fake_isotonic)

        # Create a large validation set to trigger isotonic attempt
        rng = np.random.default_rng(99)
        big_X = rng.standard_normal((ISOTONIC_MIN_SAMPLES + 50, 5))
        big_y = (big_X[:, 0] > 0).astype(int)
        refitted_model, _, _ = _make_fake_model()

        result = calibrate_model(refitted_model, big_X, big_y)
        assert result["method"] == "isotonic"
        assert result["calibrated_brier"] == 0.20
        assert result["platt_brier"] == 0.30


# ── apply_calibration ─────────────────────────────────────────────────────────

class TestApplyCalibration:
    def test_none_method_returns_raw_probs(self):
        """When method='none', raw probabilities should pass through."""
        model, X, y = _make_fake_model()
        raw = model.predict_proba(X[:10])[:, 1]
        result = apply_calibration(None, "none", model, X[:10])
        np.testing.assert_array_almost_equal(result, raw, decimal=6)

    def test_platt_method_returns_calibrated(self):
        """Platt calibration should return probabilities in [0, 1]."""
        model, X, y = _make_fake_model()
        cal_result = calibrate_model(model, X[:100], y[:100])

        if cal_result["method"] == "platt" and cal_result["calibrator"] is not None:
            probs = apply_calibration(cal_result["calibrator"], "platt", model, X[:10])
            assert probs.shape == (10,)
            assert (probs >= 0).all() and (probs <= 1).all()

    def test_isotonic_method_returns_calibrated(self):
        """Isotonic calibration should return probabilities in [0, 1]."""
        model, X, y = _make_fake_model()
        raw_probs = model.predict_proba(X[:100])[:, 1]

        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(raw_probs, y[:100])

        result = apply_calibration(iso, "isotonic", model, X[:10])
        assert (result >= 0).all() and (result <= 1).all()

    def test_unknown_method_falls_back_to_raw(self):
        """Unknown method string should return raw probabilities with a warning."""
        model, X, y = _make_fake_model()
        raw = model.predict_proba(X[:5])[:, 1]
        result = apply_calibration(None, "unknown_method", model, X[:5])
        np.testing.assert_array_almost_equal(result, raw, decimal=6)
