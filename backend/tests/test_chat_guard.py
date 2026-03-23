from fastapi import HTTPException

from src.intelligence.chat_guard import ChatAbuseGuard


def test_chat_guard_blocks_oversized_prompt(monkeypatch):
    monkeypatch.setattr("src.intelligence.chat_guard.config.CHAT_MAX_ESTIMATED_INPUT_TOKENS", 5)
    guard = ChatAbuseGuard()

    try:
        guard.precheck(api_key="k1", message="x" * 200, history_chars=0)
        assert False, "Expected oversized prompt to be rejected"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "too large" in str(exc.detail).lower()


def test_chat_guard_throttles_repeated_expensive_prompts(monkeypatch):
    monkeypatch.setattr("src.intelligence.chat_guard.config.CHAT_MAX_EXPENSIVE_PER_WINDOW", 1)
    monkeypatch.setattr("src.intelligence.chat_guard.config.CHAT_ANOMALY_WINDOW_SECONDS", 600)
    guard = ChatAbuseGuard()

    guard.precheck(api_key="k2", message="show all rows for all games ever", history_chars=0)
    try:
        guard.precheck(api_key="k2", message="dump table without limit", history_chars=0)
        assert False, "Expected expensive prompt throttle"
    except HTTPException as exc:
        assert exc.status_code == 429
        assert "expensive-query" in str(exc.detail).lower()


def test_chat_guard_blocks_repeated_off_topic(monkeypatch):
    monkeypatch.setattr("src.intelligence.chat_guard.config.CHAT_MAX_OFFTOPIC_PER_WINDOW", 1)
    monkeypatch.setattr("src.intelligence.chat_guard.config.CHAT_ANOMALY_WINDOW_SECONDS", 600)
    guard = ChatAbuseGuard()

    guard.record_policy_outcome(api_key="k3", policy_decision="blocked")
    try:
        guard.record_policy_outcome(api_key="k3", policy_decision="blocked")
        assert False, "Expected off-topic throttle"
    except HTTPException as exc:
        assert exc.status_code == 429
        assert "out-of-scope" in str(exc.detail).lower()
