"""
Tests for feature engineering pipeline orchestration.
"""

from src.data import feature_store


def test_compute_streak_features_executes_update():
    executed = {}

    class _Conn:
        def execute(self, query, params=None):
            executed["query"] = str(query)
            executed["params"] = params

    class _Ctx:
        def __init__(self, conn):
            self.conn = conn

        def __enter__(self):
            return self.conn

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Engine:
        def __init__(self):
            self.conn = _Conn()

        def begin(self):
            return _Ctx(self.conn)

    engine = _Engine()
    feature_store.compute_streak_features(engine, season="2025-26")

    assert "UPDATE match_features" in executed["query"]
    assert executed["params"] == {"season": "2025-26"}


def test_run_feature_engineering_runs_h2h_and_streak(monkeypatch):
    call_order = []
    recorded = {}

    monkeypatch.setattr(feature_store, "get_engine", lambda: object())
    monkeypatch.setattr(feature_store.config, "CURRENT_SEASON", "2025-26")
    monkeypatch.setattr(
        feature_store,
        "compute_features",
        lambda _engine, season: call_order.append(("compute_features", season)) or 42,
    )
    monkeypatch.setattr(
        feature_store,
        "compute_h2h_features",
        lambda _engine, season: call_order.append(("compute_h2h_features", season)),
    )
    monkeypatch.setattr(
        feature_store,
        "compute_streak_features",
        lambda _engine, season: call_order.append(("compute_streak_features", season)),
    )

    def _record(_engine, module, status, processed=0, inserted=0, errors=None, details=None):
        recorded.update(
            {
                "module": module,
                "status": status,
                "processed": processed,
                "inserted": inserted,
                "errors": errors,
                "details": details,
            }
        )

    monkeypatch.setattr(feature_store, "record_audit", _record)
    monkeypatch.setattr(feature_store.time, "time", lambda: 100.0)

    feature_store.run_feature_engineering()

    assert call_order == [
        ("compute_features", "2025-26"),
        ("compute_h2h_features", "2025-26"),
        ("compute_streak_features", "2025-26"),
    ]
    assert recorded["module"] == "feature_store"
    assert recorded["status"] == "success"
    assert recorded["processed"] == 42
    assert recorded["inserted"] == 42
    assert recorded["details"]["h2h_features_updated"] is True
    assert recorded["details"]["streak_features_updated"] is True
