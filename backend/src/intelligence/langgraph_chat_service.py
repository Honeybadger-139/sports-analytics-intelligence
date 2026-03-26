"""
LangGraph chatbot service — Phase 6.1 enhanced with LangChain tools and PostgreSQL memory.

Graph flow:
  memory_load -> policy_gate -> route_intent -> rewrite_query ->
    rag  : rag_retrieve  -> rag_quality_gate -> rag_respond   -> memory_save -> finalize
    db   : db_query      -> db_retry?         -> memory_save -> finalize
    off_topic                                 -> finalize

Phase 6.1 additions (SCR-317):
  - LangChain tools (SQLQueryTool, RAGRetrieverTool, etc.) replace raw lambdas
  - ChatMemory persists history to PostgreSQL (survives container restarts)
  - Structured output via Pydantic schemas (output_schemas.py)
  - Memory loaded at graph start, saved after each reply

If langgraph/langchain imports are unavailable it safely falls back to the
legacy ChatService engine.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TypedDict

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from src import config
from src.intelligence.chat_service import ChatService, IntentRouter, PolicyGate
from src.intelligence.langfuse_client import observe, set_session_context
from src.intelligence.memory import ChatMemory, get_memory

logger = logging.getLogger(__name__)


class ChatGraphState(TypedDict, total=False):
    original_message: str
    message: str
    history: List[Dict[str, str]]       # merged: in-request + DB memory
    session_id: Optional[str]           # Phase 6.1: for DB memory lookup
    policy_decision: str
    policy_reason: str
    intent: str
    reply: str
    source_path: str
    tool_path: str
    quality_score: float
    retrieval_docs: List[Dict]
    retrieval_meta: Dict
    sources: List[Dict[str, Any]]
    table: Optional[Dict[str, Any]]
    key_numbers: List[Dict[str, Any]]
    sql_latency_ms: Optional[float]
    rows_returned: int
    needs_db_retry: bool
    db_attempts: int


class GraphReplyContract(BaseModel):
    reply: str = Field(min_length=1)
    source_path: str = Field(default="db")
    tool_path: str = Field(default="none")
    policy_decision: str = Field(default="allowed")
    policy_reason: str = Field(default="sports_analytics_scope")
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
        self._memory = get_memory(db)             # Phase 6.1: PostgreSQL memory
        self._tools: Optional[Dict] = None        # Phase 6.1: lazy-initialised tool map
        self._graph = self._build_graph()
        self.last_metadata: Dict[str, Any] = {}

    def _get_tools(self) -> Dict:
        """Lazily build the LangChain tool map (avoids import overhead when graph unavailable)."""
        if self._tools is None:
            try:
                from src.intelligence.langchain_tools import get_tool_map
                self._tools = get_tool_map(db=self.db, sport=self.sport)
                logger.debug("LangChain tools initialised: %s", list(self._tools.keys()))
            except Exception as exc:
                logger.warning("LangChain tools unavailable: %s", exc)
                self._tools = {}
        return self._tools

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
                f"{i}. [{doc.get('source', 'source')}] {doc.get('title', '')} - "
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

        policy_runnable = RunnableLambda(lambda state: PolicyGate.evaluate(str(state.get("original_message", ""))))
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
                return_meta=True,
            )
        )
        off_topic_runnable = RunnableLambda(lambda _state: self._legacy._decline())

        def memory_load(state: ChatGraphState) -> ChatGraphState:
            """
            Phase 6.1: Load PostgreSQL conversation history and merge with
            in-request history. DB memory wins for older turns; in-request
            history wins for the current session (frontend may have more context).
            """
            session_id = state.get("session_id")
            if not session_id:
                return {}
            try:
                db_history = self._memory.get_history(session_id, max_turns=6)
                existing = list(state.get("history") or [])
                # Deduplicate: use DB history as base, append any new turns from request
                existing_contents = {h.get("content", "") for h in existing}
                extra = [h for h in db_history if h.get("content") not in existing_contents]
                merged = extra + existing
                return {"history": merged[-12:]}  # cap at 12 turns total
            except Exception as exc:
                logger.warning("memory_load failed: %s", exc)
                return {}

        def memory_save(state: ChatGraphState) -> ChatGraphState:
            """
            Phase 6.1: Persist the user message + assistant reply to PostgreSQL.
            Runs after a successful reply is generated.
            """
            session_id = state.get("session_id")
            reply = state.get("reply", "")
            original_message = state.get("original_message", "")
            if not session_id or not reply:
                return {}
            try:
                self._memory.add_message(session_id, "user", original_message)
                self._memory.add_message(session_id, "assistant", reply)
                self._memory.increment_turn_count(session_id)
            except Exception as exc:
                logger.warning("memory_save failed: %s", exc)
            return {}

        def policy_gate(state: ChatGraphState) -> ChatGraphState:
            decision, reason = policy_runnable.invoke(state)
            return {"policy_decision": str(decision), "policy_reason": str(reason)}

        def policy_refusal(state: ChatGraphState) -> ChatGraphState:
            reason = str(state.get("policy_reason", "off_topic"))
            return {
                "reply": self._legacy._policy_refusal(reason),
                "source_path": "off_topic",
                "tool_path": "policy_gate",
                "quality_score": 0.9,
            }

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
                "tool_path": "rag_tool",
                "quality_score": 0.0,
            }

        def rag_respond(state: ChatGraphState) -> ChatGraphState:
            reply = str(rag_generate_runnable.invoke(state))
            docs = state.get("retrieval_docs", [])
            sources = [
                {
                    "title": doc.get("title") or "Source",
                    "url": doc.get("url") or "",
                    "source": doc.get("source") or "unknown",
                }
                for doc in docs[:5]
            ]
            return {
                "reply": reply,
                "source_path": "rag",
                "tool_path": "rag_tool",
                "sources": sources,
                "table": None,
                "key_numbers": [],
                "quality_score": float(state.get("quality_score", 0.55)),
            }

        def db_query(state: ChatGraphState) -> ChatGraphState:
            reply, db_meta = db_runnable.invoke(state)
            attempts = 1
            return {
                "reply": str(reply),
                "source_path": "db",
                "tool_path": "sql_tool",
                "table": db_meta.get("table"),
                "key_numbers": db_meta.get("key_numbers", []),
                "sql_latency_ms": db_meta.get("sql_latency_ms"),
                "rows_returned": db_meta.get("rows_returned", 0),
                "db_attempts": attempts,
                "needs_db_retry": self._should_retry_db(str(reply), attempts),
                "quality_score": float(db_meta.get("confidence", 0.65)),
            }

        def db_retry(state: ChatGraphState) -> ChatGraphState:
            retry_question = (
                f"{state.get('original_message', '')}. "
                "Use available 2025-26 data and valid joins from schema relationships."
            )
            reply, db_meta = self._legacy._db_reply(
                retry_question,
                state.get("history", []),
                return_meta=True,
            )
            return {
                "reply": str(reply),
                "source_path": "db",
                "tool_path": "sql_tool",
                "table": db_meta.get("table"),
                "key_numbers": db_meta.get("key_numbers", []),
                "sql_latency_ms": db_meta.get("sql_latency_ms"),
                "rows_returned": db_meta.get("rows_returned", 0),
                "db_attempts": int(state.get("db_attempts", 1)) + 1,
                "needs_db_retry": False,
                "quality_score": float(db_meta.get("confidence", 0.7)),
            }

        def off_topic_node(_state: ChatGraphState) -> ChatGraphState:
            reply = str(off_topic_runnable.invoke({}))
            return {
                "reply": reply,
                "source_path": "off_topic",
                "tool_path": "policy_gate",
                "quality_score": 0.5,
            }

        def finalize(state: ChatGraphState) -> ChatGraphState:
            reply = str(state.get("reply", "")).strip()
            if not reply:
                reply = "I couldn't generate a response for that request. Please try rephrasing."
            payload = {
                "reply": reply,
                "source_path": state.get("source_path", "db"),
                "tool_path": state.get("tool_path", "none"),
                "policy_decision": state.get("policy_decision", "allowed"),
                "policy_reason": state.get("policy_reason", "sports_analytics_scope"),
                "quality_score": float(state.get("quality_score", 0.5)),
                "table": state.get("table"),
                "key_numbers": state.get("key_numbers", []),
                "sources": state.get("sources", []),
                "sql_latency_ms": state.get("sql_latency_ms"),
                "rows_returned": state.get("rows_returned", 0),
            }
            try:
                contract = GraphReplyContract.model_validate(payload)
                merged = contract.model_dump()
                merged.update({
                    "table": payload.get("table"),
                    "key_numbers": payload.get("key_numbers", []),
                    "sources": payload.get("sources", []),
                    "sql_latency_ms": payload.get("sql_latency_ms"),
                    "rows_returned": payload.get("rows_returned", 0),
                })
                return merged
            except ValidationError:
                return {
                    "reply": reply,
                    "source_path": state.get("source_path", "db"),
                    "tool_path": state.get("tool_path", "none"),
                    "policy_decision": state.get("policy_decision", "allowed"),
                    "policy_reason": state.get("policy_reason", "sports_analytics_scope"),
                    "quality_score": 0.5,
                    "table": state.get("table"),
                    "key_numbers": state.get("key_numbers", []),
                    "sources": state.get("sources", []),
                    "sql_latency_ms": state.get("sql_latency_ms"),
                    "rows_returned": state.get("rows_returned", 0),
                }

        def policy_branch(state: ChatGraphState) -> str:
            if state.get("policy_decision") == "blocked":
                return "blocked"
            return "allowed"

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
        # Phase 6.1: memory nodes
        graph.add_node("memory_load", memory_load)
        graph.add_node("memory_save", memory_save)
        # Existing nodes
        graph.add_node("policy_gate", policy_gate)
        graph.add_node("policy_refusal", policy_refusal)
        graph.add_node("route_intent", route_intent)
        graph.add_node("rewrite_query", rewrite_query)
        graph.add_node("rag_retrieve", rag_retrieve)
        graph.add_node("rag_quality_gate", rag_quality_gate)
        graph.add_node("rag_respond", rag_respond)
        graph.add_node("db_query", db_query)
        graph.add_node("db_retry", db_retry)
        graph.add_node("off_topic_node", off_topic_node)
        graph.add_node("finalize", finalize)

        # Phase 6.1: entry point is memory_load → policy_gate
        graph.set_entry_point("memory_load")
        graph.add_edge("memory_load", "policy_gate")

        graph.add_conditional_edges(
            "policy_gate",
            policy_branch,
            {
                "allowed": "route_intent",
                "blocked": "policy_refusal",
            },
        )
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
        # Phase 6.1: save memory after successful replies
        graph.add_edge("rag_respond", "memory_save")
        graph.add_edge("memory_save", "finalize")
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
        graph.add_edge("policy_refusal", "finalize")
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
            answer = self._legacy.reply(message=message, history=history, session_id=session_id)
            self.last_metadata = dict(self._legacy.last_metadata)
            return answer

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
                    "session_id": session_id,   # Phase 6.1: enables DB memory
                }
            )
            reply = str(result.get("reply", "")).strip() if isinstance(result, dict) else ""
            if reply:
                source_path = str(result.get("source_path", "db")) if isinstance(result, dict) else "db"
                intent = "rag" if source_path == "rag" else ("off_topic" if source_path == "off_topic" else "db")
                self.last_metadata = self._legacy._build_response_metadata(
                    message=message,
                    answer=reply,
                    intent=intent,
                    policy_decision=str(result.get("policy_decision", "allowed")) if isinstance(result, dict) else "allowed",
                    policy_reason=str(result.get("policy_reason", "sports_analytics_scope")) if isinstance(result, dict) else "sports_analytics_scope",
                    meta={
                        "tool_path": result.get("tool_path", "none") if isinstance(result, dict) else "none",
                        "table": result.get("table") if isinstance(result, dict) else None,
                        "key_numbers": result.get("key_numbers", []) if isinstance(result, dict) else [],
                        "sources": result.get("sources", []) if isinstance(result, dict) else [],
                        "confidence": float(result.get("quality_score", 0.5)) if isinstance(result, dict) else 0.5,
                        "sql_latency_ms": result.get("sql_latency_ms") if isinstance(result, dict) else None,
                        "rows_returned": result.get("rows_returned", 0) if isinstance(result, dict) else 0,
                    },
                )
                return reply
            logger.warning("LangGraph returned empty reply; falling back to legacy engine.")
        except Exception as exc:
            logger.warning("LangGraph execution failed; falling back to legacy engine: %s", exc)

        answer = self._legacy.reply(message=message, history=history, session_id=session_id)
        self.last_metadata = dict(self._legacy.last_metadata)
        return answer
