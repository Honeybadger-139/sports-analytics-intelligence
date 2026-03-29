"""
Tests for deterministic NL->SQL fallback templates in ChatService.
"""

import pytest

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
        if "previous_win_rate" in sql and "improvement" in sql:
            return _FakeResult(
                ["full_name", "abbreviation", "current_win_rate", "previous_win_rate", "improvement", "current_wins", "previous_wins"],
                [("Oklahoma City Thunder", "OKC", 0.70, 0.54, 0.16, 56, 44)],
            )
        if "FROM teams" in sql and "win_rate" in sql:
            return _FakeResult(
                ["full_name", "abbreviation", "wins", "games_played", "win_rate"],
                [("Los Angeles Lakers", "LAL", 30, 50, 0.6)],
            )
        if "assists_per_game" in sql and "player_season_stats" in sql:
            return _FakeResult(
                ["full_name", "abbreviation", "position", "games_played", "assists_per_game", "total_assists"],
                [("Tyrese Haliburton", "IND", "PG", 70, 10.9, 763)],
            )
        if "avg_points" in sql and "players_count" in sql:
            return _FakeResult(
                ["team_name", "players_count", "avg_points", "avg_rebounds", "avg_assists", "avg_steals", "avg_blocks"],
                [("Boston Celtics", 14, 11.42, 4.78, 2.63, 0.78, 0.61)],
            )
        return _FakeResult([], [])


class _FakeLLMUnavailable:
    available = False


class _FakeLLMReturnsBadButValidSQL:
    available = True

    def generate(self, *args, **kwargs):  # noqa: ARG002 - parity with LLM interface
        return "SELECT 1 AS value LIMIT 1"


class _FakeRetrieverEmpty:
    def retrieve(self, *args, **kwargs):
        return [], {"docs_used": 0}


def _build_service_with_fake_db(fake_db):
    service = ChatService.__new__(ChatService)
    service.db = fake_db
    service.sport = "nba"
    service.llm = _FakeLLMUnavailable()
    service._schema_context = "matches(game_id, season, home_team_id, away_team_id, winner_team_id)\nteams(team_id, full_name, abbreviation)"
    return service


def _build_service_with_empty_rag():
    service = ChatService.__new__(ChatService)
    service._retriever = _FakeRetrieverEmpty()
    service.llm = _FakeLLMUnavailable()
    return service


def _build_service_with_bad_llm_and_fake_db(fake_db):
    service = _build_service_with_fake_db(fake_db)
    service.llm = _FakeLLMReturnsBadButValidSQL()
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


def test_rule_based_sql_generates_record_query_for_specific_team():
    sql = ChatService._rule_based_sql("Show me the Lakers' record in 2025-26")
    assert sql is not None
    assert "SUM(CASE WHEN m.winner_team_id = t.team_id THEN 1 ELSE 0 END) AS wins" in sql
    assert "SUM(CASE WHEN m.winner_team_id IS NOT NULL AND m.winner_team_id <> t.team_id THEN 1 ELSE 0 END) AS losses" in sql
    assert "m.season = '2025-26'" in sql
    assert "lakers" in sql.lower()


def test_rule_based_sql_generates_season_over_season_improvement_query():
    sql = ChatService._rule_based_sql("Which teams have improved the most from last season?")
    assert sql is not None
    assert "season_team_results" in sql
    assert "improvement" in sql
    assert "('2025-26', '2024-25')" in sql
    assert "ORDER BY improvement DESC" in sql
    assert "LIMIT 10" in sql


def test_rule_based_sql_generates_top_point_guards_assist_comparison():
    sql = ChatService._rule_based_sql("Compare assists per game for the top 5 point guards")
    assert sql is not None
    assert "assists_per_game" in sql
    assert "p.position" in sql
    assert "LIMIT 5" in sql


@pytest.mark.parametrize(
    "message",
    [
        "Compare assists per game for the top 5 point guards",
        "Top 5 guards by assists per game this season",
    ],
)
def test_rule_based_sql_recognizes_point_guard_assist_variants(message):
    sql = ChatService._rule_based_sql(message)
    assert sql is not None
    assert "assists_per_game" in sql
    assert "COALESCE(p.position" in sql
    assert "LIMIT 5" in sql


def test_rule_based_sql_generates_team_average_player_stats_query():
    sql = ChatService._rule_based_sql("What are the average player stats for the Celtics this season?")
    assert sql is not None
    assert "AVG(pss.points)" in sql
    assert "AVG(pss.rebounds)" in sql
    assert "AVG(pss.assists)" in sql
    assert "celtics" in sql.lower()


def test_db_reply_uses_deterministic_sql_when_llm_is_unavailable():
    fake_db = _FakeDB()
    service = _build_service_with_fake_db(fake_db)

    reply = service._db_reply("Show me the Lakers' win rate in 2025-26.", history=[])

    assert "Los Angeles Lakers" in reply
    assert any("FROM teams" in sql for sql in fake_db.executed)


def test_db_reply_uses_deterministic_sql_for_improvement_question_when_llm_unavailable():
    fake_db = _FakeDB()
    service = _build_service_with_fake_db(fake_db)

    reply = service._db_reply("Which teams have improved the most from last season?", history=[])

    assert "Oklahoma City Thunder" in reply
    assert any("improvement" in sql.lower() for sql in fake_db.executed)


def test_db_reply_prefers_point_guard_rule_sql_even_with_available_llm():
    fake_db = _FakeDB()
    service = _build_service_with_bad_llm_and_fake_db(fake_db)

    reply, meta = service._db_reply(
        "Compare assists per game for the top 5 point guards",
        history=[],
        return_meta=True,
    )

    assert isinstance(reply, str)
    assert meta["sql_used"] is not None
    assert "player_season_stats" in meta["sql_used"]
    assert "assists_per_game" in meta["sql_used"]
    assert meta["rows_returned"] == 1


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


@pytest.mark.parametrize(
    ("message", "expected_snippet"),
    [
        ("Any injury updates for tonight's games?", "injury-report context indexed yet"),
        ("What are the latest trade updates for the Lakers?", "trade-rumor context indexed yet"),
        ("What games are scheduled tomorrow?", "upcoming schedule previews indexed yet"),
        ("Tell me the latest context on the Celtics.", "recent news or context documents indexed"),
    ],
)
def test_rag_reply_uses_sub_intent_specific_no_docs_fallback(message, expected_snippet):
    service = _build_service_with_empty_rag()

    reply = service._rag_reply(message, history=[])

    assert expected_snippet in reply


def test_rag_reply_triggers_guarded_refresh_on_empty_context(monkeypatch):
    service = _build_service_with_empty_rag()
    called = {}

    def _fake_trigger(*, reason):
        called["reason"] = reason
        return True

    monkeypatch.setattr("src.intelligence.chat_service.trigger_guarded_rag_refresh", _fake_trigger)

    reply = service._rag_reply("Any injury updates for tonight's games?", history=[])

    assert "injury-report context indexed yet" in reply
    assert called["reason"] == "rag_empty:injury"
