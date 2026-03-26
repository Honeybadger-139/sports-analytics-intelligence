"""
PostgreSQL-backed conversation memory for the NBA chatbot.

WHY DATABASE-BACKED MEMORY?
----------------------------
In-memory history (list[dict]) works for a single request but dies on:
  - Container restarts (Cloud Run scales to zero — all state lost)
  - Multi-instance deployments (two containers, two different memories)
  - Long sessions ("What did I ask about the Lakers 20 minutes ago?")

PostgreSQL solves all three. The same DB that stores game data now stores
conversation turns, so every Cloud Run instance shares the same history.

DESIGN CHOICE — Plain SQLAlchemy vs LangChain ConversationBufferMemory:
  - LangChain's built-in memory classes use in-memory lists with optional
    serialisers. Their PostgreSQL backend (langchain-community SQLChatHistory)
    requires JSONB and a specific table schema we don't control.
  - Our custom class keeps the schema simple, integrates with the existing
    SQLAlchemy session, and adds session expiry + turn capping for free.

TABLES:
  chat_sessions  (id, session_id, sport, created_at, last_active_at)
  chat_messages  (id, session_id, role, content, created_at)

INTERVIEW ANGLE:
  Junior:  "I store history in a list"
  Senior:  "I persist conversation state in PostgreSQL so it survives
            container restarts. History is capped at N turns and sessions
            expire after 24 hours to control storage costs."

Part of: SCR-317 — Module 6.1 LangChain/LangGraph Enhancement
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Maximum conversation turns to load (older turns truncated to keep prompts small)
MAX_MEMORY_TURNS = 10


class ChatMemory:
    """
    PostgreSQL-backed conversation memory.

    Usage:
        memory = ChatMemory(db)
        memory.add_message(session_id="abc123", role="user", content="Who leads in points?")
        memory.add_message(session_id="abc123", role="assistant", content="Shai leads with 31.4 PPG.")
        history = memory.get_history("abc123")  # → [{"role": ..., "content": ...}]
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Public API ────────────────────────────────────────────────────────────

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """
        Persist a single message turn to the database.

        Creates the session row if it doesn't exist yet.
        Also updates last_active_at on the session so we can expire stale sessions.
        """
        if not session_id or not content:
            return

        try:
            # Ensure session exists
            self._ensure_session(session_id)

            # Insert the message
            self.db.execute(
                text(
                    """
                    INSERT INTO chat_messages (session_id, role, content, created_at)
                    VALUES (:session_id, :role, :content, :created_at)
                    """
                ),
                {
                    "session_id": session_id,
                    "role": role,
                    "content": content[:4000],  # cap per-message size
                    "created_at": datetime.now(timezone.utc),
                },
            )

            # Bump last_active_at on the session
            self.db.execute(
                text(
                    """
                    UPDATE chat_sessions
                    SET last_active_at = :now
                    WHERE session_id = :session_id
                    """
                ),
                {"session_id": session_id, "now": datetime.now(timezone.utc)},
            )

            self.db.commit()

        except Exception as exc:
            logger.warning("ChatMemory.add_message failed (session=%s): %s", session_id, exc)
            try:
                self.db.rollback()
            except Exception:
                pass

    def get_history(
        self,
        session_id: str,
        max_turns: int = MAX_MEMORY_TURNS,
    ) -> List[Dict[str, str]]:
        """
        Retrieve the last N conversation turns for a session.

        Returns a list of {"role": "user"|"assistant", "content": str} dicts,
        in chronological order (oldest first), ready to pass to LangGraph nodes.
        """
        if not session_id:
            return []

        try:
            rows = self.db.execute(
                text(
                    """
                    SELECT role, content
                    FROM chat_messages
                    WHERE session_id = :session_id
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"session_id": session_id, "limit": max_turns * 2},  # *2 for user+assistant pairs
            ).fetchall()

            # Reverse to chronological order (we fetched DESC to get latest N)
            return [{"role": row[0], "content": row[1]} for row in reversed(rows)]

        except Exception as exc:
            logger.warning("ChatMemory.get_history failed (session=%s): %s", session_id, exc)
            return []

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return session metadata, or None if session doesn't exist."""
        if not session_id:
            return None
        try:
            row = self.db.execute(
                text(
                    """
                    SELECT session_id, sport, created_at, last_active_at, turn_count
                    FROM chat_sessions
                    WHERE session_id = :session_id
                    """
                ),
                {"session_id": session_id},
            ).fetchone()
            if not row:
                return None
            return {
                "session_id": row[0],
                "sport": row[1],
                "created_at": row[2],
                "last_active_at": row[3],
                "turn_count": row[4],
            }
        except Exception as exc:
            logger.warning("ChatMemory.get_session_info failed: %s", exc)
            return None

    def increment_turn_count(self, session_id: str) -> None:
        """Increment the turn counter for analytics / abuse detection."""
        if not session_id:
            return
        try:
            self.db.execute(
                text(
                    """
                    UPDATE chat_sessions
                    SET turn_count = turn_count + 1
                    WHERE session_id = :session_id
                    """
                ),
                {"session_id": session_id},
            )
            self.db.commit()
        except Exception as exc:
            logger.warning("ChatMemory.increment_turn_count failed: %s", exc)
            try:
                self.db.rollback()
            except Exception:
                pass

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _ensure_session(self, session_id: str, sport: str = "nba") -> None:
        """
        Insert a session row if one doesn't already exist.

        Uses INSERT ... ON CONFLICT DO NOTHING to handle concurrent requests
        without raising a unique-constraint error.
        """
        self.db.execute(
            text(
                """
                INSERT INTO chat_sessions (session_id, sport, created_at, last_active_at, turn_count)
                VALUES (:session_id, :sport, :now, :now, 0)
                ON CONFLICT (session_id) DO NOTHING
                """
            ),
            {
                "session_id": session_id,
                "sport": sport,
                "now": datetime.now(timezone.utc),
            },
        )


# ── Convenience factory ───────────────────────────────────────────────────────


def get_memory(db: Session) -> ChatMemory:
    """Construct a ChatMemory instance for the given DB session."""
    return ChatMemory(db=db)
