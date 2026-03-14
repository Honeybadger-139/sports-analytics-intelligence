"""
Tests for temporal train/validation splitting in the trainer.
"""

import pandas as pd

from src.models import trainer as trainer_module


def test_load_training_dataset_enforces_cutoff_and_validation_season(monkeypatch):
    sample_df = pd.DataFrame(
        [
            {
                "game_id": "old-train",
                "game_date": "2025-01-10",
                "season": "2024-25",
                "home_win": 1,
                **{feature: 1.0 for feature in trainer_module.FEATURE_COLUMNS},
            },
            {
                "game_id": "recent-train",
                "game_date": "2025-03-10",
                "season": "2024-25",
                "home_win": 0,
                **{feature: 2.0 for feature in trainer_module.FEATURE_COLUMNS},
            },
            {
                "game_id": "validation-game",
                "game_date": "2026-01-05",
                "season": "2025-26",
                "home_win": 1,
                **{feature: 3.0 for feature in trainer_module.FEATURE_COLUMNS},
            },
        ]
    )

    monkeypatch.setattr(trainer_module.pd, "read_sql", lambda *args, **kwargs: sample_df.copy())

    class _FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeEngine:
        def connect(self):
            return _FakeConnection()

    dataset = trainer_module.load_training_dataset(
        _FakeEngine(),
        season="2024-25",
        cutoff_date="2025-06-01",
        validation_season="2025-26",
    )

    assert list(dataset["train_y"]) == [1, 0]
    assert list(dataset["validation_y"]) == [1]
    assert dataset["metadata"]["cutoff_date"] == "2025-06-01"
    assert dataset["metadata"]["validation_season"] == "2025-26"
    assert dataset["metadata"]["training_games"] == 2
    assert dataset["metadata"]["validation_games"] == 1
