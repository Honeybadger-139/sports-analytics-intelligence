"""
Unit tests for retrain policy execute-mode behavior.
"""

from src.mlops import retrain_policy as retrain_policy_module


class _Result:
    def __init__(self, *, fetchone_value=None, scalar_value=None):
        self._fetchone_value = fetchone_value
        self._scalar_value = scalar_value

    def fetchone(self):
        return self._fetchone_value

    def scalar(self):
        return self._scalar_value


class _PerfRow:
    def __init__(self):
        self.evaluated_predictions = 10
        self.accuracy = 0.50
        self.brier_score = 0.28


class _FakeEngine:
    pass


class _FakeDB:
    def execute(self, query, _params=None):
        q = str(query)
        if "COUNT(*) AS evaluated_predictions" in q:
            return _Result(fetchone_value=_PerfRow())
        if "FROM matches" in q and "is_completed = TRUE" in q and "COUNT(*)" in q:
            return _Result(scalar_value=80)
        return _Result(scalar_value=0)

    def get_bind(self):
        return _FakeEngine()


def test_retrain_policy_queues_job_when_execute_mode(monkeypatch):
    monkeypatch.setattr(retrain_policy_module, "find_recent_active_retrain_job", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        retrain_policy_module,
        "create_retrain_job",
        lambda *args, **kwargs: {"id": 101, "season": "2025-26", "status": "queued"},
    )
    monkeypatch.setattr(retrain_policy_module, "record_intelligence_audit", lambda *args, **kwargs: None)

    payload = retrain_policy_module.evaluate_retrain_need(_FakeDB(), "2025-26", dry_run=False)
    assert payload["should_retrain"] is True
    assert payload["action"] == "queued-retrain"
    assert payload["execution"]["duplicate_guard_triggered"] is False
    assert payload["execution"]["retrain_job"]["id"] == 101


def test_retrain_policy_duplicate_guard(monkeypatch):
    monkeypatch.setattr(
        retrain_policy_module,
        "find_recent_active_retrain_job",
        lambda *args, **kwargs: {"id": 88, "season": "2025-26", "status": "queued"},
    )
    monkeypatch.setattr(
        retrain_policy_module,
        "create_retrain_job",
        lambda *args, **kwargs: {"id": 101, "season": "2025-26", "status": "queued"},
    )
    monkeypatch.setattr(retrain_policy_module, "record_intelligence_audit", lambda *args, **kwargs: None)

    payload = retrain_policy_module.evaluate_retrain_need(_FakeDB(), "2025-26", dry_run=False)
    assert payload["should_retrain"] is True
    assert payload["action"] == "already-queued"
    assert payload["execution"]["duplicate_guard_triggered"] is True
    assert payload["execution"]["retrain_job"]["id"] == 88
