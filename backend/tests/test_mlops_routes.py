"""
Tests for Phase 5 MLOps endpoints.
"""

from fastapi.testclient import TestClient

from main import app
from src.data.db import get_db


client = TestClient(app)


class _Result:
    def __init__(self, *, fetchone_value=None, scalar_value=None):
        self._fetchone_value = fetchone_value
        self._scalar_value = scalar_value

    def fetchone(self):
        return self._fetchone_value

    def scalar(self):
        return self._scalar_value


class _PerfRow:
    def __init__(self):
        self.evaluated_predictions = 120
        self.accuracy = 0.58
        self.brier_score = 0.23


class _FakeDB:
    def execute(self, query, _params=None):
        q = str(query)
        if "COUNT(*) AS evaluated_predictions" in q:
            return _Result(fetchone_value=_PerfRow())
        if "SELECT MAX(game_date)" in q:
            return _Result(scalar_value=__import__("datetime").date(2026, 2, 27))
        if "SELECT MAX(sync_time)" in q:
            return _Result(scalar_value=__import__("datetime").datetime(2026, 2, 28, 9, 0, 0))
        if "FROM matches" in q and "is_completed = TRUE" in q and "COUNT(*)" in q:
            return _Result(scalar_value=180)
        return _Result(scalar_value=0)


def _override_get_db():
    yield _FakeDB()


class TestMlopsRoutes:
    def test_monitoring_endpoint_returns_metrics(self):
        app.dependency_overrides[get_db] = _override_get_db
        try:
            response = client.get("/api/v1/mlops/monitoring?season=2025-26")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        payload = response.json()
        assert payload["metrics"]["evaluated_predictions"] == 120
        assert "alerts" in payload

    def test_retrain_policy_dry_run(self):
        app.dependency_overrides[get_db] = _override_get_db
        try:
            response = client.get("/api/v1/mlops/retrain/policy?season=2025-26&dry_run=true")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        payload = response.json()
        assert payload["dry_run"] is True
        assert "should_retrain" in payload
