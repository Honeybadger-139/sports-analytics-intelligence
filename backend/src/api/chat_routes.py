"""
Chatbot API route.

Exposes POST /api/v1/chat — the single endpoint consumed by the frontend
ChatbotPanel component. Routes each message through ChatService which
handles intent classification, RAG retrieval, and NL→SQL→narration.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.data.db import get_db
from src.intelligence.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chatbot"])


class HistoryMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: Optional[List[HistoryMessage]] = Field(default_factory=list)
    sport: Optional[str] = Field(default="nba", description="Sport context (reserved for future multi-sport support)")


class ChatResponse(BaseModel):
    reply: str
    intent: Optional[str] = None  # 'rag' | 'db' | 'off_topic' — useful for debugging


@router.post("/chat", response_model=ChatResponse)
async def chat(
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
        service = ChatService(db=db, sport=payload.sport or "nba")

        # Expose intent for frontend debug (not shown in UI, available in network tab)
        from src.intelligence.chat_service import IntentRouter
        intent = IntentRouter.route(payload.message)

        reply = service.reply(message=payload.message, history=history)
        return ChatResponse(reply=reply, intent=intent)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("ChatService error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="The AI assistant encountered an error. Please try again.",
        ) from exc
