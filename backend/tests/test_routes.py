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
from src.api import routes as routes_module


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

    def test_predictions_today_returns_games(self, monkeypatch):
        class _FakePredictor:
            def predict_today(self, _engine):
                return [
                    {
                        "game_id": "001",
                        "game_date": "2026-02-28",
                        "home_team": "LAL",
                        "home_team_name": "Los Angeles Lakers",
                        "away_team": "BOS",
                        "away_team_name": "Boston Celtics",
                        "predictions": {
                            "ensemble": {
                                "home_win_prob": 0.58,
                                "away_win_prob": 0.42,
                                "prediction": "home",
                                "confidence": 0.58,
                            }
                        },
                    }
                ]

        class _FakeDB:
            def get_bind(self):
                return object()

        def _override_get_db():
            yield _FakeDB()

        monkeypatch.setattr(routes_module, "get_predictor", lambda: _FakePredictor())
        monkeypatch.setattr(routes_module, "_persist_predictions_for_games", lambda _db, games: len(games))

        app.dependency_overrides[get_db] = _override_get_db
        try:
            response = client.get("/api/v1/predictions/today")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        payload = response.json()
        assert payload["count"] == 1
        assert payload["persisted_rows"] == 1
        assert payload["games"][0]["game_id"] == "001"

    def test_predictions_performance_returns_summary(self, monkeypatch):
        class _Result:
            def __init__(self, fetchall_value=None, scalar_value=None):
                self._fetchall_value = fetchall_value
                self._scalar_value = scalar_value

            def fetchall(self):
                return self._fetchall_value

            def scalar(self):
                return self._scalar_value

        class _FakeDB:
            def execute(self, query, _params=None):
                q = str(query)
                if "GROUP BY p.model_name" in q:
                    row = type(
                        "PerfRow",
                        (),
                        {
                            "_mapping": {
                                "model_name": "ensemble",
                                "evaluated_games": 120,
                                "correct_games": 70,
                                "accuracy": 0.5833,
                                "avg_confidence": 0.6042,
                                "brier_score": 0.2411,
                                "first_prediction_at": __import__("datetime").datetime(2026, 1, 1, 10, 0, 0),
                                "last_prediction_at": __import__("datetime").datetime(2026, 2, 28, 10, 0, 0),
                            }
                        },
                    )
                    return _Result(fetchall_value=[row])
                if "m.is_completed = FALSE" in q:
                    return _Result(scalar_value=8)
                return _Result(fetchall_value=[])

        def _override_get_db():
            yield _FakeDB()

        monkeypatch.setattr(routes_module, "sync_prediction_outcomes", lambda _db, season: 0)

        app.dependency_overrides[get_db] = _override_get_db
        try:
            response = client.get("/api/v1/predictions/performance")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        payload = response.json()
        assert payload["evaluated_models"] == 1
        assert payload["pending_games"] == 8
        assert payload["performance"][0]["model_name"] == "ensemble"


class TestBetLedgerEndpoints:
    """Tests for Phase 2 bet-ledger endpoints."""

    def test_create_bet_returns_created_row(self, monkeypatch):
        class _FakeDB:
            pass

        def _override_get_db():
            yield _FakeDB()

        monkeypatch.setattr(
            routes_module,
            "create_bet",
            lambda *_args, **_kwargs: {
                "id": 41,
                "game_id": "001",
                "bet_type": "match_winner",
                "selection": "LAL",
                "odds": 1.91,
                "stake": 50.0,
                "result": "pending",
            },
        )

        app.dependency_overrides[get_db] = _override_get_db
        try:
            response = client.post(
                "/api/v1/bets",
                json={
                    "game_id": "001",
                    "bet_type": "match_winner",
                    "selection": "LAL",
                    "odds": 1.91,
                    "stake": 50.0,
                    "kelly_fraction": 0.25,
                    "model_probability": 0.57,
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        payload = response.json()
        assert payload["bet"]["id"] == 41
        assert payload["bet"]["result"] == "pending"

    def test_list_bets_returns_count(self, monkeypatch):
        class _FakeDB:
            pass

        def _override_get_db():
            yield _FakeDB()

        monkeypatch.setattr(
            routes_module,
            "list_bets",
            lambda *_args, **_kwargs: [
                {"id": 41, "result": "pending"},
                {"id": 42, "result": "win"},
            ],
        )

        app.dependency_overrides[get_db] = _override_get_db
        try:
            response = client.get("/api/v1/bets?result=settled&limit=10")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        payload = response.json()
        assert payload["count"] == 2
        assert len(payload["bets"]) == 2

    def test_settle_bet_returns_404_when_not_found(self, monkeypatch):
        class _FakeDB:
            pass

        def _override_get_db():
            yield _FakeDB()

        def _raise_not_found(*_args, **_kwargs):
            raise LookupError("bet 999 not found")

        monkeypatch.setattr(routes_module, "settle_bet", _raise_not_found)

        app.dependency_overrides[get_db] = _override_get_db
        try:
            response = client.post("/api/v1/bets/999/settle", json={"result": "win"})
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_bet_summary_returns_metrics(self, monkeypatch):
        class _FakeDB:
            pass

        def _override_get_db():
            yield _FakeDB()

        monkeypatch.setattr(
            routes_module,
            "get_bets_summary",
            lambda *_args, **_kwargs: {
                "season": "2025-26",
                "initial_bankroll": 1000.0,
                "current_bankroll": 1084.5,
                "total_bets": 10,
                "settled_bets": 7,
                "open_bets": 3,
                "total_stake": 1000.0,
                "settled_stake": 700.0,
                "total_pnl": 84.5,
                "roi": 0.1207,
            },
        )

        app.dependency_overrides[get_db] = _override_get_db
        try:
            response = client.get("/api/v1/bets/summary?season=2025-26")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        payload = response.json()
        assert payload["summary"]["current_bankroll"] == 1084.5
        assert payload["summary"]["roi"] == 0.1207


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

    def test_system_status_handles_missing_audit_table(self):
        class _Result:
            def __init__(self, *, scalar_value=None):
                self._scalar_value = scalar_value

            def scalar(self):
                return self._scalar_value

        class _FakeDB:
            def execute(self, query, _params=None):
                q = str(query)
                if "SELECT 1" in q:
                    return _Result()
                if "FROM pipeline_audit" in q:
                    raise RuntimeError('relation "pipeline_audit" does not exist')
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
        assert payload["audit_history"] == []
        assert payload["pipeline"]["last_status"] == "unknown"
