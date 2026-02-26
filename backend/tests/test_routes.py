"""
Tests for API endpoints using FastAPI TestClient.

These tests verify that endpoints return correct response shapes
and status codes. They require a running database for full integration
testing, so some tests are marked to skip when DB is unavailable.
"""
import pytest
from fastapi.testclient import TestClient
from main import app


client = TestClient(app)


class TestHealthEndpoints:
    """Tests for health-check and root endpoints."""

    def test_root_returns_200(self):
        """Root endpoint should return 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_contains_version(self):
        """Root should expose the app version."""
        response = client.get("/")
        data = response.json()
        assert "version" in data
        assert data["version"] == "1.0.0"

    def test_root_contains_status(self):
        """Root should report operational status."""
        response = client.get("/")
        data = response.json()
        assert data["status"] == "operational"

    def test_health_endpoint(self):
        """/api/v1/health should return OK."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


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
