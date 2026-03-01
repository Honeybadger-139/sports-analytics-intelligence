"""
Chatbot backend service — hybrid RAG + DB query engine.

Architecture:
    User message
        ↓
    IntentRouter  (keyword heuristics, no LLM call — fast)
        ├── rag       → ChromaDB retrieve context → LLM synthesise answer
        ├── db        → LLM writes SQL → safe execute → LLM narrates result
        └── off_topic → polite decline (no LLM call needed)

LLM Abstraction:
    All LLM calls are routed through LLMClient.
    To swap Gemini for Minimax (or any other provider) in the future,
    only modify LLMClient below — zero changes elsewhere.

Sport Extensibility:
    The service is designed around a `sport` parameter (default "nba").
    When new sports are added, extend _SPORT_TABLE_MAP and _DB_SCOPE_HINT
    per sport — the rest of the logic stays unchanged.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from src import config
from src.intelligence.embeddings import EmbeddingClient
from src.intelligence.retriever import ContextRetriever
from src.intelligence.vector_store import VectorStore

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

MAX_HISTORY_TURNS = 6      # Last N messages sent as conversation context to LLM
MAX_SQL_ROWS = 50          # Cap rows narrated by LLM (prevents huge prompts)
RAG_TOP_K = 5
_DECLINE_MSG = (
    "I'm focused on sports analytics — I can only answer questions about your NBA "
    "data (stats, standings, predictions, bankroll) or recent sports news and game context. "
    "What would you like to know?"
)

# Keywords that signal a question is about live DB data / analytics
_DB_KEYWORDS = frozenset([
    "stats", "statistics", "average", "win", "loss", "record", "rate", "ranking",
    "top", "best", "worst", "most", "least", "total", "how many", "count",
    "pts", "points", "assist", "rebound", "steal", "block", "performance",
    "season", "predict", "prediction", "model", "bankroll", "roi", "bet",
    "bets", "profit", "stake", "odds", "pg", "per game", "pace", "rating",
    "efg", "true shooting", "plus minus", "compare", "vs", "versus",
    "standings", "conference", "division", "roster",
])

# Keywords that signal the question is about news / game context / injuries
_RAG_KEYWORDS = frozenset([
    "injur", "injury", "hurt", "lineup", "available", "playing", "out",
    "questionable", "doubtful", "news", "report", "update", "latest",
    "preview", "context", "matchup", "game", "tonight", "today",
    "back-to-back", "travel", "rest", "fatigue", "trade", "sign",
    "rumour", "rumor", "headline", "article",
])

# Patterns that signal off-topic questions
_OFF_TOPIC_PATTERNS = [
    re.compile(r"\b(recipe|cook|movie|music|song|weather|stock|crypto|bitcoin|"
               r"politics|election|president|covid|vaccine|history|math|"
               r"capital of|translate|poem|essay|joke)\b", re.IGNORECASE),
]

# Whitelisted tables for NL→SQL (only raw data tables — no internal/audit tables)
_SQL_SAFE_TABLES = (
    "matches", "teams", "players",
    "team_game_stats", "player_game_stats", "player_season_stats",
    "match_features", "bets", "predictions",
)

_SQL_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|TRUNCATE|DROP|CREATE|ALTER|RENAME|GRANT|REVOKE"
    r"|EXECUTE|EXEC|CALL|DO|COPY|VACUUM|ANALYZE|CLUSTER|REINDEX|REFRESH)\b",
    re.IGNORECASE,
)
_SQL_SELECT = re.compile(r"^\s*SELECT\b", re.IGNORECASE)


# ── LLM Client (swap this class to change LLM provider) ─────────────────────

class LLMClient:
    """
    Thin wrapper around the LLM provider.

    CURRENT PROVIDER: Google Gemini (gemini-2.0-flash)

    TO SWITCH TO MINIMAX (or any other provider):
        1. Replace the import and `_call` implementation below.
        2. Keep the public interface: `generate(prompt, system, max_tokens) -> str`
        3. No other file needs to change.
    """

    def __init__(self) -> None:
        self._genai = None
        self._model_name = config.RAG_SUMMARY_MODEL
        if config.GEMINI_API_KEY:
            try:
                import google.generativeai as genai  # type: ignore
                genai.configure(api_key=config.GEMINI_API_KEY)
                self._genai = genai
                logger.info("LLMClient: Gemini %s ready", self._model_name)
            except Exception as exc:
                logger.warning("LLMClient: Gemini unavailable — %s", exc)

    @property
    def available(self) -> bool:
        return self._genai is not None

    def generate(self, prompt: str, *, max_tokens: int = 400) -> Optional[str]:
        """Generate a text response. Returns None if LLM is unavailable."""
        if not self._genai:
            return None
        try:
            model = self._genai.GenerativeModel(self._model_name)  # type: ignore[union-attr]
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.25, "max_output_tokens": max_tokens},
            )
            text = (response.text or "").strip()
            return text if text else None
        except Exception as exc:
            logger.warning("LLMClient.generate failed: %s", exc)
            return None


# ── Intent Router ────────────────────────────────────────────────────────────

class IntentRouter:
    """
    Keyword-based intent classifier — no LLM call, runs in microseconds.

    Returns one of: 'rag' | 'db' | 'off_topic'
    """

    @staticmethod
    def route(message: str) -> str:
        lower = message.lower()

        # 1. Off-topic guard
        for pattern in _OFF_TOPIC_PATTERNS:
            if pattern.search(lower):
                return "off_topic"

        # 2. Score RAG vs DB keyword hits
        rag_score = sum(1 for kw in _RAG_KEYWORDS if kw in lower)
        db_score  = sum(1 for kw in _DB_KEYWORDS  if kw in lower)

        if rag_score == 0 and db_score == 0:
            # Ambiguous — default to DB (richer data source for this platform)
            return "db"

        if rag_score > db_score:
            return "rag"

        return "db"


# ── DB Schema Helper ─────────────────────────────────────────────────────────

def _fetch_schema_context(db: Session) -> str:
    """
    Fetch actual column names from information_schema for whitelisted tables.
    Gives the LLM an accurate schema to generate valid SQL.
    """
    parts: List[str] = []
    for table in _SQL_SAFE_TABLES:
        try:
            rows = db.execute(
                text("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = :t AND table_schema = 'public'
                    ORDER BY ordinal_position
                """),
                {"t": table},
            ).fetchall()
            if rows:
                cols = ", ".join(f"{r[0]}" for r in rows)
                parts.append(f"  {table}({cols})")
        except Exception:
            pass
    return "\n".join(parts)


