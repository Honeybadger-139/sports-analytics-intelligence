# 2026-03-06 - Phase 7 completion: LangGraph chatbot orchestration + eval harness

## Type
Implementation (backend chatbot architecture + docs)

## Objective
Complete Phase 7 migration goals by introducing LangChain/LangGraph orchestration with guarded control flow, while preserving legacy-safe behavior.

## What changed
- Added `CHAT_ENGINE` config flag (`legacy` default, `langgraph` optional):
  - `backend/src/config.py`
  - `backend/.env.example`
- Added LangGraph service:
  - `backend/src/intelligence/langgraph_chat_service.py`
  - State graph:
    - `route_intent -> rewrite_query`
    - RAG path: `rag_retrieve -> rag_quality_gate -> rag_respond -> finalize`
    - DB path: `db_query -> db_retry(optional) -> finalize`
    - Off-topic path: `off_topic_node -> finalize`
  - Graph nodes use LangChain `RunnableLambda` wrappers for tool invocation.
  - Output contract validation via `GraphReplyContract`.
  - Safe fallback to legacy engine when langgraph/langchain deps are unavailable.
- Wired chat API to engine selector:
  - `backend/src/api/chat_routes.py`
  - `/api/v1/chat` now instantiates service via `_get_chat_service()` based on `CHAT_ENGINE`.
  - `/api/v1/chat` response now includes `engine`.
  - `/api/v1/chat/health` now includes:
    - `chat_engine_configured`
    - `chat_engine_active`
    - `langgraph_available`
- Added evaluation harness:
  - `backend/src/intelligence/chat_eval.py`
  - Compares legacy vs langgraph behavior on fixed intent classes (DB/RAG/off-topic).
- Added dependencies for framework layer:
  - `backend/requirements.txt` (`langchain`, `langgraph`)

## Test coverage added
- New tests: `backend/tests/test_chat_routes.py`
  - Engine selection (legacy/langgraph)
  - `/api/v1/chat` service usage path
  - `/api/v1/chat/health` engine metadata fields
- New tests: `backend/tests/test_langgraph_chat_service.py`
  - graph-unavailable fallback behavior
  - RAG quality-gate fallback when retrieval is empty
  - DB retry path behavior
  - off-topic branch behavior

## Validation
- `cd backend && PYTHONPATH=. venv/bin/pytest tests/test_langgraph_chat_service.py tests/test_chat_routes.py tests/test_intelligence_routes.py -q` ✅ (`12 passed`)

## Notes
- Legacy engine remains default (`CHAT_ENGINE=legacy`), preserving current behavior.
- LangGraph path now includes guard + retry nodes and can be extended with streaming + tool-level metrics in Phase 8.
