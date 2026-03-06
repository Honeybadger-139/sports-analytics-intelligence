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
from src.intelligence.langfuse_client import (
    init_langfuse,
    observe,
    record_generation,
    set_session_context,
)
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
# Also includes forward-looking schedule keywords — upcoming games are NOT in
# the Postgres DB (only completed games are stored), so RAG (ESPN/CBS news)
# is the only source that can answer questions about tomorrow's fixtures.
_RAG_KEYWORDS = frozenset([
    "injur", "injury", "hurt", "lineup", "available", "playing", "out",
    "questionable", "doubtful", "news", "report", "update", "latest",
    "preview", "context", "matchup", "game", "tonight", "today",
    "back-to-back", "travel", "rest", "fatigue", "trade", "sign",
    "rumour", "rumor", "headline", "article",
    # Forward-looking / schedule keywords → route to RAG not DB
    "tomorrow", "upcoming", "fixture", "fixtures", "schedule", "scheduled",
    "next game", "next match", "this week", "weekend", "tonight's",
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

# Relationship hints injected into the schema prompt so the LLM writes correct JOINs
_SCHEMA_RELATIONSHIP_NOTES = """
KEY RELATIONSHIPS (always use these to JOIN correctly):
  matches.home_team_id   → teams.team_id
  matches.away_team_id   → teams.team_id
  matches.winner_team_id → teams.team_id
  team_game_stats.game_id → matches.game_id     (use this to filter team stats by season)
  team_game_stats.team_id → teams.team_id
  player_game_stats.game_id  → matches.game_id  (use this to filter player game stats by season)
  player_game_stats.player_id → players.player_id
  player_season_stats.player_id → players.player_id
  player_season_stats.team_id  → teams.team_id
  match_features.game_id → matches.game_id
  predictions.game_id → matches.game_id
  bets.game_id → matches.game_id

IMPORTANT COLUMN NOTES:
  - Season is stored in matches.season (e.g. '2025-26'). team_game_stats and player_game_stats do NOT have a season column — always JOIN via matches to filter by season.
  - To get a team's win rate: JOIN teams → matches (home_team_id or away_team_id), filter by season, count wins where winner_team_id = team_id.
  - Available seasons: '2025-26' (current), '2024-25' (previous). Default to '2025-26'.
  - matches.is_completed = true means the game has been played.
  - players.player_id and teams.team_id are the canonical FK columns (not 'id').

PROVEN QUERY PATTERNS:
  Team win rates this season:
    SELECT t.full_name, t.abbreviation,
           SUM(CASE WHEN m.winner_team_id = t.team_id THEN 1 ELSE 0 END)::float / NULLIF(COUNT(m.id),0) AS win_rate,
           COUNT(m.id) AS games_played
    FROM teams t
    JOIN matches m ON m.home_team_id = t.team_id OR m.away_team_id = t.team_id
    WHERE m.season = '2025-26' AND m.is_completed = true
    GROUP BY t.full_name, t.abbreviation
    ORDER BY win_rate DESC;

  Top scorers this season (player_season_stats):
    SELECT p.full_name, t.abbreviation, pss.points, pss.games_played
    FROM player_season_stats pss
    JOIN players p ON p.player_id = pss.player_id
    JOIN teams t   ON t.team_id   = pss.team_id
    WHERE pss.season = '2025-26'
    ORDER BY pss.points DESC;
"""

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
        if not config.GEMINI_API_KEY:
            logger.warning(
                "LLMClient: GEMINI_API_KEY is not set in backend/.env — "
                "the chatbot will use plain-text fallbacks instead of AI-narrated answers. "
                "Set GEMINI_API_KEY to enable full chatbot functionality."
            )
        else:
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

    @observe(name="llm.generate", as_type="generation", capture_input=False, capture_output=False)
    def generate(self, prompt: str, *, max_tokens: int = 400, _span_name: str = "llm.generate") -> Optional[str]:
        """Generate a text response. Returns None if LLM is unavailable."""
        if not self._genai:
            return None
        output_text: Optional[str] = None
        input_tokens: Optional[int] = None
        output_tokens: Optional[int] = None
        try:
            model = self._genai.GenerativeModel(self._model_name)  # type: ignore[union-attr]
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.25, "max_output_tokens": max_tokens},
            )
            output_text = (response.text or "").strip() or None

            # Extract token usage from Gemini response metadata if available
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                input_tokens = getattr(response.usage_metadata, "prompt_token_count", None)
                output_tokens = getattr(response.usage_metadata, "candidates_token_count", None)
        except Exception as exc:
            logger.warning("LLMClient.generate failed: %s", exc)
            return None
        finally:
            # Record a nested generation span in Langfuse with full prompt, output, and tokens
            record_generation(
                name=_span_name,
                prompt=prompt,
                output=output_text,
                model=self._model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        return output_text


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
    Appends FK relationship notes so the LLM generates correct JOINs.
    """
    parts: List[str] = []
    empty_tables: List[str] = []
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
                # Check if the table actually has data
                count = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
                if count == 0:
                    empty_tables.append(table)
                    parts.append(f"  {table}({cols})  -- EMPTY: no rows yet")
                else:
                    parts.append(f"  {table}({cols})")
        except Exception as exc:
            logger.warning("_fetch_schema_context: could not fetch schema for table %s — %s", table, exc)
    schema = "\n".join(parts)
    if empty_tables:
        logger.info("_fetch_schema_context: tables with 0 rows: %s", empty_tables)
    if schema:
        logger.debug("_fetch_schema_context: fetched schema for %d tables", len(parts))
        schema = schema + "\n" + _SCHEMA_RELATIONSHIP_NOTES
    else:
        logger.warning(
            "_fetch_schema_context: schema is empty — DB may be unreachable or "
            "tables may not exist yet. Run the ingestion pipeline first."
        )
    return schema


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
        init_langfuse()
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

    @observe(name="chatbot.rag_reply", as_type="retriever")
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
            lower_msg = message.lower()
            is_schedule_q = any(w in lower_msg for w in (
                "tomorrow", "tonight", "fixture", "schedule", "upcoming", "next game", "this week"
            ))
            if is_schedule_q:
                return (
                    "I don't have today's or tomorrow's schedule indexed yet — the news feeds "
                    "may not have published the matchup previews. The database only stores "
                    "completed games, so future fixtures aren't queryable directly. "
                    "Try checking NBA.com for today's schedule, or ask me about "
                    "recent results, standings, or player stats."
                )
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

    @observe(name="chatbot.db_reply", as_type="chain")
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

        # Guard: if schema is empty the LLM cannot generate valid SQL
        if not schema:
            return (
                "I can't query the database right now — the database schema appears to be "
                "empty or unreachable. Make sure the backend is connected to PostgreSQL and "
                "the ingestion pipeline has been run at least once."
            )

        # ── Step 1: Generate SQL ──────────────────────────────────────────
        if self.llm.available:
            sql_prompt = (
                f"You are a PostgreSQL expert for a sports analytics platform (NBA data).\n"
                f"Generate ONE valid SELECT query to answer the user's question.\n\n"
                f"STRICT RULES:\n"
                f"- Use ONLY the tables and exact column names listed in the schema below.\n"
                f"- NEVER filter team_game_stats or player_game_stats by season directly — "
                f"they have no season column. Always JOIN via matches to filter by season.\n"
                f"- Only SELECT — no INSERT, UPDATE, DELETE, or DDL.\n"
                f"- Follow the KEY RELATIONSHIPS section for all JOINs.\n"
                f"- Follow the PROVEN QUERY PATTERNS as templates where applicable.\n"
                f"- Default to season '2025-26' unless the user specifies otherwise.\n"
                f"- If a table is marked EMPTY, do not query it — say so instead.\n"
                f"- Include ORDER BY and LIMIT for readability.\n"
                f"- Return ONLY the raw SQL with no markdown, no explanation.\n\n"
                f"Schema and relationships:\n{schema}\n\n"
                f"{'Conversation context:' + chr(10) + history_str + chr(10) if history_str else ''}"
                f"Question: {message}\n"
                f"SQL:"
            )
            raw_sql = self.llm.generate(sql_prompt, max_tokens=400)
        else:
            raw_sql = None

        if not raw_sql:
            logger.warning("ChatService._db_reply: LLM returned empty SQL for: %s", message)
            return self._db_fallback(message)

        sql = _extract_sql(raw_sql)
        valid, err = _validate_sql(sql)
        if not valid:
            logger.warning("ChatService._db_reply: invalid SQL (%s): %s", err, sql)
            return self._db_fallback(message)

        sql = _cap_limit(sql)
        logger.debug("ChatService._db_reply: executing SQL:\n%s", sql)

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
            logger.info(
                "ChatService._db_reply: query returned %d row(s) | columns: %s",
                len(rows), columns,
            )
        except Exception as exc:
            logger.warning("ChatService._db_reply: SQL execution failed: %s | SQL: %s", exc, sql)
            return (
                "I tried to query your data but hit a database error. "
                "Could you rephrase the question? "
                f"_(Technical detail: {str(exc)[:120]})_"
            )

        if not rows:
            logger.info("ChatService._db_reply: 0 rows returned. SQL was:\n%s", sql)
            lower_msg = message.lower()
            # Specific hints based on what the query was about
            if any(w in lower_msg for w in ("tomorrow", "tonight", "fixture", "schedule", "upcoming", "next game")):
                return (
                    "The database only stores **completed** games — upcoming fixtures and schedules "
                    "aren't stored yet. The ingestion pipeline runs daily and only records results "
                    "after games finish. Try asking about recent results or standings instead, "
                    "for example: \"Which team has the best win rate this season?\""
                )
            if "predictions" in sql.lower():
                return (
                    "The predictions table is currently empty — model predictions are stored here "
                    "once the ML pipeline runs against scheduled games. No predictions have been "
                    "generated yet for upcoming matches."
                )
            if "bets" in sql.lower():
                return "The bets table has very limited data so far — only 1 bet has been recorded."
            return (
                "I ran the query but found no results for that question. "
                "Try rephrasing — for example: \"Which team has the best win rate this season?\" "
                "or \"Who are the top 5 scorers in 2025-26?\""
            )

        # ── Step 3: Narrate ───────────────────────────────────────────────
        header = " | ".join(columns)
        data_rows = "\n".join(
            " | ".join(str(row.get(c, "")) for c in columns)
            for row in rows[:20]
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
        if self.llm.available:
            reply = self.llm.generate(narrate_prompt, max_tokens=250)
            if reply:
                logger.info("ChatService._db_reply: LLM narrated %d-row result.", len(rows))
                return reply
            logger.warning("ChatService._db_reply: LLM narration empty — using plain-text fallback.")
        else:
            logger.info("ChatService._db_reply: LLM unavailable — using plain-text row fallback.")
        return self._rows_fallback(columns, rows)

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

    @observe(name="chatbot.reply", as_type="chain")
    def reply(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Generate a chatbot reply.

        Parameters
        ----------
        message    : The user's latest message.
        history    : Previous conversation turns [{role, content}, ...].
        session_id : Optional frontend session ID for Langfuse trace grouping.
                     Pass a stable per-user/per-browser identifier so that
                     all turns from one session appear together in the
                     Langfuse dashboard.

        Returns
        -------
        str : The assistant's reply.
        """
        history = history or []

        # Attach session context to the Langfuse trace created by @observe above
        set_session_context(
            session_id=session_id,
            trace_name=f"chatbot/{self.sport}",
        )

        intent = IntentRouter.route(message)
        logger.info("ChatService.reply: intent=%s sport=%s session=%s", intent, self.sport, session_id)

        if intent == "off_topic":
            return self._decline()
        if intent == "rag":
            return self._rag_reply(message, history)
        return self._db_reply(message, history)
