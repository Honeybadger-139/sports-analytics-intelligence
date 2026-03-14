# Wave 1 Hardening — 2026-03-14

## Scope
- Tightened Scribble SQL execution timeout from 10s to 5s.
- Hardened intelligence ingestion/retrieval with stable feed IDs, dedupe stats, and a configurable similarity floor.
- Added JSONL fallback logging for LLM calls when Langfuse tracing is disabled.
- Secured `/api/v1/chat/stream` with trusted-proxy `X-API-Key` enforcement.
- Added Slack-based critical MLOps escalation notifications with duplicate suppression.
- Added subsystem health endpoints, Prometheus metrics exposure, and wait-for-completion scheduler shutdown.
- Added CI coverage gate to the backend regression workflow.

## Files Changed
- `backend/src/config.py`
- `backend/main.py`
- `backend/scheduler.py`
- `backend/src/api/chat_routes.py`
- `backend/src/api/routes.py`
- `backend/src/api/scribble_routes.py`
- `backend/src/intelligence/chat_service.py`
- `backend/src/intelligence/langfuse_client.py`
- `backend/src/intelligence/news_agent.py`
- `backend/src/intelligence/retriever.py`
- `backend/src/intelligence/service.py`
- `backend/src/intelligence/types.py`
- `backend/src/intelligence/vector_store.py`
- `backend/src/mlops/monitoring.py`
- `backend/src/mlops/notifications.py`
- `backend/requirements.txt`
- `.github/workflows/backend-regression.yml`

## Verification
- Targeted backend regression:
```bash
cd backend
PYTHONPATH=. venv/bin/pytest tests/test_chat_routes.py tests/test_scribble_routes.py tests/test_routes.py tests/test_intelligence_modules.py tests/test_langfuse_client.py tests/test_mlops_routes.py tests/test_config.py -q
```
- Result: `56 passed`

## Repo-State Verifications
- Backlog Task 3.4 was a no-op at Wave 1 start because `git status` was clean.
- Backlog Task 6.3 was already mostly satisfied because `.gitignore` already covered `logs/`, `*.log`, `ingestion.pid`, and `ingestion_output.log`.
- Backlog Task 6.1 was partially already satisfied because `docker-compose.yml` already contained a backend service.
