from datetime import date

from fastapi.testclient import TestClient

from main import app
from src.api import forecast_routes
from src.data.db import get_db
from src.models.bayesian_ratings import load_ratings_from_db
from src.models.timeseries_forecaster import TeamPerformanceForecaster


client = TestClient(app)


def test_load_ratings_from_db_uses_full_name_columns():
    class _FakeDB:
        def execute(self, query, _params=None):
            q = str(query)
            assert "home_t.full_name AS home_team" in q
            assert "away_t.full_name AS away_team" in q
            assert "team_name" not in q
            return type("_Res", (), {"fetchall": lambda self: [("Boston Celtics", "Miami Heat", True), ("Miami Heat", "Boston Celtics", False)]})()

    ratings = load_ratings_from_db(_FakeDB(), season="2025-26")
    assert ratings.is_fitted is True
    assert len(ratings.get_rankings(top_n=2)) == 2


def test_team_game_loader_uses_supported_team_columns():
    class _FakeDB:
        def execute(self, query, _params=None):
            q = str(query)
            assert "LOWER(t.full_name) LIKE LOWER(:team)" in q
            assert "LOWER(t.abbreviation) LIKE LOWER(:team)" in q
            assert "LOWER(t.city) LIKE LOWER(:team)" in q
            assert "LOWER(t.team_name)" not in q
            return type("_Res", (), {"fetchall": lambda self: [(date(2026, 3, 1), True), (date(2026, 3, 3), False)]})()

    df = TeamPerformanceForecaster._load_team_games(_FakeDB(), team_name="Celtics", season="2025-26")
    assert df is not None
    assert len(df) == 2


def test_league_momentum_endpoint_uses_full_name_column():
    class _FakeDB:
        def execute(self, query, _params=None):
            q = str(query)
            assert "t.full_name" in q
            assert "t.team_name" not in q
            rows = [
                ("Boston Celtics", date(2026, 3, 20), True),
                ("Boston Celtics", date(2026, 3, 22), True),
                ("Miami Heat", date(2026, 3, 20), False),
                ("Miami Heat", date(2026, 3, 22), True),
            ]
            return type("_Res", (), {"fetchall": lambda self: rows})()

    def _override_get_db():
        yield _FakeDB()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        response = client.get("/api/v1/forecast/league/momentum?season=2025-26")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["n_teams"] == 2
    assert payload["teams"][0]["team"] in {"Boston Celtics", "Miami Heat"}

