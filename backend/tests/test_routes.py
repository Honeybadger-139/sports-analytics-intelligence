"""
Tests for API endpoints using FastAPI TestClient.

These tests verify that endpoints return correct response shapes
and status codes. They require a running database for full integration
testing, so some tests are marked to skip when DB is unavailable.
"""
import pytest
from fastapi.testclient import TestClient
from main import app
from src.data.db import get_db


client = TestClient(app)


class TestHealthEndpoints:
    """Tests for health-check and root endpoints."""

    def test_root_returns_200(self):
        """Root endpoint should return 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_serves_frontend_html(self):
        """Root should serve dashboard HTML when static frontend is mounted."""
        response = client.get("/")
        content_type = response.headers.get("content-type", "")
        assert "text/html" in content_type
        assert "<html" in response.text.lower()

    def test_health_endpoint(self):
        """/api/v1/health should return healthy."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestPredictionEndpoints:
    """Tests for prediction-related endpoints (shape validation)."""

    def test_bet_sizing_valid_input(self):
        """/api/v1/predictions/bet-sizing with valid params."""
        response = client.get(
            "/api/v1/predictions/bet-sizing",
            params={"model_prob": 0.65, "odds": 150}
        )
        assert response.status_code == 200
        data = response.json()
        assert "recommendation" in data
        assert "bet_amount" in data

    def test_bet_sizing_invalid_probability(self):
        """model_prob > 1.0 should return 422."""
        response = client.get(
            "/api/v1/predictions/bet-sizing",
            params={"model_prob": 1.5, "odds": 150}
        )
        assert response.status_code == 422

    def test_bet_sizing_missing_params(self):
        """Missing required params should return 422."""
        response = client.get("/api/v1/predictions/bet-sizing")
        assert response.status_code == 422


class TestDocumentation:
    """Tests that API documentation endpoints exist."""

    def test_swagger_docs(self):
        """/docs should serve Swagger UI."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json(self):
        """/openapi.json should return the API schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data
        assert "info" in data


class TestSystemStatus:
    """Tests for /api/v1/system/status."""

    def test_system_status_exposes_audit_violations(self):
        class _Result:
            def __init__(self, *, fetchall_value=None, scalar_value=None):
                self._fetchall_value = fetchall_value
                self._scalar_value = scalar_value

            def fetchall(self):
                return self._fetchall_value

            def scalar(self):
                return self._scalar_value

        class _FakeDB:
            def execute(self, query, _params=None):
                q = str(query)
                if "SELECT 1" in q:
                    return _Result()
                if "FROM pipeline_audit" in q:
                    row = type(
                        "AuditRow",
                        (),
                        {
                            "id": 1,
                            "sync_time": __import__("datetime").datetime(2026, 2, 28, 9, 0, 0),
                            "module": "ingestion",
                            "status": "success",
                            "records_processed": 100,
                            "records_inserted": 100,
                            "errors": None,
                            "details": {
                                "audit_violations": {
                                    "team_stats_violations": 0,
                                    "player_stats_missing_games": 0,
                                    "null_score_matches": 0,
                                    "passed": True,
                                }
                            },
                        },
                    )
                    return _Result(fetchall_value=[row])
                if "SELECT COUNT(*) FROM matches" in q:
                    return _Result(scalar_value=10)
                if "SELECT COUNT(*) FROM match_features" in q:
                    return _Result(scalar_value=8)
                if "SELECT COUNT(*) FROM players" in q:
                    return _Result(scalar_value=300)
                return _Result(scalar_value=0)

        def _override_get_db():
            yield _FakeDB()

        app.dependency_overrides[get_db] = _override_get_db
        try:
            response = client.get("/api/v1/system/status")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        payload = response.json()
        assert payload["pipeline"]["audit_violations"]["passed"] is True
