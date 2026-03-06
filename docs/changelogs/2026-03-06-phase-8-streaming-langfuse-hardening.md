# 2026-03-06 - Phase 8: Chat streaming + Langfuse offline hardening

## Type
Implementation (backend + frontend + reliability hardening)

## Objective
1. Add token-stream UX for chatbot responses.
2. Eliminate noisy tracing failures in offline/local development mode.
3. Make eval harness resilient when DB access is unavailable.

## What changed

### Backend
- Added SSE endpoint:
  - `POST /api/v1/chat/stream` in `backend/src/api/chat_routes.py`
  - emits `meta`, `token`, `done`, `error` events
- Added helper utilities in route:
  - `_sse_event(...)`
  - `_chunk_reply(...)`

### Frontend
- Updated stream-first chatbot hook:
  - `frontend/src/hooks/useChatbot.ts`
  - consumes SSE and updates assistant message progressively
  - falls back to non-stream `/api/v1/chat` on `HTTP 404`
- Updated chat response types:
  - `frontend/src/types.ts`

### Observability hardening
- Refactored `backend/src/intelligence/langfuse_client.py`:
  - added local `observe` wrapper that is no-op when tracing is disabled
  - set `OTEL_SDK_DISABLED=true` when Langfuse disabled/missing keys/init failure
- Updated chatbot services to use local wrapper:
  - `backend/src/intelligence/chat_service.py`
  - `backend/src/intelligence/langgraph_chat_service.py`
- Updated defaults for local cleanliness:
  - `backend/src/config.py` (`LANGFUSE_ENABLED` default false)
  - `backend/.env.example` (`LANGFUSE_ENABLED=false`)

### Eval harness
- Hardened `backend/src/intelligence/chat_eval.py`:
  - local-safe env defaults for tracing + LLM key
  - DB availability probe
  - skips DB-intent case when DB unavailable
  - still writes output report with error context

## Tests and verification
- `cd backend && PYTHONPATH=. venv/bin/pytest tests/test_chat_routes.py tests/test_langgraph_chat_service.py tests/test_intelligence_routes.py -q` -> `13 passed`
- `cd frontend && npm run build` -> success
- `cd backend && PYTHONPATH=. venv/bin/python src/intelligence/chat_eval.py --output data/chat_eval_phase7.json` -> completed and wrote report (DB marked unavailable in sandbox)
