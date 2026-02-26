"""
Shared test fixtures for the Sports Analytics test suite.
"""
import pytest


@pytest.fixture
def sample_kelly_inputs():
    """Common inputs for Kelly Criterion tests."""
    return {
        "high_edge": {"model_prob": 0.65, "decimal_odds": 2.0, "kelly_fraction": 0.25},
        "no_edge": {"model_prob": 0.45, "decimal_odds": 2.0, "kelly_fraction": 0.25},
        "negative_ev": {"model_prob": 0.30, "decimal_odds": 2.0, "kelly_fraction": 0.25},
        "huge_edge": {"model_prob": 0.90, "decimal_odds": 3.0, "kelly_fraction": 0.25},
    }


@pytest.fixture
def sample_features():
    """Sample feature row for prediction tests."""
    import pandas as pd
    return pd.DataFrame([{
        "win_pct_last_5": 0.600,
        "win_pct_last_10": 0.700,
        "avg_point_diff_last_5": 5.2,
        "avg_point_diff_last_10": 4.8,
        "is_home": 1,
        "days_rest": 2,
        "is_back_to_back": 0,
        "avg_off_rating_last_5": 112.5,
        "avg_def_rating_last_5": 108.3,
        "avg_pace_last_5": 100.2,
        "avg_efg_last_5": 0.545,
        "h2h_win_pct": 0.600,
        "h2h_avg_margin": 3.5,
        "current_streak": 3,
        "opp_win_pct_last_5": 0.400,
        "opp_win_pct_last_10": 0.500,
        "opp_avg_point_diff_last_5": -2.1,
        "opp_avg_point_diff_last_10": -1.5,
        "opp_days_rest": 1,
        "opp_is_back_to_back": 1,
        "opp_avg_off_rating_last_5": 108.1,
        "opp_avg_def_rating_last_5": 112.4,
        "opp_avg_pace_last_5": 98.7,
        "opp_avg_efg_last_5": 0.490,
    }])
