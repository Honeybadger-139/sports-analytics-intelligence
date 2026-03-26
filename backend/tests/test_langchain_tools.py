"""
Unit tests for LangChain tools and output schemas.

Tests are designed to run without a live DB or LLM — all DB/LLM calls
are mocked. This validates the tool interface contract, not the underlying
service logic (which has its own tests).

Run:  pytest backend/tests/test_langchain_tools.py -v

Part of: SCR-317 — Module 6.1 LangChain/LangGraph Enhancement
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from src.intelligence.output_schemas import (
    Citation,
    GameAnalysis,
    KeyFactor,
    RAGResponse,
    StatsSummary,
    ToolResult,
)


# ── Output Schema Tests ───────────────────────────────────────────────────────


class TestGameAnalysis:
    def test_valid_construction(self):
        ga = GameAnalysis(
            home_team="Lakers",
            away_team="Warriors",
            home_win_probability=0.62,
            away_win_probability=0.38,
            confidence=0.75,
            narrative="Lakers favoured at home.",
        )
        assert ga.home_team == "Lakers"
        assert ga.home_win_probability == 0.62
        assert ga.away_win_probability == 0.38

    def test_probability_clamping(self):
        """Values outside [0,1] should be clamped."""
        ga = GameAnalysis(
            home_team="Lakers",
            away_team="Warriors",
            home_win_probability=1.5,   # too high
            away_win_probability=-0.1,  # too low
        )
        assert ga.home_win_probability == 1.0
        assert ga.away_win_probability == 0.0

    def test_default_narrative(self):
        ga = GameAnalysis(
            home_team="Celtics",
            away_team="Heat",
            home_win_probability=0.55,
            away_win_probability=0.45,
        )
        assert ga.narrative == ""
        assert ga.key_factors == []

    def test_key_factors(self):
        ga = GameAnalysis(
            home_team="Celtics",
            away_team="Heat",
            home_win_probability=0.55,
            away_win_probability=0.45,
            key_factors=[
                KeyFactor(factor="home_court", value=0.15, direction="positive"),
                KeyFactor(factor="back_to_back", value=-0.08, direction="negative"),
            ],
        )
        assert len(ga.key_factors) == 2
        assert ga.key_factors[0].factor == "home_court"


class TestStatsSummary:
    def test_valid_construction(self):
        ss = StatsSummary(
            metric_name="Points Per Game",
            value=114.3,
            unit="pts/game",
            trend="up",
            context="3rd in Western Conference",
            team="Lakers",
        )
        assert ss.value == 114.3
        assert ss.trend == "up"

    def test_invalid_trend_defaults_to_stable(self):
        ss = StatsSummary(metric_name="PPG", value=100.0, trend="sideways")
        assert ss.trend == "stable"

    def test_default_rows(self):
        ss = StatsSummary(metric_name="PPG", value=100.0)
        assert ss.rows == []


class TestRAGResponse:
    def test_from_retrieval_high_quality(self):
        docs = [
            {"title": "Lakers injury update", "url": "http://espn.com/1", "source": "ESPN", "score": 0.9},
            {"title": "LeBron day-to-day", "url": "http://nba.com/2", "source": "NBA", "score": 0.85},
            {"title": "Davis playing tonight", "url": "", "source": "CBS", "score": 0.8},
            {"title": "Lineup confirmed", "url": "http://espn.com/3", "source": "ESPN", "score": 0.75},
        ]
        meta = {"docs_used": 4}
        resp = RAGResponse.from_retrieval("LeBron is questionable.", docs, meta)
        assert resp.source_quality == "high"
        assert resp.confidence >= 0.85
        assert len(resp.citations) == 4

    def test_from_retrieval_low_quality(self):
        docs = [{"title": "News", "source": "ESPN", "score": 0.3}]
        meta = {"docs_used": 1}
        resp = RAGResponse.from_retrieval("No info.", docs, meta)
        assert resp.source_quality == "low"
        assert resp.confidence < 0.5

    def test_invalid_source_quality_defaults(self):
        resp = RAGResponse(answer="test", source_quality="excellent")
        assert resp.source_quality == "medium"


class TestToolResult:
    def test_success_result(self):
        tr = ToolResult(tool_name="sql_query_tool", success=True, text="Lakers are 45-20")
        assert tr.success is True
        assert tr.error is None

    def test_error_result(self):
        tr = ToolResult(tool_name="sql_query_tool", success=False, error="DB unreachable")
        assert tr.success is False
        assert "DB unreachable" in tr.error


# ── LangChain Tool Tests ──────────────────────────────────────────────────────


class TestSQLQueryTool:
    def test_tool_name_and_description(self):
        from src.intelligence.langchain_tools import SQLQueryTool
        mock_db = MagicMock()
        tool = SQLQueryTool(db=mock_db)
        assert tool.name == "sql_query_tool"
        assert "NBA" in tool.description
        assert "database" in tool.description.lower()

    def test_run_returns_string(self):
        from src.intelligence.langchain_tools import SQLQueryTool
        mock_db = MagicMock()
        tool = SQLQueryTool(db=mock_db)

        with patch("src.intelligence.langchain_tools.ChatService") as MockSvc:
            instance = MockSvc.return_value
            instance._db_reply.return_value = ("Lakers lead with 31.4 PPG", {"rows_returned": 5})
            result = tool._run("Who leads in scoring?")

        assert "Lakers" in result

    def test_run_handles_exception_gracefully(self):
        from src.intelligence.langchain_tools import SQLQueryTool
        mock_db = MagicMock()
        tool = SQLQueryTool(db=mock_db)

        with patch("src.intelligence.langchain_tools.ChatService") as MockSvc:
            MockSvc.side_effect = RuntimeError("DB connection failed")
            result = tool._run("Who leads?")

        assert "failed" in result.lower() or "error" in result.lower()


class TestRAGRetrieverTool:
    def test_tool_name(self):
        from src.intelligence.langchain_tools import RAGRetrieverTool
        mock_db = MagicMock()
        tool = RAGRetrieverTool(db=mock_db)
        assert tool.name == "rag_retriever_tool"

    def test_run_no_docs_returns_fallback(self):
        from src.intelligence.langchain_tools import RAGRetrieverTool
        mock_db = MagicMock()
        tool = RAGRetrieverTool(db=mock_db)

        with patch("src.intelligence.langchain_tools.ChatService") as MockSvc:
            instance = MockSvc.return_value
            instance._retriever.retrieve.return_value = ([], {"docs_used": 0})
            result = tool._run("Is LeBron playing tonight?")

        assert "No recent news" in result or "Try asking" in result


class TestTeamStatsTool:
    def test_tool_name(self):
        from src.intelligence.langchain_tools import TeamStatsTool
        mock_db = MagicMock()
        tool = TeamStatsTool(db=mock_db)
        assert tool.name == "team_stats_tool"

    def test_run_with_mock_db(self):
        from src.intelligence.langchain_tools import TeamStatsTool
        mock_db = MagicMock()
        tool = TeamStatsTool(db=mock_db)

        mock_row = ("Los Angeles Lakers", 45, 20, 116.3, 44.5, 27.2, 47.8)
        mock_db.execute.return_value.fetchone.return_value = mock_row

        result = tool._run("Lakers")
        assert "Lakers" in result
        assert "45" in result  # wins

    def test_run_no_team_found(self):
        from src.intelligence.langchain_tools import TeamStatsTool
        mock_db = MagicMock()
        tool = TeamStatsTool(db=mock_db)
        mock_db.execute.return_value.fetchone.return_value = None

        result = tool._run("NonExistentTeam")
        assert "No stats found" in result


class TestCreateTools:
    def test_create_tools_returns_5_tools(self):
        from src.intelligence.langchain_tools import create_tools
        mock_db = MagicMock()
        tools = create_tools(mock_db, sport="nba")
        assert len(tools) == 5

    def test_tool_names(self):
        from src.intelligence.langchain_tools import create_tools
        mock_db = MagicMock()
        tools = create_tools(mock_db)
        names = {t.name for t in tools}
        expected = {
            "sql_query_tool",
            "rag_retriever_tool",
            "team_stats_tool",
            "prediction_tool",
            "explainability_tool",
        }
        assert names == expected

    def test_get_tool_map_keyed_by_name(self):
        from src.intelligence.langchain_tools import get_tool_map
        mock_db = MagicMock()
        tool_map = get_tool_map(mock_db)
        assert "sql_query_tool" in tool_map
        assert "prediction_tool" in tool_map


# ── ChatMemory Tests ──────────────────────────────────────────────────────────


class TestChatMemory:
    def _make_memory(self):
        from src.intelligence.memory import ChatMemory
        mock_db = MagicMock()
        # Simulate fetchall returning empty list by default
        mock_db.execute.return_value.fetchall.return_value = []
        mock_db.execute.return_value.fetchone.return_value = None
        return ChatMemory(db=mock_db), mock_db

    def test_get_history_empty_session(self):
        memory, _ = self._make_memory()
        history = memory.get_history("session-abc")
        assert history == []

    def test_get_history_no_session_id(self):
        memory, _ = self._make_memory()
        history = memory.get_history("")
        assert history == []

    def test_add_message_skips_empty_content(self):
        memory, mock_db = self._make_memory()
        memory.add_message("session-abc", "user", "")
        mock_db.execute.assert_not_called()

    def test_add_message_commits(self):
        memory, mock_db = self._make_memory()
        memory.add_message("session-abc", "user", "Who leads in scoring?")
        mock_db.commit.assert_called()

    def test_get_history_maps_rows_correctly(self):
        memory, mock_db = self._make_memory()
        mock_db.execute.return_value.fetchall.return_value = [
            ("assistant", "Lakers lead with 31 PPG"),
            ("user", "What about assists?"),
        ]
        history = memory.get_history("session-abc")
        # Should be reversed (chronological)
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
