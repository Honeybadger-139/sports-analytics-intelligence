"""
Tests for centralized configuration module.
"""
import pytest


class TestConfig:
    """Tests for config.py values and defaults."""

    def test_database_url_exists(self):
        """DATABASE_URL should have a default value."""
        from src.config import DATABASE_URL
        assert DATABASE_URL is not None
        assert "postgresql" in DATABASE_URL

    def test_request_delay_reasonable(self):
        """Rate limit delay should be between 1-5 seconds."""
        from src.config import REQUEST_DELAY
        assert 1.0 <= REQUEST_DELAY <= 5.0

    def test_max_retries_positive(self):
        """Retries should be a positive integer."""
        from src.config import MAX_RETRIES
        assert MAX_RETRIES > 0

    def test_current_season_format(self):
        """Season string should be in 'YYYY-YY' format."""
        from src.config import CURRENT_SEASON
        assert len(CURRENT_SEASON) == 7
        assert CURRENT_SEASON[4] == "-"

    def test_log_dir_exists(self):
        """LOG_DIR should exist after config import."""
        from src.config import LOG_DIR
        assert LOG_DIR.exists()

    def test_model_dir_path(self):
        """MODEL_DIR should point to a reasonable path."""
        from src.config import MODEL_DIR
        assert "models" in str(MODEL_DIR)
