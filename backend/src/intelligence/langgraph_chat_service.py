"""
LangGraph chatbot service (Phase 7).

This service keeps the legacy chatbot path intact while adding a richer
LangGraph workflow with LangChain runnable nodes:

  route_intent -> rewrite_query ->
    rag: retrieve -> quality_gate -> respond -> finalize
    db : query -> optional_retry -> finalize
    off_topic -> finalize

If langgraph/langchain imports are unavailable, it safely falls back to the
legacy ChatService engine.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple, TypedDict

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from src import config
from src.intelligence.chat_service import ChatService, IntentRouter
from src.intelligence.langfuse_client import observe, set_session_context

logger = logging.getLogger(__name__)


class ChatGraphState(TypedDict, total=False):
    original_message: str
    message: str
    history: List[Dict[str, str]]
    intent: str
    reply: str
    source_path: str
    quality_score: float
    retrieval_docs: List[Dict]
    retrieval_meta: Dict
    needs_db_retry: bool
    db_attempts: int


class GraphReplyContract(BaseModel):
    reply: str = Field(min_length=1)
    source_path: str = Field(default="db")
    quality_score: float = Field(default=0.5, ge=0.0, le=1.0)


class LangGraphChatService:
    """
    Feature-flagged LangGraph orchestration layer for chatbot replies.

    Public API mirrors ChatService.reply(), so routes can switch engines with
    a single config flag.
    """

    def __init__(self, db: Session, sport: str = "nba") -> None:
        self.db = db
        self.sport = sport
        self._legacy = ChatService(db=db, sport=sport)
        self._graph = self._build_graph()

    @property
    def graph_available(self) -> bool:
        return self._graph is not None

    @property
    def active_engine(self) -> str:
        return "langgraph" if self.graph_available else "legacy"

    @staticmethod
    def _rewrite_message(message: str, intent: str) -> str:
        cleaned = " ".join((message or "").split())
        if intent == "db" and "season" not in cleaned.lower():
            return f"{cleaned} for the 2025-26 season"
        return cleaned

    @staticmethod
    def _score_retrieval(docs: List[Dict], retrieval_meta: Dict) -> float:
        docs_used = int(retrieval_meta.get("docs_used", 0))
        if docs_used <= 0:
            return 0.0
        if docs_used >= 4:
            return 0.9
        if docs_used >= 2:
            return 0.75
        return 0.55

    @staticmethod
    def _should_retry_db(reply: str, attempts: int) -> bool:
        if attempts >= 2:
            return False
        lower = (reply or "").lower()
        retry_markers = (
            "couldn't generate a database query",
            "database error",
            "i tried to query your data but hit a database error",
            "i ran the query but found no results",
        )
        return any(marker in lower for marker in retry_markers)

    @staticmethod
    def _format_citations(docs: List[Dict]) -> str:
        rows = []
        for doc in docs[:3]:
            title = doc.get("title") or "Source"
            url = doc.get("url") or ""
            source = doc.get("source") or ""
            if url:
                rows.append(f"- {title} ({source}): {url}")
            else:
                rows.append(f"- {title} ({source})")
        if not rows:
            return ""
        return "Sources:\n" + "\n".join(rows)

    def _rag_generate_from_docs(self, message: str, history: List[Dict[str, str]], docs: List[Dict]) -> str:
        if not docs:
            return (
                "I don't have recent context indexed for that question yet. "
                "Try asking a stats question while this feed catches up."
            )

        snippets = []
        for i, doc in enumerate(docs[:5], 1):
            snippets.append(
                f"{i}. [{doc.get('source', 'source')}] {doc.get('title', '')} — "
                f"{str(doc.get('content', ''))[:260]}"
            )
        context_blob = "\n".join(snippets)
        history_str = self._legacy._format_history(history)
        history_block = f"Conversation so far:\n{history_str}\n\n" if history_str else ""

        if not self._legacy.llm.available:
            base = self._legacy._rag_fallback(docs)
            citations = self._format_citations(docs)
            return f"{base}\n\n{citations}" if citations else base

        prompt = (
            "You are a sports analytics assistant for an NBA platform. "
            "Answer using only the retrieved context, and be concise (3-5 sentences).\n\n"
            f"{history_block}"
            f"Retrieved context:\n{context_blob}\n\n"
            f"User: {message}\nAssistant:"
        )
        generated = self._legacy.llm.generate(prompt, max_tokens=300, _span_name="llm.generate.langgraph.rag")
        body = (generated or "").strip() or self._legacy._rag_fallback(docs)
        citations = self._format_citations(docs)
        return f"{body}\n\n{citations}" if citations else body

    def _build_graph(self):
        try:
            from langchain_core.runnables import RunnableLambda  # type: ignore
            from langgraph.graph import END, StateGraph  # type: ignore
        except Exception as exc:
            logger.warning(
                "LangGraph engine unavailable (missing langgraph/langchain dependencies): %s. "
                "Falling back to legacy chatbot engine.",
                exc,
            )
            return None

        intent_runnable = RunnableLambda(lambda state: IntentRouter.route(str(state.get("original_message", ""))))
        rewrite_runnable = RunnableLambda(
            lambda state: self._rewrite_message(
                str(state.get("original_message", "")),
                str(state.get("intent", "db")),
            )
        )
        rag_retrieve_runnable = RunnableLambda(
            lambda state: self._legacy._retriever.retrieve(
                str(state.get("message", "")),
                top_k=config.RAG_TOP_K,
                max_age_hours=config.RAG_MAX_AGE_HOURS,
            )
        )
        rag_generate_runnable = RunnableLambda(
            lambda state: self._rag_generate_from_docs(
                str(state.get("message", "")),
                state.get("history", []),
                state.get("retrieval_docs", []),
            )
        )
        db_runnable = RunnableLambda(
            lambda state: self._legacy._db_reply(
                str(state.get("message", "")),
                state.get("history", []),
            )
        )
        off_topic_runnable = RunnableLambda(lambda _state: self._legacy._decline())

        def route_intent(state: ChatGraphState) -> ChatGraphState:
            intent = str(intent_runnable.invoke(state))
            return {"intent": intent}

        def rewrite_query(state: ChatGraphState) -> ChatGraphState:
            rewritten = str(rewrite_runnable.invoke(state))
            return {"message": rewritten}

        def rag_retrieve(state: ChatGraphState) -> ChatGraphState:
            docs, meta = rag_retrieve_runnable.invoke(state)
            quality = self._score_retrieval(docs, meta)
            return {
                "retrieval_docs": docs,
                "retrieval_meta": meta,
                "quality_score": quality,
            }

        def rag_quality_gate(state: ChatGraphState) -> ChatGraphState:
            docs = state.get("retrieval_docs", [])
            if docs:
                return {}
            return {
                "reply": (
                    "I don't have recent news/context indexed for that question yet. "
                    "Try asking a stats question, or retry after the next feed refresh."
                ),
                "source_path": "rag",
                "quality_score": 0.0,
            }

        def rag_respond(state: ChatGraphState) -> ChatGraphState:
            reply = str(rag_generate_runnable.invoke(state))
            return {
                "reply": reply,
                "source_path": "rag",
                "quality_score": float(state.get("quality_score", 0.55)),
            }

        def db_query(state: ChatGraphState) -> ChatGraphState:
            reply = str(db_runnable.invoke(state))
            attempts = 1
            return {
                "reply": reply,
                "source_path": "db",
                "db_attempts": attempts,
                "needs_db_retry": self._should_retry_db(reply, attempts),
                "quality_score": 0.65,
            }

        def db_retry(state: ChatGraphState) -> ChatGraphState:
            retry_question = (
                f"{state.get('original_message', '')}. "
                "Use available 2025-26 data and valid joins from schema relationships."
            )
            reply = self._legacy._db_reply(retry_question, state.get("history", []))
            return {
                "reply": reply,
                "source_path": "db",
                "db_attempts": int(state.get("db_attempts", 1)) + 1,
                "needs_db_retry": False,
                "quality_score": 0.7,
            }

        def off_topic_node(_state: ChatGraphState) -> ChatGraphState:
            reply = str(off_topic_runnable.invoke({}))
            return {
                "reply": reply,
                "source_path": "off_topic",
                "quality_score": 0.5,
            }

        def finalize(state: ChatGraphState) -> ChatGraphState:
            reply = str(state.get("reply", "")).strip()
            if not reply:
                reply = "I couldn't generate a response for that request. Please try rephrasing."
            payload = {
                "reply": reply,
                "source_path": state.get("source_path", "db"),
                "quality_score": float(state.get("quality_score", 0.5)),
            }
            try:
                contract = GraphReplyContract.model_validate(payload)
                return contract.model_dump()
            except ValidationError:
                return {
                    "reply": reply,
                    "source_path": state.get("source_path", "db"),
                    "quality_score": 0.5,
                }

        def intent_branch(state: ChatGraphState) -> str:
            intent = state.get("intent", "db")
            if intent == "rag":
                return "rag"
            if intent == "off_topic":
                return "off_topic"
            return "db"

        def rag_quality_branch(state: ChatGraphState) -> str:
            return "done" if bool(state.get("reply")) else "continue"

        def db_retry_branch(state: ChatGraphState) -> str:
            return "retry" if bool(state.get("needs_db_retry")) else "done"

        graph = StateGraph(ChatGraphState)
        graph.add_node("route_intent", route_intent)
        graph.add_node("rewrite_query", rewrite_query)
        graph.add_node("rag_retrieve", rag_retrieve)
        graph.add_node("rag_quality_gate", rag_quality_gate)
        graph.add_node("rag_respond", rag_respond)
        graph.add_node("db_query", db_query)
        graph.add_node("db_retry", db_retry)
        graph.add_node("off_topic_node", off_topic_node)
        graph.add_node("finalize", finalize)

        graph.set_entry_point("route_intent")
        graph.add_edge("route_intent", "rewrite_query")
        graph.add_conditional_edges(
            "rewrite_query",
            intent_branch,
            {
                "rag": "rag_retrieve",
                "db": "db_query",
                "off_topic": "off_topic_node",
            },
        )
        graph.add_edge("rag_retrieve", "rag_quality_gate")
        graph.add_conditional_edges(
            "rag_quality_gate",
            rag_quality_branch,
            {
                "continue": "rag_respond",
                "done": "finalize",
            },
        )
        graph.add_edge("rag_respond", "finalize")
        graph.add_conditional_edges(
            "db_query",
            db_retry_branch,
            {
                "retry": "db_retry",
                "done": "finalize",
            },
        )
        graph.add_edge("db_retry", "finalize")
        graph.add_edge("off_topic_node", "finalize")
        graph.add_edge("finalize", END)

        logger.info("LangGraph chatbot engine initialized (Phase 7 graph).")
        return graph.compile()

    @observe(name="chatbot.reply.langgraph", as_type="chain")
    def reply(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        session_id: Optional[str] = None,
    ) -> str:
        history = history or []

        if not self.graph_available:
            return self._legacy.reply(message=message, history=history, session_id=session_id)

        set_session_context(
            session_id=session_id,
            trace_name=f"chatbot/{self.sport}/langgraph",
        )

        try:
            result = self._graph.invoke(
                {
                    "original_message": message,
                    "message": message,
                    "history": history,
                }
            )
            reply = str(result.get("reply", "")).strip() if isinstance(result, dict) else ""
            if reply:
                return reply
            logger.warning("LangGraph returned empty reply; falling back to legacy engine.")
        except Exception as exc:
            logger.warning("LangGraph execution failed; falling back to legacy engine: %s", exc)

        return self._legacy.reply(message=message, history=history, session_id=session_id)
