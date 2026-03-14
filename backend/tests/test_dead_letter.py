"""
Tests for Wave 3 Ingestion Validators + Dead-Letter Store
============================================================
Tests: payload validation (happy path + edge cases), batch validation,
       dead-letter persistence (mocked engine), list/count queries.
"""

import pytest

from src.data.validators import (
    TeamPayload,
    GamePayload,
    PlayerPayload,
    validate_payload,
    validate_batch,
)


# ── TeamPayload ───────────────────────────────────────────────────────────────

class TestTeamPayload:
    def test_valid_team(self):
        model, errors = validate_payload("team", {
            "team_id": 1610612747,
            "abbreviation": "LAL",
            "full_name": "Los Angeles Lakers",
            "city": "Los Angeles",
            "conference": "West",
            "division": "Pacific",
        })
        assert model is not None
        assert errors == []

    def test_abbreviation_uppercased(self):
        model, errors = validate_payload("team", {
            "team_id": 1,
            "abbreviation": "lal",
            "full_name": "Los Angeles Lakers",
        })
        assert model is not None
        assert model.abbreviation == "LAL"

    def test_negative_team_id_rejected(self):
        model, errors = validate_payload("team", {
            "team_id": -1,
            "abbreviation": "BAD",
            "full_name": "Bad Team",
        })
        assert model is None
        assert len(errors) > 0

    def test_missing_required_field(self):
        model, errors = validate_payload("team", {
            "team_id": 1,
            # missing abbreviation and full_name
        })
        assert model is None
        assert len(errors) > 0


# ── GamePayload ───────────────────────────────────────────────────────────────

class TestGamePayload:
    def _valid_game(self, **overrides):
        base = {
            "game_id": "0022400001",
            "game_date": "2026-01-15",
            "season": "2025-26",
            "home_team_id": 1,
            "away_team_id": 2,
            "is_completed": True,
            "winner_team_id": 1,
        }
        base.update(overrides)
        return base

    def test_valid_game(self):
        model, errors = validate_payload("game", self._valid_game())
        assert model is not None
        assert errors == []

    def test_home_away_same_team_rejected(self):
        # Exclude winner_team_id so only the home==away model_validator fires
        model, errors = validate_payload("game", {
            "game_id": "0022400099",
            "game_date": "2026-01-15",
            "season": "2025-26",
            "home_team_id": 5,
            "away_team_id": 5,
            "is_completed": False,
        })
        assert model is None
        assert len(errors) > 0  # home==away validator must fire

    def test_winner_not_home_or_away_rejected(self):
        model, errors = validate_payload("game", self._valid_game(winner_team_id=999))
        assert model is None
        assert any("winner_team_id" in e for e in errors)

    def test_invalid_season_format(self):
        model, errors = validate_payload("game", self._valid_game(season="2025"))
        assert model is None

    def test_score_above_250_rejected(self):
        model, errors = validate_payload("game", self._valid_game(home_score=300))
        assert model is None

    def test_score_negative_rejected(self):
        model, errors = validate_payload("game", self._valid_game(away_score=-10))
        assert model is None

    def test_optional_fields_default_correctly(self):
        minimal = {
            "game_id": "0022400002",
            "game_date": "2026-01-16",
            "season": "2025-26",
            "home_team_id": 10,
            "away_team_id": 20,
        }
        model, errors = validate_payload("game", minimal)
        assert model is not None
        assert model.is_completed is False
        assert model.winner_team_id is None


# ── PlayerPayload ─────────────────────────────────────────────────────────────

class TestPlayerPayload:
    def test_valid_player(self):
        model, errors = validate_payload("player", {
            "player_id": 2544,
            "full_name": "LeBron James",
            "team_id": 1610612747,
            "position": "SF",
            "is_active": True,
        })
        assert model is not None
        assert errors == []

    def test_negative_player_id_rejected(self):
        model, errors = validate_payload("player", {
            "player_id": -5,
            "full_name": "Ghost Player",
        })
        assert model is None

    def test_minimal_player_valid(self):
        model, errors = validate_payload("player", {
            "player_id": 123,
            "full_name": "Test Player",
        })
        assert model is not None
        assert model.is_active is True  # default


# ── validate_payload edge cases ───────────────────────────────────────────────

class TestValidatePayload:
    def test_unknown_entity_type(self):
        model, errors = validate_payload("stadium", {"name": "MSG"})
        assert model is None
        assert "Unknown entity_type" in errors[0]


# ── validate_batch ────────────────────────────────────────────────────────────

class TestValidateBatch:
    def test_separates_valid_from_invalid(self):
        records = [
            {"team_id": 1, "abbreviation": "BOS", "full_name": "Boston Celtics"},
            {"team_id": -1, "abbreviation": "BAD", "full_name": "Bad Team"},  # invalid
            {"team_id": 2, "abbreviation": "MIA", "full_name": "Miami Heat"},
        ]
        valid, failed = validate_batch("team", records)
        assert len(valid) == 2
        assert len(failed) == 1
        assert "errors" in failed[0]
        assert "raw" in failed[0]

    def test_all_valid_batch(self):
        records = [
            {"team_id": i, "abbreviation": f"T{i:02d}", "full_name": f"Team {i}"}
            for i in range(1, 6)
        ]
        valid, failed = validate_batch("team", records)
        assert len(valid) == 5
        assert failed == []

    def test_all_invalid_batch(self):
        records = [
            {"team_id": -i, "abbreviation": "X", "full_name": "Y"}
            for i in range(1, 4)
        ]
        valid, failed = validate_batch("team", records)
        assert valid == []
        assert len(failed) == 3


# ── Dead-letter store (mocked DB) ────────────────────────────────────────────

class TestDeadLetterStore:
    """Tests for persist_failed_record and list_failed_records using a mock engine."""

    def _make_mock_engine(self, return_id=1):
        from unittest.mock import MagicMock
        mock_result = MagicMock()
        mock_result.scalar.return_value = return_id
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_engine = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: mock_conn
        ctx.__exit__ = MagicMock(return_value=False)
        mock_engine.begin.return_value = ctx
        return mock_engine

    def test_persist_failed_record_returns_id(self):
        from src.data.dead_letter import persist_failed_record

        engine = self._make_mock_engine(return_id=42)
        row_id = persist_failed_record(
            engine,
            entity_type="game",
            raw_payload={"game_id": "bad"},
            validation_errors=["game_id: too short"],
            source_module="ingestion",
        )
        assert row_id == 42

    def test_persist_failed_record_handles_db_error(self):
        from src.data.dead_letter import persist_failed_record
        from unittest.mock import MagicMock

        engine = MagicMock()
        engine.begin.side_effect = RuntimeError("DB down")

        row_id = persist_failed_record(
            engine,
            entity_type="team",
            raw_payload={},
            validation_errors=["some error"],
        )
        assert row_id is None

    def test_persist_failed_batch_counts_successes(self):
        from src.data.dead_letter import persist_failed_batch

        engine = self._make_mock_engine(return_id=10)
        failed_records = [
            {"raw": {"team_id": -1}, "errors": ["team_id: negative"]},
            {"raw": {"team_id": -2}, "errors": ["team_id: negative"]},
        ]
        count = persist_failed_batch(engine, failed_records, "team")
        assert count == 2
