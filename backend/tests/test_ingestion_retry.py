"""
Tests for ingestion retry logic and audit summaries.
"""
from types import SimpleNamespace

import pytest

from src.data import ingestion


class _FakeResult:
    def __init__(self, *, fetchall_value=None, scalar_value=None):
        self._fetchall_value = fetchall_value
        self._scalar_value = scalar_value

    def fetchall(self):
        return self._fetchall_value

    def scalar(self):
        return self._scalar_value


class _FakeConn:
    def __init__(self, responses):
        self._responses = responses
        self._idx = 0

    def execute(self, _query):
        response = self._responses[self._idx]
        self._idx += 1
        return response


class _FakeCtx:
    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self._conn

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, responses):
        self._responses = responses

    def connect(self):
        return _FakeCtx(_FakeConn(self._responses))


def test_retry_api_call_succeeds_after_transient_failure(monkeypatch):
    calls = {"count": 0}
    sleeps = []

    def _fn():
        calls["count"] += 1
        if calls["count"] < 2:
            raise RuntimeError("temporary")
        return "ok"

    monkeypatch.setattr(ingestion, "rate_limit", lambda: None)
    monkeypatch.setattr(ingestion.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(ingestion.config, "MAX_RETRIES", 3)
    monkeypatch.setattr(ingestion.config, "BASE_BACKOFF", 10)

    assert ingestion.retry_api_call(_fn) == "ok"
    assert calls["count"] == 2
    assert sleeps == [10]


def test_retry_api_call_raises_after_max_retries(monkeypatch):
    monkeypatch.setattr(ingestion, "rate_limit", lambda: None)
    monkeypatch.setattr(ingestion.time, "sleep", lambda _s: None)
    monkeypatch.setattr(ingestion.config, "MAX_RETRIES", 3)
    monkeypatch.setattr(ingestion.config, "BASE_BACKOFF", 10)

    with pytest.raises(RuntimeError):
        ingestion.retry_api_call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))


def test_audit_data_returns_passed_summary():
    responses = [
        _FakeResult(fetchall_value=[]),   # team stats check
        _FakeResult(fetchall_value=[]),   # player stats check
        _FakeResult(scalar_value=0),      # null score check
    ]
    summary = ingestion.audit_data(_FakeEngine(responses))

    assert summary == {
        "team_stats_violations": 0,
        "player_stats_missing_games": 0,
        "null_score_matches": 0,
        "passed": True,
    }


def test_audit_data_returns_failed_summary():
    responses = [
        _FakeResult(fetchall_value=[SimpleNamespace(game_id="1")]),
        _FakeResult(fetchall_value=[SimpleNamespace(game_id="2"), SimpleNamespace(game_id="3")]),
        _FakeResult(scalar_value=4),
    ]
    summary = ingestion.audit_data(_FakeEngine(responses))

    assert summary == {
        "team_stats_violations": 1,
        "player_stats_missing_games": 2,
        "null_score_matches": 4,
        "passed": False,
    }


def test_run_full_ingestion_records_audit_violations(monkeypatch):
    recorded = {}

    monkeypatch.setattr(ingestion, "get_engine", lambda: object())
    monkeypatch.setattr(ingestion, "check_health", lambda _engine: True)
    monkeypatch.setattr(ingestion, "ingest_teams", lambda _engine: 30)
    monkeypatch.setattr(ingestion, "ingest_season_games", lambda _engine, season: 10)
    monkeypatch.setattr(ingestion, "ingest_players", lambda _engine, season: 300)
    monkeypatch.setattr(ingestion, "ingest_player_game_logs", lambda _engine, season: 50)
    monkeypatch.setattr(ingestion, "ingest_player_season_stats", lambda _engine, season: 200)
    monkeypatch.setattr(
        ingestion,
        "audit_data",
        lambda _engine: {
            "team_stats_violations": 0,
            "player_stats_missing_games": 0,
            "null_score_matches": 0,
            "passed": True,
        },
    )

    def _record(_engine, module, status, processed=0, inserted=0, errors=None, details=None):
        recorded.update(
            {
                "module": module,
                "status": status,
                "processed": processed,
                "inserted": inserted,
                "errors": errors,
                "details": details,
            }
        )

    monkeypatch.setattr(ingestion, "record_audit", _record)
    monkeypatch.setattr(ingestion.time, "time", lambda: 100.0)

    ingestion.run_full_ingestion(["2025-26"])

    assert recorded["module"] == "ingestion"
    assert recorded["status"] == "success"
    assert recorded["details"]["audit_violations"]["passed"] is True
