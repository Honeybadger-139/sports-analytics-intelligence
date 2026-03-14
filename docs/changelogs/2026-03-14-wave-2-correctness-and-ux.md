# 2026-03-14 Wave 2 Correctness and UX

## Scope

Implemented Wave 2 from the backlog under Linear issue `SCR-296`, keeping the work limited to:

- temporal train/validation enforcement
- SHAP persistence and API exposure
- React Query caching with loading/error UX improvements
- background retrain execution
- structured request logging and public endpoint rate limiting

## Backend changes

### Temporal training split

- Added `load_training_dataset(...)` in `backend/src/models/trainer.py`
- Added explicit `cutoff_date` and `validation_season` handling to `run_training_pipeline(...)`
- Persisted training metadata to timestamped JSON artifacts so cutoff/validation context is auditable

### SHAP persistence

- Added `shap_factors JSONB` handling in `backend/src/data/prediction_store.py`
- Added `top_shap_factors(...)` in `backend/src/models/explainability.py`
- Added per-model explainability extraction in `backend/src/models/predictor.py`
- Updated `/api/v1/predictions/game/{game_id}` and prediction bootstrap/persist flows in `backend/src/api/routes.py`

### Background retrain execution

- Refactored retrain execution into `_run_claimed_retrain_job(...)` in `backend/src/mlops/retrain_worker.py`
- Added `dispatch_next_retrain_job(...)` to claim queued jobs and run them in a daemon thread
- Updated `POST /api/v1/mlops/retrain/worker/run-next` to return `processing` immediately

### Structured logging and rate limiting

- Added JSON logging setup in `backend/src/logging_setup.py`
- Added per-request trace IDs and `X-Trace-Id` response header in `backend/main.py`
- Added SlowAPI wrapper helpers in `backend/src/rate_limit.py`
- Added chat and Scribble limits in `backend/src/api/chat_routes.py` and `backend/src/api/scribble_routes.py`
- Added `CHAT_RATE_LIMIT` and `SCRIBBLE_RATE_LIMIT` config in `backend/src/config.py`

## Frontend changes

### React Query

- Added `@tanstack/react-query`
- Wrapped the app with `QueryClientProvider` in `frontend/src/App.tsx`
- Reworked `frontend/src/hooks/useApi.ts` to use `useQuery` with endpoint-appropriate `staleTime`

### Error boundaries and skeletons

- Added `frontend/src/components/ErrorBoundary.tsx`
- Added `frontend/src/components/SkeletonCard.tsx`
- Wrapped Arena, Pulse, and Lab routed sections in boundaries
- Replaced blank suspense fallbacks with shimmer skeleton layouts

## Verification

### Backend tests

Ran:

```bash
cd backend
PYTHONPATH=. venv/bin/pytest tests/test_chat_routes.py tests/test_scribble_routes.py tests/test_prediction_store.py tests/test_retrain_worker.py tests/test_mlops_routes.py tests/test_trainer.py tests/test_routes.py -q
```

Result:

- `51 passed`

### Frontend checks

Ran:

```bash
cd frontend
npx eslint src/App.tsx src/hooks/useApi.ts src/pages/Arena.tsx src/pages/Pulse.tsx src/pages/Lab.tsx src/components/ErrorBoundary.tsx src/components/SkeletonCard.tsx
npm run build
```

Result:

- targeted lint passed for the Wave 2-touched frontend files
- production build passed

## Follow-up notes

- `npm run lint` for the whole frontend still reports pre-existing React hooks / compiler issues in unrelated files outside the Wave 2 scope
- repo root `data/chroma/` remains untracked and was left untouched because it predates this wave and may be part of local RAG state
