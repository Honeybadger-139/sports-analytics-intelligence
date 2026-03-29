"""
Focused tests for the guarded asynchronous RAG refresh helper.
"""

from src.intelligence import rag_refresh_guard as guard


class _FakeThread:
    def __init__(self, target, name=None, daemon=None):  # noqa: ARG002 - parity with threading.Thread
        self._target = target

    def start(self):
        self._target()


def test_trigger_guarded_rag_refresh_schedules_only_once_within_cooldown(monkeypatch):
    guard.reset_rag_refresh_guard()
    scheduled = []
    clock = {"now": 100.0}

    monkeypatch.setattr(guard.threading, "Thread", _FakeThread)
    monkeypatch.setattr(guard.time, "monotonic", lambda: clock["now"])

    assert guard.trigger_guarded_rag_refresh(
        reason="rag_empty:injury",
        refresh_job=lambda: scheduled.append("refresh"),
        cooldown_seconds=60,
    ) is True
    assert scheduled == ["refresh"]

    clock["now"] = 130.0
    assert guard.trigger_guarded_rag_refresh(
        reason="rag_empty:injury",
        refresh_job=lambda: scheduled.append("refresh"),
        cooldown_seconds=60,
    ) is False
    assert scheduled == ["refresh"]

    clock["now"] = 170.0
    assert guard.trigger_guarded_rag_refresh(
        reason="rag_empty:injury",
        refresh_job=lambda: scheduled.append("refresh"),
        cooldown_seconds=60,
    ) is True
    assert scheduled == ["refresh", "refresh"]

