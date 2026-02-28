"""
Tests for advanced team metric computation and backfill selection.
"""

import pandas as pd

from src.data import ingestion


def test_compute_advanced_team_metrics_from_game_log_row():
    row = pd.Series(
        {
            "PTS": 112,
            "PLUS_MINUS": 6,
            "FGA": 90,
            "FGM": 41,
            "FG3M": 12,
            "FTA": 22,
            "OREB": 10,
            "TOV": 14,
        }
    )

    metrics = ingestion._compute_advanced_team_metrics(row)

    # possessions = 90 - 10 + 14 + 0.44*22 = 103.68
    assert metrics["pace"] == 103.68
    assert metrics["offensive_rating"] == 108.02
    assert metrics["defensive_rating"] == 102.24
    assert metrics["effective_fg_pct"] == 0.522
    assert metrics["true_shooting_pct"] == 0.562


def test_compute_advanced_team_metrics_handles_missing_denominators():
    row = pd.Series({"PTS": 100, "FGA": 0, "FTA": 0, "FGM": 0, "FG3M": 0})
    metrics = ingestion._compute_advanced_team_metrics(row)

    assert metrics["offensive_rating"] is None
    assert metrics["defensive_rating"] is None
    assert metrics["pace"] is None
    assert metrics["effective_fg_pct"] is None
    assert metrics["true_shooting_pct"] is None


def test_load_games_missing_advanced_metrics_returns_game_id_set():
    class _Result:
        def fetchall(self):
            return [("001",), ("002",)]

    class _Conn:
        def execute(self, _query, _params=None):
            return _Result()

    class _Ctx:
        def __enter__(self):
            return _Conn()

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Engine:
        def connect(self):
            return _Ctx()

    game_ids = ingestion._load_games_missing_advanced_metrics(_Engine(), "2025-26")
    assert game_ids == {"001", "002"}


def test_load_games_missing_advanced_metrics_handles_empty_result():
    class _Result:
        def fetchall(self):
            return []

    class _Conn:
        def execute(self, _query, _params=None):
            return _Result()

    class _Ctx:
        def __enter__(self):
            return _Conn()

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Engine:
        def connect(self):
            return _Ctx()

    game_ids = ingestion._load_games_missing_advanced_metrics(_Engine(), "2025-26")
    assert game_ids == set()


def test_backfill_defensive_rating_executes_update_with_season_param():
    executed = {}

    class _Conn:
        def execute(self, query, params=None):
            executed["query"] = str(query)
            executed["params"] = params

    class _Ctx:
        def __enter__(self):
            return _Conn()

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Engine:
        def begin(self):
            return _Ctx()

    ingestion._backfill_defensive_rating_from_opponent_points(_Engine(), "2025-26")
    assert "UPDATE team_game_stats" in executed["query"]
    assert "defensive_rating" in executed["query"]
    assert executed["params"] == {"season": "2025-26"}
