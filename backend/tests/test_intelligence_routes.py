"""
Tests for intelligence API routes.
"""

from datetime import date

from fastapi.testclient import TestClient

from main import app
from src.api import intelligence_routes as intelligence_routes_module
from src.data.db import get_db


client = TestClient(app)


class _FakeDB:
    pass


def _override_get_db():
    yield _FakeDB()


class TestIntelligenceRoutes:
    def test_game_intelligence_success(self, monkeypatch):
        class _FakeService:
            def __init__(self, _db):
                pass

            def get_game_intelligence(self, **_kwargs):
                return {
                    "game_id": "001",
                    "season": "2025-26",
                    "generated_at": "2026-02-28T12:00:00",
                    "summary": "Context summary.",
                    "risk_signals": [
                        {"id": "injury_watch", "label": "Injury Watch", "severity": "medium", "rationale": "test"}
                    ],
                    "citations": [
                        {
                            "title": "Report",
                            "url": "https://example.com",
                            "source": "example.com",
                            "published_at": "2026-02-28T10:00:00+00:00",
                            "snippet": "snippet",
                        }
                    ],
                    "retrieval": {"docs_considered": 12, "docs_used": 3, "freshness_window_hours": 120},
                    "coverage_status": "sufficient",
                }

        monkeypatch.setattr(intelligence_routes_module, "IntelligenceService", _FakeService)
        app.dependency_overrides[get_db] = _override_get_db
        try:
            response = client.get("/api/v1/intelligence/game/001")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        payload = response.json()
        assert payload["game_id"] == "001"
        assert payload["coverage_status"] == "sufficient"
        assert len(payload["citations"]) == 1

    def test_game_intelligence_404_passthrough(self, monkeypatch):
        from fastapi import HTTPException

        class _FakeService:
            def __init__(self, _db):
                pass

            def get_game_intelligence(self, **_kwargs):
                raise HTTPException(status_code=404, detail="Game 404 not found")

        monkeypatch.setattr(intelligence_routes_module, "IntelligenceService", _FakeService)
        app.dependency_overrides[get_db] = _override_get_db
        try:
            response = client.get("/api/v1/intelligence/game/404")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_daily_brief_shape(self, monkeypatch):
        class _FakeService:
            def __init__(self, _db):
                pass

            def get_daily_brief(self, **_kwargs):
                return {
                    "date": date(2026, 2, 28).isoformat(),
                    "season": "2025-26",
                    "items": [
                        {
                            "game_id": "001",
                            "matchup": "BOS @ LAL",
                            "summary": "Brief",
                            "risk_level": "low",
                            "citation_count": 2,
                        }
                    ],
                }

        monkeypatch.setattr(intelligence_routes_module, "IntelligenceService", _FakeService)
        app.dependency_overrides[get_db] = _override_get_db
        try:
            response = client.get("/api/v1/intelligence/brief?date=2026-02-28&season=2025-26")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        payload = response.json()
        assert payload["date"] == "2026-02-28"
        assert payload["items"][0]["citation_count"] == 2

    def test_intelligence_disabled_returns_503(self, monkeypatch):
        monkeypatch.setattr(intelligence_routes_module.config, "INTELLIGENCE_ENABLED", False)
        app.dependency_overrides[get_db] = _override_get_db
        try:
            response = client.get("/api/v1/intelligence/brief")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 503
