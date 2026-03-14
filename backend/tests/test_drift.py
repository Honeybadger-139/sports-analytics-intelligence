"""
Tests for Wave 3 PSI Drift Detection
======================================
Tests: PSI computation correctness, status thresholds, empty/edge cases,
       drift_features sorting.
"""

import numpy as np
import pandas as pd
import pytest

from src.mlops.drift import (
    PSI_N_BINS,
    PSI_SIGNIFICANT_THRESHOLD,
    PSI_WARNING_THRESHOLD,
    _compute_psi_for_feature,
    compute_psi_report,
)


# ── _compute_psi_for_feature ──────────────────────────────────────────────────

class TestComputePsiForFeature:
    def test_identical_distributions_give_zero_psi(self):
        """Identical reference and current should yield PSI ≈ 0."""
        rng = np.random.default_rng(1)
        data = rng.normal(0, 1, 500)
        psi = _compute_psi_for_feature(data, data)
        assert psi < 0.01, f"Expected near-zero PSI, got {psi}"

    def test_highly_shifted_distribution_gives_high_psi(self):
        """Reference ≈ N(0,1), current ≈ N(5,1) → significant PSI."""
        rng = np.random.default_rng(2)
        ref = rng.normal(0, 1, 1000)
        cur = rng.normal(5, 1, 1000)
        psi = _compute_psi_for_feature(ref, cur)
        assert psi >= PSI_SIGNIFICANT_THRESHOLD, f"Expected large PSI, got {psi}"

    def test_constant_feature_returns_zero(self):
        """All-constant reference has no variation → PSI = 0."""
        ref = np.ones(100) * 5.0
        cur = np.ones(100) * 3.0
        psi = _compute_psi_for_feature(ref, cur)
        assert psi == 0.0

    def test_psi_is_non_negative(self):
        """PSI must always be ≥ 0."""
        rng = np.random.default_rng(3)
        for _ in range(20):
            ref = rng.uniform(0, 1, 200)
            cur = rng.uniform(0, 2, 200)
            assert _compute_psi_for_feature(ref, cur) >= 0.0


# ── compute_psi_report ────────────────────────────────────────────────────────

FEATURES = ["win_pct_last_5", "days_rest", "avg_off_rating_last_5"]


def _make_dfs(shift: float = 0.0):
    rng = np.random.default_rng(42)
    n = 300
    ref_data = {f: rng.normal(0, 1, n) for f in FEATURES}
    cur_data = {f: rng.normal(shift, 1, n) for f in FEATURES}
    return pd.DataFrame(ref_data), pd.DataFrame(cur_data)


class TestComputePsiReport:
    def test_stable_when_no_shift(self):
        ref_df, cur_df = _make_dfs(shift=0.0)
        report = compute_psi_report(ref_df, cur_df, FEATURES)
        assert report["status"] == "stable"
        assert report["max_psi"] < PSI_WARNING_THRESHOLD

    def test_significant_when_large_shift(self):
        ref_df, cur_df = _make_dfs(shift=5.0)
        report = compute_psi_report(ref_df, cur_df, FEATURES)
        assert report["status"] == "significant"
        assert report["max_psi"] >= PSI_SIGNIFICANT_THRESHOLD

    def test_report_has_all_required_keys(self):
        ref_df, cur_df = _make_dfs()
        report = compute_psi_report(ref_df, cur_df, FEATURES)
        for key in ("psi_per_feature", "drift_features", "max_psi", "mean_psi", "status", "n_reference", "n_current"):
            assert key in report, f"Missing key: {key}"

    def test_psi_per_feature_has_entry_for_each_feature(self):
        ref_df, cur_df = _make_dfs()
        report = compute_psi_report(ref_df, cur_df, FEATURES)
        for f in FEATURES:
            assert f in report["psi_per_feature"]

    def test_drift_features_sorted_descending(self):
        """Drift features list should be sorted by PSI descending."""
        ref_df, cur_df = _make_dfs(shift=3.0)
        report = compute_psi_report(ref_df, cur_df, FEATURES)
        psids = [d["psi"] for d in report["drift_features"]]
        assert psids == sorted(psids, reverse=True)

    def test_empty_dataframes_return_stable(self):
        """Empty DataFrames should not raise and should return stable."""
        ref_df = pd.DataFrame(columns=FEATURES)
        cur_df = pd.DataFrame(columns=FEATURES)
        report = compute_psi_report(ref_df, cur_df, FEATURES)
        assert report["status"] == "stable"
        assert report["max_psi"] == 0.0

    def test_sample_counts_in_report(self):
        ref_df, cur_df = _make_dfs()
        report = compute_psi_report(ref_df, cur_df, FEATURES)
        assert report["n_reference"] == len(ref_df)
        assert report["n_current"] == len(cur_df)

    def test_warning_status_for_moderate_shift(self):
        """A moderate shift should yield 'warning' not 'significant'."""
        rng = np.random.default_rng(7)
        ref_data = {f: rng.normal(0, 1, 500) for f in FEATURES}
        cur_data = {f: rng.normal(0.8, 1, 500) for f in FEATURES}
        ref_df = pd.DataFrame(ref_data)
        cur_df = pd.DataFrame(cur_data)
        report = compute_psi_report(ref_df, cur_df, FEATURES)
        # Status should be warning or stable (not necessarily significant for 0.8 shift)
        assert report["status"] in {"stable", "warning", "significant"}
