"""
Tests for LangGraphChatService orchestration behavior.
"""

from src.intelligence.langgraph_chat_service import LangGraphChatService


class _FakeDB:
    pass


def test_langgraph_service_falls_back_when_graph_unavailable(monkeypatch):
    monkeypatch.setattr(LangGraphChatService, "_build_graph", lambda self: None)
    service = LangGraphChatService(db=_FakeDB(), sport="nba")

    def _legacy_reply(message, history, session_id=None):
        return f"legacy::{message}::{len(history)}::{session_id or 'none'}"

    monkeypatch.setattr(service._legacy, "reply", _legacy_reply)
    reply = service.reply("hello", history=[{"role": "user", "content": "x"}], session_id="s1")
    assert reply == "legacy::hello::1::s1"
    assert service.active_engine == "legacy"


def test_langgraph_rag_quality_gate_without_docs(monkeypatch):
    service = LangGraphChatService(db=_FakeDB(), sport="nba")
    if not service.graph_available:
        # Environment without langgraph/langchain — fallback path is tested above.
        return

    monkeypatch.setattr(
        service._legacy._retriever,
        "retrieve",
        lambda *_args, **_kwargs: ([], {"docs_considered": 0, "docs_used": 0, "freshness_window_hours": 120}),
    )
    reply = service.reply("Any injury updates for tonight?", history=[])
    assert "don't have recent news/context indexed" in reply.lower()


def test_langgraph_db_retry_path(monkeypatch):
    service = LangGraphChatService(db=_FakeDB(), sport="nba")
    if not service.graph_available:
        return

    calls = []

    def _db_reply(message, history):
        calls.append((message, history))
        if len(calls) == 1:
            return "I couldn't generate a database query for that question."
        return "Recovered DB answer."

    monkeypatch.setattr(service._legacy, "_db_reply", _db_reply)
    reply = service.reply("Which team has the best win rate this season?", history=[])
    assert reply == "Recovered DB answer."
    assert len(calls) == 2


def test_langgraph_off_topic_decline(monkeypatch):
    service = LangGraphChatService(db=_FakeDB(), sport="nba")
    if not service.graph_available:
        return

    monkeypatch.setattr(service._legacy, "_decline", lambda: "Off-topic decline.")
    reply = service.reply("What is the weather in Delhi today?", history=[])
    assert reply == "Off-topic decline."
