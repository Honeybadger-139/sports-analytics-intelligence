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


def test_retrain_policy_submits_vertex_pipeline_when_execute_mode(monkeypatch):
    monkeypatch.setattr(
        retrain_policy_module,
        "_submit_vertex_pipeline_job",
        lambda **kwargs: {
            "submitted": True,
            "resource_name": "projects/p/models/123",
            "display_name": "retrain-20260320-120000",
            "project_id": "sports-analytics-intelligence",
        },
    )
    monkeypatch.setattr(retrain_policy_module, "record_intelligence_audit", lambda *args, **kwargs: None)

    payload = retrain_policy_module.evaluate_retrain_need(_FakeDB(), "2025-26", dry_run=False)
    assert payload["should_retrain"] is True
    assert payload["action"] == "queue-retrain"
    assert payload["execution"]["pipeline_job"]["submitted"] is True
    assert payload["execution"]["pipeline_job"]["resource_name"] == "projects/p/models/123"


def test_retrain_policy_dry_run_skips_submission(monkeypatch):
    called = {"count": 0}

    def _should_not_run(**kwargs):
        called["count"] += 1
        return {"submitted": True}

    monkeypatch.setattr(retrain_policy_module, "_submit_vertex_pipeline_job", _should_not_run)
    monkeypatch.setattr(retrain_policy_module, "record_intelligence_audit", lambda *args, **kwargs: None)

    payload = retrain_policy_module.evaluate_retrain_need(_FakeDB(), "2025-26", dry_run=True)
    assert payload["should_retrain"] is True
    assert payload["action"] == "dry-run-noop"
    assert payload["execution"]["pipeline_job"] is None
    assert called["count"] == 0