def _extract_sql(text_: str) -> str:
    """Extract a SQL block from an LLM response that may wrap it in markdown."""
    # Try ```sql ... ``` block
    match = re.search(r"```(?:sql)?\s*([\s\S]+?)```", text_, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Try first SELECT ... up to first blank line or end
    match = re.search(r"(SELECT[\s\S]+?)(?:\n\n|$)", text_, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text_.strip()


def _validate_sql(sql: str) -> Tuple[bool, str]:
    """Returns (valid, error_message)."""
    sql = sql.strip().rstrip(";")
    if not _SQL_SELECT.match(sql):
        return False, "Generated query is not a SELECT statement."
    if _SQL_FORBIDDEN.search(sql):
        return False, "Generated query contains forbidden keywords."
    return True, ""


def _cap_limit(sql: str, max_rows: int = MAX_SQL_ROWS) -> str:
    """Enforce a LIMIT on the query."""
    limit_re = re.compile(r"\bLIMIT\s+(\d+)", re.IGNORECASE)
    sql = sql.rstrip(";").rstrip()
    match = limit_re.search(sql)
    if match:
        existing = int(match.group(1))
        if existing > max_rows:
            return limit_re.sub(f"LIMIT {max_rows}", sql)
        return sql
    return f"{sql}\nLIMIT {max_rows}"


# ── Chat Service ─────────────────────────────────────────────────────────────

class ChatService:
    """
    Orchestrates the hybrid chatbot: RAG path + DB path + off-topic gate.

    Parameters
    ----------
    db      : SQLAlchemy Session
    sport   : Sport slug — currently 'nba'. Extend for future sports without
              changing the public interface.
    """

    def __init__(self, db: Session, sport: str = "nba") -> None:
        self.db = db
        self.sport = sport
        self.llm = LLMClient()
        self._embedding_client = EmbeddingClient()
        self._vector_store = VectorStore()
        self._retriever = ContextRetriever(self._embedding_client, self._vector_store)
        self._schema_context: Optional[str] = None  # Lazy-loaded

    def _get_schema(self) -> str:
        if self._schema_context is None:
            self._schema_context = _fetch_schema_context(self.db)
        return self._schema_context

    # ── History formatting ────────────────────────────────────────────────

    @staticmethod
    def _format_history(history: List[Dict[str, str]], max_turns: int = MAX_HISTORY_TURNS) -> str:
        recent = history[-(max_turns * 2):]
        lines = []
        for msg in recent:
            role = msg.get("role", "user")
            prefix = "User" if role == "user" else "Assistant"
            lines.append(f"{prefix}: {msg.get('content', '')}")
        return "\n".join(lines)

    # ── Off-topic ─────────────────────────────────────────────────────────

    def _decline(self) -> str:
        return _DECLINE_MSG

    # ── RAG path ──────────────────────────────────────────────────────────

    def _rag_reply(self, message: str, history: List[Dict[str, str]]) -> str:
        """Retrieve recent sports news/context from ChromaDB, then synthesise an answer."""
        try:
            docs, _ = self._retriever.retrieve(
                message,
                top_k=RAG_TOP_K,
                max_age_hours=config.RAG_MAX_AGE_HOURS,
            )
        except Exception as exc:
            logger.warning("RAG retrieval failed: %s", exc)
            docs = []

        if not docs:
            return (
                "I don't have recent news or context documents indexed for that topic. "
                "The context store may be empty or the RSS feeds haven't been fetched yet. "
                "Try asking a stats question instead — I can query your live Postgres data directly."
            )

        # Build context blob
        snippets = []
        for i, doc in enumerate(docs[:5], 1):
            snippets.append(
                f"{i}. [{doc.get('source', 'source')}] "
                f"{doc.get('title', '')} — {doc.get('content', '')[:300]}"
            )
        context_blob = "\n".join(snippets)
        history_str = self._format_history(history)

        if not self.llm.available:
            # Deterministic fallback
            titles = "; ".join(d.get("title", "update") for d in docs[:3] if d.get("title"))
            return (
                f"Recent sports context: {titles}. "
                "Add your GEMINI_API_KEY to backend/.env for richer AI-generated answers."
            )

        prompt = (
            f"You are a Sports Analytics AI assistant for an NBA analytics platform.\n"
            f"Answer ONLY sports analytics questions. Decline anything unrelated.\n"
            f"Use the context snippets below to answer the user's question.\n"
            f"If the context doesn't answer the question, say so clearly.\n"
            f"Keep your answer concise (3-5 sentences).\n\n"
            f"{'Conversation so far:' + chr(10) + history_str + chr(10) if history_str else ''}"
            f"Retrieved context:\n{context_blob}\n\n"
            f"User: {message}\nAssistant:"
        )
        reply = self.llm.generate(prompt, max_tokens=300)
        return reply or self._rag_fallback(docs)

    @staticmethod
    def _rag_fallback(docs: List[Dict]) -> str:
        titles = "; ".join(d.get("title", "update") for d in docs[:3] if d.get("title"))
        return f"Recent context: {titles}." if titles else "No recent context available."

    # ── DB path ───────────────────────────────────────────────────────────

    def _db_reply(self, message: str, history: List[Dict[str, str]]) -> str:
        """
        Natural language → SQL → execute → narrate.

        Step 1: Ask LLM to write a SELECT query.
        Step 2: Validate + cap the query.
        Step 3: Execute against Postgres.
        Step 4: Ask LLM to narrate the result in plain English.
        """
        schema = self._get_schema()
        history_str = self._format_history(history)

        # ── Step 1: Generate SQL ──────────────────────────────────────────
        if self.llm.available:
            sql_prompt = (
                f"You are a PostgreSQL expert for a sports analytics platform (currently NBA, "
                f"may include other sports in future).\n"
                f"Generate ONE valid SELECT query to answer the user's question.\n"
                f"Rules:\n"
                f"- Only use tables and columns from the schema below.\n"
                f"- Only SELECT — no INSERT, UPDATE, DELETE, or DDL.\n"
                f"- Add sensible JOINs for readable output (e.g. team abbreviations).\n"
                f"- Default to season '2025-26' unless the user specifies otherwise.\n"
                f"- Include ORDER BY and LIMIT clauses for large tables.\n"
                f"- Return ONLY the SQL, no explanation.\n\n"
                f"Schema:\n{schema}\n\n"
                f"{'Context:' + chr(10) + history_str + chr(10) if history_str else ''}"
                f"Question: {message}\n"
                f"SQL:"
            )
            raw_sql = self.llm.generate(sql_prompt, max_tokens=300)
        else:
            raw_sql = None

        if not raw_sql:
            return self._db_fallback(message)

        sql = _extract_sql(raw_sql)
        valid, err = _validate_sql(sql)
        if not valid:
            logger.warning("ChatService: invalid generated SQL (%s): %s", err, sql)
            return self._db_fallback(message)

        sql = _cap_limit(sql)

        # ── Step 2: Execute ───────────────────────────────────────────────
        try:
            result = self.db.execute(text(sql))
            columns = list(result.keys())
            raw_rows = result.fetchall()
            rows: List[Dict[str, Any]] = [
                {col: (str(v) if v is not None and not isinstance(v, (int, float, bool, str)) else v)
                 for col, v in zip(columns, row)}
                for row in raw_rows
            ]
        except Exception as exc:
            logger.warning("ChatService: SQL execution failed: %s\nSQL: %s", exc, sql)
            # Provide a user-friendly error instead of crashing
            return (
                "I tried to query your data but hit a database error. "
                "Could you rephrase the question? "
                f"_(Technical detail: {str(exc)[:120]})_"
            )

        if not rows:
            return "I ran the query but found no matching data for that question in your database."

        # ── Step 3: Narrate ───────────────────────────────────────────────
        # Build a compact table string for the LLM
        header = " | ".join(columns)
        data_rows = "\n".join(
            " | ".join(str(row.get(c, "")) for c in columns)
            for row in rows[:20]  # Show up to 20 rows in the narration prompt
        )
        table_str = f"{header}\n{data_rows}"

        narrate_prompt = (
            f"You are a Sports Analytics AI assistant.\n"
            f"The user asked: \"{message}\"\n"
            f"A SQL query returned these results:\n\n"
            f"{table_str}\n\n"
            f"{'There are ' + str(len(rows)) + ' rows total. ' if len(rows) > 20 else ''}"
            f"Summarise the key findings in 2-4 plain-English sentences. "
            f"Be specific — mention numbers, team names, and player names from the data. "
            f"Do not describe the query itself, just the answer.\n"
            f"Assistant:"
        )
        reply = self.llm.generate(narrate_prompt, max_tokens=250)
        return reply or self._rows_fallback(columns, rows)

    @staticmethod
    def _rows_fallback(columns: List[str], rows: List[Dict]) -> str:
        """Plain-text table when LLM is unavailable."""
        if not rows:
            return "No results found."
        header = " | ".join(columns)
        lines = [header, "-" * len(header)]
        for row in rows[:10]:
            lines.append(" | ".join(str(row.get(c, "")) for c in columns))
        suffix = f"\n… and {len(rows) - 10} more rows." if len(rows) > 10 else ""
        return f"```\n{chr(10).join(lines)}{suffix}\n```\n\n_Add GEMINI_API_KEY to backend/.env for AI-narrated answers._"

    @staticmethod
    def _db_fallback(message: str) -> str:
        return (
            "I couldn't generate a database query for that question. "
            "Try rephrasing — for example: \"What are the top 10 scorers this season?\" "
            "or \"Show me the Lakers' win rate in 2025-26.\""
        )

    # ── Public Interface ──────────────────────────────────────────────────

    def reply(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Generate a chatbot reply.

        Parameters
        ----------
        message : The user's latest message.
        history : Previous conversation turns [{role, content}, ...].

        Returns
        -------
        str : The assistant's reply.
        """
        history = history or []
        intent = IntentRouter.route(message)

        logger.info("ChatService.reply: intent=%s sport=%s", intent, self.sport)

        if intent == "off_topic":
            return self._decline()
        if intent == "rag":
            return self._rag_reply(message, history)
        return self._db_reply(message, history)
