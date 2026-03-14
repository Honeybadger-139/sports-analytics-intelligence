"""
Chatbot API routes.

Exposes:
  POST /api/v1/chat        — main conversational endpoint (hybrid RAG + DB path)
  GET  /api/v1/chat/health — readiness check for the chatbot subsystem
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.data.db import get_db
from src.intelligence.chat_service import ChatService, LLMClient
from src.intelligence.langgraph_chat_service import LangGraphChatService
from src.rate_limit import limit
from src import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chatbot"])

_llm_client: Optional[LLMClient] = None


def _get_llm_client() -> LLMClient:
    """Singleton LLM client used for health checks (avoids re-init on every request)."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


class HistoryMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: Optional[List[HistoryMessage]] = Field(default_factory=list)
    sport: Optional[str] = Field(default="nba", description="Sport context (reserved for future multi-sport support)")
    session_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description=(
            "Optional stable per-session identifier (e.g. localStorage UUID). "
            "Used to group all turns from one browser session in Langfuse traces."
        ),
    )


class ChatResponse(BaseModel):
    reply: str
    intent: Optional[str] = None  # 'rag' | 'db' | 'off_topic' — useful for debugging
    engine: Optional[str] = None  # 'legacy' | 'langgraph'


class ChatHealthResponse(BaseModel):
    status: str  # 'ok' | 'degraded' | 'unavailable'
    llm_available: bool
    db_connected: bool
    schema_tables_visible: int
    gemini_model: str
    chat_engine_configured: str
    chat_engine_active: str
    langgraph_available: bool
    message: str


def _get_chat_service(db: Session, sport: str):
    """
    Build chatbot service using configured orchestration engine.

    CHAT_ENGINE options:
    - legacy   (default): existing custom orchestration
    - langgraph         : LangGraph state machine + LangChain runnable nodes
    """
    if config.CHAT_ENGINE == "langgraph":
        return LangGraphChatService(db=db, sport=sport)
    return ChatService(db=db, sport=sport)


def _sse_event(event: str, payload: Dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"


def _chunk_reply(reply: str, chunk_size: int = 24) -> List[str]:
    text_value = reply or ""
    if not text_value:
        return []
    return [text_value[i : i + chunk_size] for i in range(0, len(text_value), chunk_size)]


def _require_chat_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    if not config.CHAT_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat streaming is disabled until CHAT_API_KEY is configured.",
        )
    if x_api_key != config.CHAT_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key.",
        )


@router.get("/chat/health", response_model=ChatHealthResponse)
async def chat_health(db: Session = Depends(get_db)):
    """
    Readiness check for the chatbot subsystem.

    Returns:
    - llm_available: whether the Gemini API key is configured and reachable
    - db_connected: whether the database session is live
    - schema_tables_visible: how many whitelisted tables have columns in the schema
    - status: 'ok' if both LLM + DB are up, 'degraded' if only one is, 'unavailable' if neither

    Use this endpoint to diagnose "no matching data" issues:
    - If schema_tables_visible == 0 → run the ingestion pipeline
    - If llm_available == False     → set GEMINI_API_KEY in backend/.env
    """
    from src.intelligence.chat_service import _fetch_schema_context, _SQL_SAFE_TABLES

    llm = _get_llm_client()
    service = _get_chat_service(db=db, sport="nba")
    llm_ok = llm.available

    db_ok = False
    schema_count = 0
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
        schema = _fetch_schema_context(db)
        schema_count = len([line for line in schema.splitlines() if line.strip()])
    except Exception as exc:
        logger.warning("chat/health: DB check failed — %s", exc)

    if llm_ok and db_ok:
        status = "ok"
        msg = "Chatbot is fully operational."
    elif db_ok and not llm_ok:
        status = "degraded"
        msg = "DB is connected but LLM is unavailable — set GEMINI_API_KEY in backend/.env for AI-narrated answers."
    elif llm_ok and not db_ok:
        status = "degraded"
        msg = "LLM is available but DB is unreachable — check DATABASE_URL and PostgreSQL connection."
    else:
        status = "unavailable"
        msg = "Both LLM and DB are unavailable — check GEMINI_API_KEY and DATABASE_URL."

    return ChatHealthResponse(
        status=status,
        llm_available=llm_ok,
        db_connected=db_ok,
        schema_tables_visible=schema_count,
        gemini_model=config.RAG_SUMMARY_MODEL,
        chat_engine_configured=config.CHAT_ENGINE,
        chat_engine_active=getattr(service, "active_engine", "legacy"),
        langgraph_available=bool(getattr(service, "graph_available", False)),
        message=msg,
    )


@router.post("/chat", response_model=ChatResponse)
@limit(config.CHAT_RATE_LIMIT)
async def chat(
    request: Request,
    payload: ChatRequest,
    db: Session = Depends(get_db),
):
    """
    Hybrid chatbot endpoint.

    Routes the user's message to:
    - RAG path: news/injury/game-context questions (ChromaDB + LLM)
    - DB path:  stats/analytics questions (NL→SQL→Postgres→LLM narration)
    - Off-topic: politely declined without hitting DB or LLM

    The `sport` field defaults to 'nba'. Future sports can be passed here
    without any backend routing changes.
    """
    try:
        history = [h.model_dump() for h in (payload.history or [])]
        service = _get_chat_service(db=db, sport=payload.sport or "nba")

        # Expose intent for frontend debug (not shown in UI, available in network tab)
        from src.intelligence.chat_service import IntentRouter
        intent = IntentRouter.route(payload.message)

        reply = service.reply(
            message=payload.message,
            history=history,
            session_id=payload.session_id,
        )
        return ChatResponse(
            reply=reply,
            intent=intent,
            engine=getattr(service, "active_engine", "legacy"),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("ChatService error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="The AI assistant encountered an error. Please try again.",
        ) from exc


@router.post("/chat/stream")
@limit(config.CHAT_RATE_LIMIT)
async def chat_stream(
    request: Request,
    payload: ChatRequest,
    _auth: None = Depends(_require_chat_api_key),
    db: Session = Depends(get_db),
):
    """
    Streaming chatbot endpoint (SSE).

    Emits events:
    - `meta`   : initial intent/engine metadata
    - `token`  : chunk of assistant reply text
    - `done`   : final payload with full reply + metadata
    - `error`  : terminal error payload
    """
    history = [h.model_dump() for h in (payload.history or [])]
    service = _get_chat_service(db=db, sport=payload.sport or "nba")

    from src.intelligence.chat_service import IntentRouter

    intent = IntentRouter.route(payload.message)
    engine = getattr(service, "active_engine", "legacy")

    async def event_generator():
        yield _sse_event(
            "meta",
            {
                "intent": intent,
                "engine": engine,
            },
        )
        try:
            reply = service.reply(
                message=payload.message,
                history=history,
                session_id=payload.session_id,
            )
            for chunk in _chunk_reply(reply):
                yield _sse_event("token", {"token": chunk})
            yield _sse_event(
                "done",
                {
                    "reply": reply,
                    "intent": intent,
                    "engine": engine,
                },
            )
        except Exception as exc:
            logger.error("ChatService stream error: %s", exc, exc_info=True)
            yield _sse_event(
                "error",
                {
                    "message": "The AI assistant encountered an error. Please try again.",
                },
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
