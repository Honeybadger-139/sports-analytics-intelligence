"""
Tests for Scribble route hardening.
"""

from fastapi.testclient import TestClient

from main import app
from src.data.db import get_db


client = TestClient(app)


class _Result:
    def keys(self):
        return ["answer"]

    def fetchall(self):
        return [(42,)]


class _FakeDB:
    def __init__(self):
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((str(query), params))
        if "SELECT 42" in str(query):
            return _Result()
        return None

    def rollback(self):
        return None


def _reset_rate_limits():
    limiter = getattr(app.state, "limiter", None)
    storage = getattr(limiter, "_storage", None)
    if storage is not None and hasattr(storage, "reset"):
        storage.reset()


def test_scribble_query_sets_five_second_statement_timeout():
    db = _FakeDB()

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        response = client.post("/api/v1/scribble/query", json={"sql": "SELECT 42"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    timeout_calls = [call for call in db.calls if "SET LOCAL statement_timeout" in call[0]]
    assert timeout_calls
    assert timeout_calls[0][1] == {"ms": 5000}


def test_scribble_query_rate_limits_after_thirty_requests():
    _reset_rate_limits()
    db = _FakeDB()

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        for _ in range(30):
            response = client.post("/api/v1/scribble/query", json={"sql": "SELECT 42"})
            assert response.status_code == 200
        limited = client.post("/api/v1/scribble/query", json={"sql": "SELECT 42"})
    finally:
        app.dependency_overrides.pop(get_db, None)
        _reset_rate_limits()

    assert limited.status_code == 429
