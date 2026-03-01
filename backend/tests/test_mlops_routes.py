"""
Tests for Phase 5 MLOps endpoints.
"""

from fastapi.testclient import TestClient

from main import app
from src.data.db import get_db


client = TestClient(app)


class _Result:
    def __init__(self, *, fetchone_value=None, scalar_value=None, fetchall_value=None):
        self._fetchone_value = fetchone_value
        self._scalar_value = scalar_value
        self._fetchall_value = fetchall_value or []

    def fetchone(self):
        return self._fetchone_value

    def scalar(self):
        return self._scalar_value

    def fetchall(self):
        return self._fetchall_value


class _PerfRow:
    def __init__(self):
        self.evaluated_predictions = 120
        self.accuracy = 0.58
        self.brier_score = 0.23


class _PoorPerfRow:
    def __init__(self):
        self.evaluated_predictions = 120
        self.accuracy = 0.44
        self.brier_score = 0.34


class _FakeDB:
    def execute(self, query, _params=None):
        q = str(query)
        if "COUNT(*) AS evaluated_predictions" in q:
            return _Result(fetchone_value=_PerfRow())
        if "SELECT MAX(game_date)" in q:
            return _Result(scalar_value=__import__("datetime").date(2026, 2, 27))
        if "SELECT MAX(sync_time)" in q:
            return _Result(scalar_value=__import__("datetime").datetime(2026, 2, 28, 9, 0, 0))
        if "FROM mlops_monitoring_snapshot" in q:
            return _Result(
                fetchall_value=[
                    __import__("types").SimpleNamespace(
                        _mapping={
                            "snapshot_time": __import__("datetime").datetime(2026, 2, 28, 9, 0, 0),
                            "evaluated_predictions": 120,
                            "accuracy": 0.58,
                            "brier_score": 0.23,
                            "game_data_freshness_days": 1,
                            "pipeline_freshness_days": 0,
                            "alert_count": 0,
                        }
                    )
                ]
            )
        if "FROM matches" in q and "is_completed = TRUE" in q and "COUNT(*)" in q:
            return _Result(scalar_value=180)
        if "FROM retrain_jobs" in q:
            return _Result(fetchall_value=[])
        return _Result(scalar_value=0)


class _EscalationDB:
    def execute(self, query, _params=None):
        q = str(query)
        if "COUNT(*) AS evaluated_predictions" in q:
            return _Result(fetchone_value=_PoorPerfRow())
        if "SELECT MAX(game_date)" in q:
            return _Result(scalar_value=__import__("datetime").date(2026, 2, 24))
        if "SELECT MAX(sync_time)" in q:
            return _Result(scalar_value=__import__("datetime").datetime(2026, 2, 24, 9, 0, 0))
        if "FROM mlops_monitoring_snapshot" in q:
            return _Result(
                fetchall_value=[
                    __import__("types").SimpleNamespace(
                        _mapping={
                            "snapshot_time": __import__("datetime").datetime(2026, 2, 28, 9, 0, 0),
                            "evaluated_predictions": 120,
                            "accuracy": 0.50,
                            "brier_score": 0.30,
                            "game_data_freshness_days": 3,
                            "pipeline_freshness_days": 3,
                            "alert_count": 2,
                        }
                    )
                ]
            )
        if "FROM matches" in q and "is_completed = TRUE" in q and "COUNT(*)" in q:
            return _Result(scalar_value=180)
        return _Result(scalar_value=0)


def _override_get_db():
    yield _FakeDB()


def _override_escalation_db():
    yield _EscalationDB()


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
        assert "escalation" in payload

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

    def test_monitoring_trend_endpoint(self):
        app.dependency_overrides[get_db] = _override_get_db
        try:
            response = client.get("/api/v1/mlops/monitoring/trend?season=2025-26&days=14&limit=10")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        payload = response.json()
        assert payload["season"] == "2025-26"
        assert payload["window_days"] == 14
        assert len(payload["points"]) == 1

    def test_monitoring_escalation_policy(self):
        app.dependency_overrides[get_db] = _override_escalation_db
        try:
            response = client.get("/api/v1/mlops/monitoring?season=2025-26")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        payload = response.json()
        assert payload["escalation"]["state"] in {"watch", "incident"}
        assert any(alert["recommended_action"] in {"investigate_now", "open_incident"} for alert in payload["alerts"])

    def test_retrain_policy_execute_mode_shape(self):
        app.dependency_overrides[get_db] = _override_get_db
        try:
            response = client.get("/api/v1/mlops/retrain/policy?season=2025-26&dry_run=false")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        payload = response.json()
        assert payload["dry_run"] is False
        assert payload["action"] in {"queue-retrain", "queued-retrain", "already-queued", "noop"}
        assert "execution" in payload

    def test_retrain_jobs_endpoint_shape(self):
        app.dependency_overrides[get_db] = _override_get_db
        try:
            response = client.get("/api/v1/mlops/retrain/jobs?season=2025-26&limit=5")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        payload = response.json()
        assert payload["season"] == "2025-26"
        assert "jobs" in payload
