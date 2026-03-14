"""
Tests for Wave 3 Lab + Admin Routes
======================================
Tests: GET /api/v1/lab/failed-ingestion (with various filters),
       GET/PATCH/DELETE /api/v1/admin/config/{key} (auth + CRUD).
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.api.lab_routes import router as lab_router
from src.api.admin_routes import router as admin_router
from src.data.db import get_db


# ── Shared helpers ────────────────────────────────────────────────────────────

def _mock_session():
    session = MagicMock()
    session.get_bind.return_value = MagicMock()
    return session


def _get_db_override(session):
    def _override():
        yield session
    return _override


def _make_app(api_key="test-key-xyz"):
    """Build a fresh FastAPI app with lab + admin routers."""
    os.environ["CHAT_API_KEY"] = api_key
    app = FastAPI()
    app.include_router(lab_router)
    app.include_router(admin_router)
    session = _mock_session()
    app.dependency_overrides[get_db] = _get_db_override(session)
    return TestClient(app), api_key


# ── Lab routes ────────────────────────────────────────────────────────────────

class TestLabFailedIngestion:
    def test_returns_200_with_empty_records(self):
        tc, _ = _make_app()
        with patch("src.api.lab_routes.list_failed_records", return_value=[]), \
             patch("src.api.lab_routes.count_failed_records", return_value=0):
            resp = tc.get("/api/v1/lab/failed-ingestion")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 0
        assert data["records"] == []
        assert "offset" in data
        assert "limit" in data

    def test_pagination_params_forwarded(self):
        tc, _ = _make_app()
        with patch("src.api.lab_routes.list_failed_records", return_value=[]), \
             patch("src.api.lab_routes.count_failed_records", return_value=5):
            resp = tc.get("/api/v1/lab/failed-ingestion?limit=10&offset=5&entity_type=game")

        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 10
        assert data["offset"] == 5
        assert data["filters"]["entity_type"] == "game"

    def test_invalid_limit_rejected(self):
        tc, _ = _make_app()
        resp = tc.get("/api/v1/lab/failed-ingestion?limit=0")
        assert resp.status_code == 422

    def test_returns_records_from_store(self):
        tc, _ = _make_app()
        fake_records = [
            {"id": 1, "entity_type": "game", "raw_payload": {}, "validation_errors": ["bad"],
             "source_module": "ingestion", "attempted_at": None, "created_at": None}
        ]
        with patch("src.api.lab_routes.list_failed_records", return_value=fake_records), \
             patch("src.api.lab_routes.count_failed_records", return_value=1):
            resp = tc.get("/api/v1/lab/failed-ingestion")

        assert resp.status_code == 200
        assert resp.json()["total_count"] == 1
        assert len(resp.json()["records"]) == 1


# ── Admin routes ──────────────────────────────────────────────────────────────

class TestAdminConfigRoutes:
    def test_list_configs_returns_200_with_valid_key(self):
        tc, key = _make_app()
        fake_configs = [
            {"key": "psi_drift_threshold", "value": "0.2", "description": None,
             "updated_at": None, "created_at": None}
        ]
        with patch("src.api.admin_routes.list_configs", return_value=fake_configs):
            resp = tc.get("/api/v1/admin/config", headers={"X-API-Key": key})

        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_list_configs_returns_401_without_key(self):
        tc, _ = _make_app()
        resp = tc.get("/api/v1/admin/config")
        assert resp.status_code == 401

    def test_list_configs_returns_401_with_wrong_key(self):
        tc, _ = _make_app(api_key="correct-key")
        resp = tc.get("/api/v1/admin/config", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    def test_get_config_returns_value(self):
        tc, key = _make_app()
        with patch("src.api.admin_routes.get_config", return_value="0.4"):
            resp = tc.get("/api/v1/admin/config/rag_min_similarity",
                          headers={"X-API-Key": key})

        assert resp.status_code == 200
        assert resp.json()["value"] == "0.4"
        assert resp.json()["key"] == "rag_min_similarity"

    def test_get_config_returns_404_when_missing(self):
        tc, key = _make_app()
        with patch("src.api.admin_routes.get_config", return_value=None):
            resp = tc.get("/api/v1/admin/config/nonexistent",
                          headers={"X-API-Key": key})
        assert resp.status_code == 404

    def test_patch_config_updates_value(self):
        tc, key = _make_app()
        with patch("src.api.admin_routes.set_config", return_value=True):
            resp = tc.patch(
                "/api/v1/admin/config/psi_drift_threshold",
                headers={"X-API-Key": key},
                json={"value": "0.15", "description": "Tighter drift sensitivity"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "updated"
        assert data["value"] == "0.15"

    def test_patch_config_returns_500_on_db_failure(self):
        tc, key = _make_app()
        with patch("src.api.admin_routes.set_config", return_value=False):
            resp = tc.patch(
                "/api/v1/admin/config/bad_key",
                headers={"X-API-Key": key},
                json={"value": "x"},
            )
        assert resp.status_code == 500

    def test_delete_config_returns_200(self):
        tc, key = _make_app()
        with patch("src.api.admin_routes.delete_config", return_value=True):
            resp = tc.delete("/api/v1/admin/config/temp_flag",
                             headers={"X-API-Key": key})
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_config_returns_404_when_not_found(self):
        tc, key = _make_app()
        with patch("src.api.admin_routes.delete_config", return_value=False):
            resp = tc.delete("/api/v1/admin/config/ghost_key",
                             headers={"X-API-Key": key})
        assert resp.status_code == 404

    def test_admin_disabled_when_no_api_key_env(self):
        """When CHAT_API_KEY is not set, admin API should return 503."""
        os.environ.pop("CHAT_API_KEY", None)
        app = FastAPI()
        app.include_router(admin_router)
        session = _mock_session()
        app.dependency_overrides[get_db] = _get_db_override(session)
        tc = TestClient(app)

        resp = tc.get("/api/v1/admin/config", headers={"X-API-Key": "anything"})
        assert resp.status_code == 503
        # Restore for other tests
        os.environ["CHAT_API_KEY"] = "restored-test-key"
