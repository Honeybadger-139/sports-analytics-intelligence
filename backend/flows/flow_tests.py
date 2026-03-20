"""
Focused tests for the feature-engineering data contracts.

These tests use mocked SQLAlchemy-style engines so the validation logic can be
exercised without a live database or Prefect runtime.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

import pytest

from flows.data_contracts import FEATURE_COLUMNS, FeatureContract, IngestionContract


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _FakeConnection:
    def __init__(self, responses: Iterable[tuple[str, object]]):
        self.responses = list(responses)
        self.queries: list[tuple[str, dict]] = []

    def execute(self, query, params=None):
        query_text = str(query)
        self.queries.append((query_text, params or {}))
        for needle, value in self.responses:
            if needle in query_text:
                return _FakeResult(value)
        return _FakeResult(0)


class _FakeContext:
    def __init__(self, connection: _FakeConnection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, responses: Iterable[tuple[str, object]]):
        self.connection = _FakeConnection(responses)

    def connect(self):
        return _FakeContext(self.connection)


@pytest.fixture
def ingestion_contract():
    return IngestionContract()


@pytest.fixture
def feature_contract():
    return FeatureContract()


@pytest.fixture
def good_raw_engine():
    responses = [
        ("SELECT COUNT(*) AS matches_count", 12),
        ("SELECT COUNT(*) AS team_stats_count", 24),
        ("SELECT MAX(game_date) AS max_game_date", date(2026, 3, 18)),
        ("game_date_null_count", 0),
        ("home_team_id_null_count", 0),
        ("away_team_id_null_count", 0),
        ("points_null_count", 0),
    ]
    return _FakeEngine(responses)


@pytest.fixture
def stale_raw_engine():
    responses = [
        ("SELECT COUNT(*) AS matches_count", 12),
        ("SELECT COUNT(*) AS team_stats_count", 24),
        ("SELECT MAX(game_date) AS max_game_date", date(2026, 3, 1)),
        ("game_date_null_count", 0),
        ("home_team_id_null_count", 0),
        ("away_team_id_null_count", 0),
        ("points_null_count", 0),
    ]
    return _FakeEngine(responses)


@pytest.fixture
def low_row_raw_engine():
    responses = [
        ("SELECT COUNT(*) AS matches_count", 9),
        ("SELECT COUNT(*) AS team_stats_count", 18),
        ("SELECT MAX(game_date) AS max_game_date", date(2026, 3, 18)),
        ("game_date_null_count", 0),
        ("home_team_id_null_count", 0),
        ("away_team_id_null_count", 0),
        ("points_null_count", 0),
    ]
    return _FakeEngine(responses)


@pytest.fixture
def feature_null_engine():
    responses = [
        ("SELECT COUNT(*) AS feature_rows", 24),
    ]
    for column in FEATURE_COLUMNS:
        null_count = 0
        if column == "h2h_win_pct":
            null_count = 2
        responses.append((f"{column}_null_count", null_count))
    return _FakeEngine(responses)


def test_validate_raw_data_passes_with_good_data(ingestion_contract, good_raw_engine):
    summary = ingestion_contract.validate_raw_data(
        good_raw_engine,
        ["2025-26"],
        current_date=date(2026, 3, 20),
    )

    assert summary["validation"] == "passed"
    assert summary["matches"] == 12
    assert summary["team_game_stats"] == 24
    assert summary["max_date"] == "2026-03-18"


def test_validate_raw_data_fails_with_stale_data(ingestion_contract, stale_raw_engine):
    with pytest.raises(ValueError, match="stale_game_data"):
        ingestion_contract.validate_raw_data(
            stale_raw_engine,
            ["2025-26"],
            current_date=date(2026, 3, 20),
        )


def test_validate_raw_data_fails_with_low_row_count(ingestion_contract, low_row_raw_engine):
    with pytest.raises(ValueError, match="not_enough_matches"):
        ingestion_contract.validate_raw_data(
            low_row_raw_engine,
            ["2025-26"],
            current_date=date(2026, 3, 20),
        )


def test_validate_feature_output_detects_null_columns(feature_contract, feature_null_engine):
    with pytest.raises(ValueError, match="feature_null_rate_exceeded"):
        feature_contract.validate_feature_output(
            feature_null_engine,
            ["2025-26"],
            expected_match_count=12,
        )
