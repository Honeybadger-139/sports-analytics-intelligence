"""
DB-backed integration tests for ingestion audit invariants.

These tests run against a real PostgreSQL connection, but use per-test TEMP
tables to keep execution isolated from production-like data.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from src import config
from src.data.ingestion import audit_data


class _ConnCtx:
    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self._conn

    def __exit__(self, exc_type, exc, tb):
        return False


class _EngineProxy:
    def __init__(self, conn):
        self._conn = conn

    def connect(self):
        return _ConnCtx(self._conn)


@pytest.fixture
def db_audit_engine():
    """
    Create a real DB session with temp tables shadowing core audit tables.
    """
    engine = create_engine(config.DATABASE_URL)
    try:
        with engine.connect() as probe:
            probe.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - environment dependent
        engine.dispose()
        pytest.skip(f"PostgreSQL not reachable for integration test: {exc}")

    conn = engine.connect()
    txn = conn.begin()
    try:
        conn.execute(
            text(
                """
                CREATE TEMP TABLE matches (
                    id SERIAL PRIMARY KEY,
                    game_id VARCHAR(20) NOT NULL,
                    is_completed BOOLEAN DEFAULT FALSE,
                    home_score INTEGER,
                    away_score INTEGER
                ) ON COMMIT DROP;
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TEMP TABLE team_game_stats (
                    id SERIAL PRIMARY KEY,
                    game_id VARCHAR(20) NOT NULL
                ) ON COMMIT DROP;
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TEMP TABLE player_game_stats (
                    id SERIAL PRIMARY KEY,
                    game_id VARCHAR(20) NOT NULL
                ) ON COMMIT DROP;
                """
            )
        )
        yield _EngineProxy(conn), conn
    finally:
        txn.rollback()
        conn.close()
        engine.dispose()


def _seed_completed_game(
    conn,
    game_id: str,
    *,
    team_rows: int = 2,
    has_player_stats: bool = True,
    home_score: int | None = 100,
    away_score: int | None = 95,
):
    conn.execute(
        text(
            """
            INSERT INTO matches (game_id, is_completed, home_score, away_score)
            VALUES (:game_id, TRUE, :home_score, :away_score)
            """
        ),
        {
            "game_id": game_id,
            "home_score": home_score,
            "away_score": away_score,
        },
    )

    for _ in range(team_rows):
        conn.execute(
            text("INSERT INTO team_game_stats (game_id) VALUES (:game_id)"),
            {"game_id": game_id},
        )

    if has_player_stats:
        conn.execute(
            text("INSERT INTO player_game_stats (game_id) VALUES (:game_id)"),
            {"game_id": game_id},
        )


def test_audit_data_passes_when_invariants_hold(db_audit_engine):
    proxy, conn = db_audit_engine
    _seed_completed_game(conn, "ITG-OK-0001", team_rows=2, has_player_stats=True, home_score=111, away_score=103)

    summary = audit_data(proxy)

    assert summary["team_stats_violations"] == 0
    assert summary["player_stats_missing_games"] == 0
    assert summary["null_score_matches"] == 0
    assert summary["passed"] is True


def test_audit_data_detects_missing_team_stats(db_audit_engine):
    proxy, conn = db_audit_engine
    _seed_completed_game(conn, "ITG-BAD-TEAM", team_rows=1, has_player_stats=True, home_score=104, away_score=99)

    summary = audit_data(proxy)

    assert summary["team_stats_violations"] == 1
    assert summary["player_stats_missing_games"] == 0
    assert summary["null_score_matches"] == 0
    assert summary["passed"] is False


def test_audit_data_detects_missing_player_stats(db_audit_engine):
    proxy, conn = db_audit_engine
    _seed_completed_game(conn, "ITG-BAD-PLYR", team_rows=2, has_player_stats=False, home_score=97, away_score=95)

    summary = audit_data(proxy)

    assert summary["team_stats_violations"] == 0
    assert summary["player_stats_missing_games"] == 1
    assert summary["null_score_matches"] == 0
    assert summary["passed"] is False


def test_audit_data_detects_null_scores(db_audit_engine):
    proxy, conn = db_audit_engine
    _seed_completed_game(conn, "ITG-BAD-NULL", team_rows=2, has_player_stats=True, home_score=None, away_score=108)

    summary = audit_data(proxy)

    assert summary["team_stats_violations"] == 0
    assert summary["player_stats_missing_games"] == 0
    assert summary["null_score_matches"] == 1
    assert summary["passed"] is False
