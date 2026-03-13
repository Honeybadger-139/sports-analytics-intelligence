# API Layer — Learning Notes

> Status: FastAPI backend with route families for prediction, intelligence, MLOps, chat, and Scribble.

## API Philosophy

1. Routes are thin contracts.
2. Service/store modules own business logic.
3. Additive response evolution is preferred over breaking changes.
4. Operational traceability is built into API outputs.

All routes are versioned under `/api/v1`.

## Endpoint Families

### A) Core prediction + data endpoints (`routes.py`)

- Health and dimensions
  - `GET /api/v1/health`
  - `GET /api/v1/teams`
  - `GET /api/v1/standings`

- Match and feature surfaces
  - `GET /api/v1/matches`
  - `GET /api/v1/matches/{game_id}/stats`
  - `GET /api/v1/features/{game_id}`
  - `GET /api/v1/players`
  - `GET /api/v1/players/{player_id}/game-stats`
  - `GET /api/v1/teams/{abbreviation}/game-stats`

- Prediction operations
  - `GET /api/v1/predictions/game/{game_id}`
  - `GET /api/v1/predictions/today`
  - `GET /api/v1/predictions/performance`
  - `GET /api/v1/predictions/bet-sizing`

- Bet ledger
  - `POST /api/v1/bets`
  - `GET /api/v1/bets`
  - `POST /api/v1/bets/{bet_id}/settle`
  - `GET /api/v1/bets/summary`

- Raw explorer + ops status
  - `GET /api/v1/raw/tables`
  - `GET /api/v1/raw/{table_name}`
  - `GET /api/v1/quality/overview`
  - `GET /api/v1/system/status`

### B) Intelligence (`intelligence_routes.py`)

- `GET /api/v1/intelligence/game/{game_id}`
- `GET /api/v1/intelligence/brief`

Supports RAG retrieval controls (top-k, freshness window) and deterministic risk overlays.

### C) MLOps (`mlops_routes.py`)

- `GET /api/v1/mlops/monitoring`
- `GET /api/v1/mlops/monitoring/trend`
- `GET /api/v1/mlops/retrain/policy`
- `GET /api/v1/mlops/retrain/jobs`
- `POST /api/v1/mlops/retrain/worker/run-next`

### D) Chatbot (`chat_routes.py`)

- `GET /api/v1/chat/health`
- `POST /api/v1/chat`
- `POST /api/v1/chat/stream` (SSE)

Key pattern: stream-first UX with non-stream fallback for compatibility.

### E) Scribble (`scribble_routes.py`)

- Query execution
  - `POST /api/v1/scribble/query`

- Notebooks
  - `GET /api/v1/scribble/notebooks`
  - `POST /api/v1/scribble/notebooks`
  - `PATCH /api/v1/scribble/notebooks/{id}`
  - `DELETE /api/v1/scribble/notebooks/{id}`

- Views
  - `GET /api/v1/scribble/views`
  - `POST /api/v1/scribble/views`
  - `DELETE /api/v1/scribble/views/{view_name}`

- AI SQL assistant
  - `POST /api/v1/scribble/ai-sql`

## Design Patterns Used

1. **Dependency injection** with `Depends(get_db)` for DB session lifecycle.
2. **Lazy init** for expensive clients/models where possible.
3. **Contract-safe enrichment** (new optional fields instead of breaking response shape).
4. **Defensive runtime behavior**: explicit error mapping and degraded-mode responses.

## Interview Angles

1. "I separated route contracts from service logic so behavior can be tested without HTTP coupling."
2. "Prediction endpoints persist outcomes so model quality is measured from production artifacts, not only offline notebooks."
3. "The chat and Scribble paths use strict guardrails to combine LLM utility with operational safety."
4. "MLOps endpoints expose both current state and trend history, enabling policy-based retrain decisions."
