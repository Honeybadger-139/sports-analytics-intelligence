"""
Tests for prediction persistence utilities.
"""

from src.data import prediction_store


class _Result:
    def __init__(self, rowcount=0):
        self.rowcount = rowcount


class _FakeSession:
    def __init__(self):
        self.insert_attempts = 0
        self.queries = []
        self.params = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, query, _params=None):
        q = str(query)
        self.queries.append(q)
        self.params.append(_params)

        if "INSERT INTO predictions" in q:
            self.insert_attempts += 1
            if self.insert_attempts == 1:
                raise RuntimeError('relation "predictions" does not exist')
            return _Result()

        if "UPDATE predictions p" in q:
            return _Result(rowcount=3)

        return _Result()

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_persist_game_predictions_bootstraps_missing_table():
    db = _FakeSession()
    predictions = {
        "xgboost": {"home_win_prob": 0.61, "away_win_prob": 0.39, "confidence": 0.61},
        "ensemble": {"home_win_prob": 0.58, "away_win_prob": 0.42, "confidence": 0.58},
    }
    shap_factors = {
        "xgboost": [{"feature": "win_pct_last_10", "shap_value": 0.12, "direction": "positive"}],
        "ensemble": [{"feature": "avg_off_rating_last_5", "shap_value": -0.07, "direction": "negative"}],
    }

    count = prediction_store.persist_game_predictions(db, "001", predictions, shap_factors_by_model=shap_factors)

    assert count == 2
    assert db.insert_attempts == 3  # 1 fail + 2 successful inserts after bootstrap
    assert db.rollbacks == 1
    joined = "\n".join(db.queries)
    assert "CREATE TABLE IF NOT EXISTS predictions" in joined
    insert_params = [params for query, params in zip(db.queries, db.params) if "INSERT INTO predictions" in query and params]
    assert insert_params[0]["shap_factors"] == '[{"feature": "win_pct_last_10", "shap_value": 0.12, "direction": "positive"}]'


def test_sync_prediction_outcomes_returns_rowcount():
    db = _FakeSession()
    rows = prediction_store.sync_prediction_outcomes(db, season="2025-26")
    assert rows == 3


def test_missing_predictions_table_detector():
    err = RuntimeError('psycopg2.errors.UndefinedTable: relation "predictions" does not exist')
    assert prediction_store.is_missing_predictions_table_error(err) is True
    assert prediction_store.is_missing_predictions_table_error(RuntimeError("boom")) is False
