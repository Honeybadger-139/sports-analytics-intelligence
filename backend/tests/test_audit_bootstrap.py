"""
Tests for pipeline_audit bootstrap and retry behavior.
"""

from src.data import ingestion, feature_store
from src.data.audit_store import (
    ensure_pipeline_audit_table,
    is_missing_pipeline_audit_error,
)


class _FakeConn:
    def __init__(self, state):
        self.state = state

    def execute(self, query, _params=None):
        q = str(query)
        self.state["queries"].append(q)
        if "INSERT INTO pipeline_audit" in q:
            self.state["insert_attempts"] += 1
            if self.state["insert_attempts"] == 1:
                raise RuntimeError('relation "pipeline_audit" does not exist')


class _FakeCtx:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self):
        self.state = {"queries": [], "insert_attempts": 0}

    def begin(self):
        return _FakeCtx(_FakeConn(self.state))


def test_is_missing_pipeline_audit_error_detects_missing_relation():
    err = RuntimeError('psycopg2.errors.UndefinedTable: relation "pipeline_audit" does not exist')
    assert is_missing_pipeline_audit_error(err) is True
    assert is_missing_pipeline_audit_error(RuntimeError("some other error")) is False


def test_ensure_pipeline_audit_table_emits_ddl():
    engine = _FakeEngine()
    ensure_pipeline_audit_table(engine)

    joined = "\n".join(engine.state["queries"])
    assert "CREATE TABLE IF NOT EXISTS pipeline_audit" in joined
    assert "CREATE INDEX IF NOT EXISTS idx_pipeline_audit_module" in joined
    assert "CREATE INDEX IF NOT EXISTS idx_pipeline_audit_status" in joined


def test_ingestion_record_audit_bootstraps_and_retries():
    engine = _FakeEngine()
    ingestion.record_audit(engine, module="ingestion", status="success")

    joined = "\n".join(engine.state["queries"])
    assert engine.state["insert_attempts"] == 2
    assert "CREATE TABLE IF NOT EXISTS pipeline_audit" in joined


def test_feature_store_record_audit_bootstraps_and_retries():
    engine = _FakeEngine()
    feature_store.record_audit(engine, module="feature_store", status="success")

    joined = "\n".join(engine.state["queries"])
    assert engine.state["insert_attempts"] == 2
    assert "CREATE TABLE IF NOT EXISTS pipeline_audit" in joined
