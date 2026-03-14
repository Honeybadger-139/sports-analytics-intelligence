"""
Tests for Wave 3 Runtime Config Store
========================================
Tests: get/set/list/delete config operations with mocked engine.
"""

import pytest
from unittest.mock import MagicMock, patch


def _make_engine(fetchone_return=None, fetchall_return=None, execute_ok=True):
    """Build a minimal mock engine for runtime_config tests."""
    mock_result = MagicMock()
    mock_result.fetchone.return_value = fetchone_return
    mock_result.fetchall.return_value = fetchall_return or []
    mock_result.scalar.return_value = None

    mock_conn = MagicMock()
    mock_conn.execute.return_value = mock_result

    # Read context (engine.connect)
    read_ctx = MagicMock()
    read_ctx.__enter__ = lambda s: mock_conn
    read_ctx.__exit__ = MagicMock(return_value=False)

    # Write context (engine.begin)
    write_ctx = MagicMock()
    write_ctx.__enter__ = lambda s: mock_conn
    write_ctx.__exit__ = MagicMock(return_value=False)

    mock_engine = MagicMock()
    mock_engine.connect.return_value = read_ctx
    if execute_ok:
        mock_engine.begin.return_value = write_ctx
    else:
        mock_engine.begin.side_effect = RuntimeError("DB error")

    return mock_engine


# ── get_config ────────────────────────────────────────────────────────────────

class TestGetConfig:
    def test_returns_value_when_key_exists(self):
        from src.data.runtime_config import get_config

        engine = _make_engine(fetchone_return=("0.4",))
        result = get_config(engine, "rag_min_similarity")
        assert result == "0.4"

    def test_returns_default_when_key_missing(self):
        from src.data.runtime_config import get_config

        engine = _make_engine(fetchone_return=None)
        result = get_config(engine, "nonexistent_key", default="fallback")
        assert result == "fallback"

    def test_returns_none_default_when_key_missing_and_no_default(self):
        from src.data.runtime_config import get_config

        engine = _make_engine(fetchone_return=None)
        result = get_config(engine, "nonexistent_key")
        assert result is None

    def test_returns_default_on_db_error(self):
        from src.data.runtime_config import get_config

        mock_engine = MagicMock()
        mock_engine.connect.side_effect = RuntimeError("DB down")
        result = get_config(mock_engine, "any_key", default="safe_fallback")
        assert result == "safe_fallback"


# ── get_config_float / get_config_int ─────────────────────────────────────────

class TestGetConfigTyped:
    def test_float_parsed_correctly(self):
        from src.data.runtime_config import get_config_float

        engine = _make_engine(fetchone_return=("0.35",))
        result = get_config_float(engine, "psi_threshold", 0.2)
        assert abs(result - 0.35) < 1e-9

    def test_float_default_on_invalid_value(self):
        from src.data.runtime_config import get_config_float

        engine = _make_engine(fetchone_return=("not-a-float",))
        result = get_config_float(engine, "psi_threshold", 0.2)
        assert result == 0.2

    def test_int_parsed_correctly(self):
        from src.data.runtime_config import get_config_int

        engine = _make_engine(fetchone_return=("10",))
        result = get_config_int(engine, "some_count", 5)
        assert result == 10

    def test_int_default_on_invalid_value(self):
        from src.data.runtime_config import get_config_int

        engine = _make_engine(fetchone_return=("abc",))
        result = get_config_int(engine, "some_count", 5)
        assert result == 5


# ── set_config ────────────────────────────────────────────────────────────────

class TestSetConfig:
    def test_set_config_returns_true_on_success(self):
        from src.data.runtime_config import set_config

        engine = _make_engine()
        result = set_config(engine, "psi_drift_threshold", "0.3", description="Drift sensitivity")
        assert result is True

    def test_set_config_returns_false_on_db_error(self):
        from src.data.runtime_config import set_config

        engine = _make_engine(execute_ok=False)
        result = set_config(engine, "bad_key", "value")
        assert result is False

    def test_set_config_without_description(self):
        from src.data.runtime_config import set_config

        engine = _make_engine()
        result = set_config(engine, "active_model_path", "/models/v3")
        assert result is True


# ── list_configs ──────────────────────────────────────────────────────────────

class TestListConfigs:
    def test_list_returns_all_entries(self):
        from src.data.runtime_config import list_configs
        from datetime import datetime

        fake_rows = [
            ("active_model_path", "/models/v3", "Active model dir", datetime(2026, 3, 14), datetime(2026, 3, 14)),
            ("psi_drift_threshold", "0.2", "Drift sensitivity", datetime(2026, 3, 14), datetime(2026, 3, 14)),
        ]
        engine = _make_engine(fetchall_return=fake_rows)
        configs = list_configs(engine)
        assert len(configs) == 2
        assert configs[0]["key"] == "active_model_path"
        assert configs[1]["key"] == "psi_drift_threshold"

    def test_list_returns_empty_on_db_error(self):
        from src.data.runtime_config import list_configs

        mock_engine = MagicMock()
        mock_engine.connect.side_effect = RuntimeError("DB down")
        configs = list_configs(mock_engine)
        assert configs == []


# ── delete_config ──────────────────────────────────────────────────────────────

class TestDeleteConfig:
    def test_delete_returns_true_when_row_deleted(self):
        from src.data.runtime_config import delete_config

        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("some_key",)  # row existed
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        write_ctx = MagicMock()
        write_ctx.__enter__ = lambda s: mock_conn
        write_ctx.__exit__ = MagicMock(return_value=False)
        engine = MagicMock()
        engine.begin.return_value = write_ctx

        result = delete_config(engine, "some_key")
        assert result is True

    def test_delete_returns_false_when_key_not_found(self):
        from src.data.runtime_config import delete_config

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None  # no row
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        write_ctx = MagicMock()
        write_ctx.__enter__ = lambda s: mock_conn
        write_ctx.__exit__ = MagicMock(return_value=False)
        engine = MagicMock()
        engine.begin.return_value = write_ctx

        result = delete_config(engine, "nonexistent")
        assert result is False

    def test_delete_returns_false_on_db_error(self):
        from src.data.runtime_config import delete_config

        engine = MagicMock()
        engine.begin.side_effect = RuntimeError("DB down")
        result = delete_config(engine, "any_key")
        assert result is False
