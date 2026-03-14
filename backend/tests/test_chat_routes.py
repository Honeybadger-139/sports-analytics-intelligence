"""
Tests for chatbot routes and engine selection.
"""

from fastapi.testclient import TestClient

from main import app
from src.api import chat_routes as chat_routes_module
from src.data.db import get_db


client = TestClient(app)


class _FakeDB:
    def execute(self, *_args, **_kwargs):
        raise RuntimeError("db unavailable in test")


def _override_get_db():
    yield _FakeDB()


def test_get_chat_service_legacy(monkeypatch):
    monkeypatch.setattr(chat_routes_module.config, "CHAT_ENGINE", "legacy")

    class _FakeLegacy:
        def __init__(self, db, sport):
            self.db = db
            self.sport = sport

    monkeypatch.setattr(chat_routes_module, "ChatService", _FakeLegacy)
    service = chat_routes_module._get_chat_service(db=_FakeDB(), sport="nba")
    assert isinstance(service, _FakeLegacy)


def test_get_chat_service_langgraph(monkeypatch):
    monkeypatch.setattr(chat_routes_module.config, "CHAT_ENGINE", "langgraph")

    class _FakeGraph:
        def __init__(self, db, sport):
            self.db = db
            self.sport = sport

    monkeypatch.setattr(chat_routes_module, "LangGraphChatService", _FakeGraph)
    service = chat_routes_module._get_chat_service(db=_FakeDB(), sport="nba")
    assert isinstance(service, _FakeGraph)


def test_chat_endpoint_uses_configured_service(monkeypatch):
    monkeypatch.setattr(chat_routes_module.config, "CHAT_ENGINE", "legacy")

    class _FakeService:
        active_engine = "legacy"

        def reply(self, message, history, session_id=None):
            return f"echo::{message}::{len(history)}::{session_id or 'none'}"

    monkeypatch.setattr(chat_routes_module, "_get_chat_service", lambda db, sport: _FakeService())
    app.dependency_overrides[get_db] = _override_get_db
    try:
        response = client.post(
            "/api/v1/chat",
            json={
                "message": "Hello",
                "history": [{"role": "user", "content": "Old turn"}],
                "session_id": "session-123",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["reply"] == "echo::Hello::1::session-123"
    assert payload["intent"] in {"db", "rag", "off_topic"}
    assert payload["engine"] == "legacy"


def test_chat_health_includes_engine_fields(monkeypatch):
    class _FakeLLM:
        available = False

    class _FakeService:
        active_engine = "langgraph"
        graph_available = True

    monkeypatch.setattr(chat_routes_module.config, "CHAT_ENGINE", "langgraph")
    monkeypatch.setattr(chat_routes_module, "_get_llm_client", lambda: _FakeLLM())
    monkeypatch.setattr(chat_routes_module, "_get_chat_service", lambda db, sport: _FakeService())
    app.dependency_overrides[get_db] = _override_get_db
    try:
        response = client.get("/api/v1/chat/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["chat_engine_configured"] == "langgraph"
    assert payload["chat_engine_active"] == "langgraph"
    assert payload["langgraph_available"] is True


def test_chat_stream_endpoint_emits_sse_events(monkeypatch):
    monkeypatch.setattr(chat_routes_module.config, "CHAT_ENGINE", "legacy")
    monkeypatch.setattr(chat_routes_module.config, "CHAT_API_KEY", "wave1-secret")

    class _FakeService:
        active_engine = "legacy"

        def reply(self, message, history, session_id=None):
            return "Streaming response payload."

    monkeypatch.setattr(chat_routes_module, "_get_chat_service", lambda db, sport: _FakeService())
    app.dependency_overrides[get_db] = _override_get_db
    try:
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "message": "Stream this please",
                "history": [],
                "session_id": "session-stream-1",
            },
            headers={"X-API-Key": "wave1-secret"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: meta" in body
    assert "event: token" in body
    assert "event: done" in body
    assert "Streaming response payload." in body


def test_chat_stream_endpoint_requires_api_key(monkeypatch):
    monkeypatch.setattr(chat_routes_module.config, "CHAT_API_KEY", "wave1-secret")
    app.dependency_overrides[get_db] = _override_get_db
    try:
        response = client.post(
            "/api/v1/chat/stream",
            json={"message": "No auth", "history": []},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 401
    assert "X-API-Key" in response.json()["detail"]


def test_chat_stream_endpoint_returns_503_when_api_key_not_configured(monkeypatch):
    monkeypatch.setattr(chat_routes_module.config, "CHAT_API_KEY", "")
    app.dependency_overrides[get_db] = _override_get_db
    try:
        response = client.post(
            "/api/v1/chat/stream",
            json={"message": "No config", "history": []},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
