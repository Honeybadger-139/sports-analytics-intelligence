"""
Tests for Wave 3 Artifact Store
=================================
Tests: dated filenames, keep-3 retention, purge logic, active_model_dir fallback.
"""

import os
import glob
import tempfile
import pytest
import joblib

from src.models.artifact_store import (
    ARTIFACT_RETENTION_COUNT,
    save_artifact,
    purge_old_artifacts,
    save_all_artifacts,
    load_latest_artifact,
    get_active_model_dir,
    set_active_model_dir,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tmp_dir():
    return tempfile.mkdtemp(prefix="test_artifacts_")


def _dummy_model(value=42):
    """Lightweight serializable object for artifact tests."""
    return {"dummy": value}


# ── save_artifact ─────────────────────────────────────────────────────────────

class TestSaveArtifact:
    def test_creates_file_with_timestamp_in_name(self):
        d = _tmp_dir()
        path = save_artifact(_dummy_model(), "xgboost", d, "20260314_120000")
        assert os.path.exists(path)
        assert "xgboost_20260314_120000.pkl" in path

    def test_artifact_can_be_loaded(self):
        d = _tmp_dir()
        obj = {"weights": [0.4, 0.3, 0.3]}
        path = save_artifact(obj, "ensemble_weights", d, "20260314_130000")
        loaded = joblib.load(path)
        assert loaded == obj


# ── purge_old_artifacts ───────────────────────────────────────────────────────

class TestPurgeOldArtifacts:
    def test_keeps_newest_n_artifacts(self):
        d = _tmp_dir()
        # Create 5 artifacts for the same model_name
        timestamps = [f"2026031{i}_100000" for i in range(1, 6)]
        for ts in timestamps:
            save_artifact(_dummy_model(), "logistic_regression", d, ts)

        deleted = purge_old_artifacts("logistic_regression", d, keep=ARTIFACT_RETENTION_COUNT)
        remaining = glob.glob(os.path.join(d, "logistic_regression_*.pkl"))
        assert len(remaining) == ARTIFACT_RETENTION_COUNT
        assert len(deleted) == 5 - ARTIFACT_RETENTION_COUNT

    def test_no_delete_when_at_or_below_limit(self):
        d = _tmp_dir()
        for ts in ["20260301_100000", "20260302_100000"]:
            save_artifact(_dummy_model(), "xgboost", d, ts)

        deleted = purge_old_artifacts("xgboost", d, keep=3)
        assert deleted == []

    def test_keeps_chronologically_newest(self):
        d = _tmp_dir()
        # Lexicographic sort of YYYYMMDD_HHMMSS ensures newest = alphabetically last
        for ts in ["20260301_100000", "20260302_100000", "20260303_100000", "20260304_100000"]:
            save_artifact(_dummy_model(value=int(ts[:8])), "lightgbm", d, ts)

        purge_old_artifacts("lightgbm", d, keep=2)
        remaining = glob.glob(os.path.join(d, "lightgbm_*.pkl"))
        remaining_names = sorted(os.path.basename(p) for p in remaining)
        # Should keep the two newest: 20260303 and 20260304
        assert "lightgbm_20260303_100000.pkl" in remaining_names
        assert "lightgbm_20260304_100000.pkl" in remaining_names
        assert "lightgbm_20260301_100000.pkl" not in remaining_names


# ── save_all_artifacts ────────────────────────────────────────────────────────

class TestSaveAllArtifacts:
    def _fake_training_output(self):
        from sklearn.linear_model import LogisticRegression
        import numpy as np
        X = np.random.randn(50, 3)
        y = (X[:, 0] > 0).astype(int)
        lr = LogisticRegression(max_iter=50).fit(X, y)
        return {
            "logistic_regression": {"model": lr},
            "xgboost": {"model": lr},       # reuse LR for test simplicity
            "lightgbm": {"model": lr},
            "ensemble": {"weights": {"Logistic Regression": 0.33, "XGBoost": 0.33, "LightGBM": 0.34}},
        }

    def test_all_artifacts_saved(self):
        d = _tmp_dir()
        output = self._fake_training_output()
        paths = save_all_artifacts(output, d, timestamp="20260314_150000")
        assert "logistic_regression" in paths
        assert "xgboost" in paths
        assert "lightgbm" in paths
        assert "ensemble_weights" in paths
        for path in paths.values():
            assert os.path.exists(path)

    def test_retention_enforced_across_runs(self):
        d = _tmp_dir()
        output = self._fake_training_output()
        # Run 4 times → should only keep 3
        for i in range(1, 5):
            ts = f"20260314_1{i}0000"
            save_all_artifacts(output, d, timestamp=ts)

        lr_files = glob.glob(os.path.join(d, "logistic_regression_*.pkl"))
        assert len(lr_files) == ARTIFACT_RETENTION_COUNT


# ── load_latest_artifact ──────────────────────────────────────────────────────

class TestLoadLatestArtifact:
    def test_loads_most_recent_file(self):
        d = _tmp_dir()
        save_artifact({"v": 1}, "xgboost", d, "20260301_100000")
        save_artifact({"v": 2}, "xgboost", d, "20260302_100000")
        loaded = load_latest_artifact("xgboost", d)
        assert loaded == {"v": 2}

    def test_returns_none_when_no_file(self):
        d = _tmp_dir()
        result = load_latest_artifact("nonexistent_model", d)
        assert result is None


# ── get_active_model_dir ──────────────────────────────────────────────────────

class TestGetActiveModelDir:
    def test_falls_back_to_default_when_db_unavailable(self):
        class FakeEngine:
            def connect(self):
                raise RuntimeError("DB unreachable")

        result = get_active_model_dir(FakeEngine(), "/default/path")
        assert result == "/default/path"

    def test_falls_back_when_configured_dir_does_not_exist(self):
        from unittest.mock import MagicMock, patch
        import sqlalchemy as sa

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = ("/nonexistent/dir",)
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__ = lambda s: mock_conn
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        result = get_active_model_dir(mock_engine, "/fallback")
        assert result == "/fallback"
