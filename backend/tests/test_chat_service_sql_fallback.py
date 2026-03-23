"""
Tests for deterministic NL->SQL fallback templates in ChatService.
"""

from src.intelligence.chat_service import ChatService


class _FakeResult:
    def __init__(self, columns, rows):
        self._columns = columns
        self._rows = rows

    def keys(self):
        return self._columns

    def fetchall(self):
        return self._rows


class _FakeDB:
    def __init__(self):
        self.executed = []

    def execute(self, query):
        sql = str(query)
        self.executed.append(sql)
        if "FROM teams" in sql and "win_rate" in sql:
            return _FakeResult(
                ["full_name", "abbreviation", "wins", "games_played", "win_rate"],
                [("Los Angeles Lakers", "LAL", 30, 50, 0.6)],
            )
        return _FakeResult([], [])


class _FakeLLMUnavailable:
    available = False


def _build_service_with_fake_db(fake_db):
    service = ChatService.__new__(ChatService)
    service.db = fake_db
    service.sport = "nba"
    service.llm = _FakeLLMUnavailable()
    service._schema_context = "matches(game_id, season, home_team_id, away_team_id, winner_team_id)\nteams(team_id, full_name, abbreviation)"
    return service


def test_rule_based_sql_handles_team_win_rate_phrase():
    sql = ChatService._rule_based_sql("Show me the Lakers' win rate in 2025-26.")
    assert sql is not None
    assert "FROM teams" in sql
    assert "m.season = '2025-26'" in sql
    assert "lakers" in sql.lower()


def test_rule_based_sql_generates_leaderboard_for_generic_win_rate_question():
    sql = ChatService._rule_based_sql("Which team has the best win rate this season?")
    assert sql is not None
    assert "ORDER BY win_rate DESC" in sql
    assert "LIMIT 10" in sql


def test_db_reply_uses_deterministic_sql_when_llm_is_unavailable():
    fake_db = _FakeDB()
    service = _build_service_with_fake_db(fake_db)

    reply = service._db_reply("Show me the Lakers' win rate in 2025-26.", history=[])

    assert "Los Angeles Lakers" in reply
    assert any("FROM teams" in sql for sql in fake_db.executed)


def test_reply_blocks_runtime_web_search_requests():
    service = ChatService.__new__(ChatService)
    service.sport = "nba"
    service.last_metadata = {}

    reply = service.reply("search the web for NBA trade rumors", history=[])

    assert "Runtime web search is disabled" in reply
    assert service.last_metadata["policy_decision"] == "blocked"
    assert service.last_metadata["external_calls_made"] == 0


def test_response_metadata_switches_to_table_mode_for_comparison_questions():
    service = ChatService.__new__(ChatService)
    payload = service._build_response_metadata(
        message="Compare the top 5 teams by win rate",
        answer="Comparison ready",
        intent="db",
        policy_decision="allowed",
        policy_reason="sports_analytics_scope",
        meta={
            "tool_path": "sql_tool",
            "table": {"columns": ["team", "win_rate"], "rows": [{"team": "A", "win_rate": 0.7}], "row_count": 1},
            "key_numbers": [{"label": "win_rate", "value": 0.7}],
            "confidence": 0.8,
        },
    )
    assert payload["format_mode"] == "table_first"
    assert payload["tool_path"] == "sql_tool->format_tool"
