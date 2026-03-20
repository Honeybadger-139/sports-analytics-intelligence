"""
Targeted tests for KL-based prediction drift detection.
"""

from src.mlops.monitoring import compute_prediction_drift


class _DummyEngine:
    pass


def test_compute_prediction_drift_returns_stable_score_for_same_windows(monkeypatch):
    monkeypatch.setattr(
        "src.mlops.monitoring._load_prediction_window",
        lambda *_args, **_kwargs: [0.2, 0.3, 0.4, 0.5],
    )

    report = compute_prediction_drift(_DummyEngine(), baseline_days=30, live_days=7, season="2025-26")

    assert report["kl_divergence"] == 0.0
    assert report["drift_detected"] is False
    assert report["baseline_mean"] == 0.35
    assert report["live_mean"] == 0.35


def test_compute_prediction_drift_flags_large_distribution_shift(monkeypatch):
    calls = []

    def _fake_window(_engine, *, season, start_days_ago, end_days_ago=None):
        calls.append((start_days_ago, end_days_ago, season))
        if end_days_ago is None:
            return [0.85, 0.9, 0.95, 0.8]
        return [0.1, 0.15, 0.2, 0.25]

    monkeypatch.setattr("src.mlops.monitoring._load_prediction_window", _fake_window)

    report = compute_prediction_drift(_DummyEngine(), baseline_days=30, live_days=7, season="2025-26")

    assert len(calls) == 2
    assert report["kl_divergence"] > 0.1
    assert report["drift_detected"] is True
    assert report["baseline_count"] == 4
    assert report["live_count"] == 4
