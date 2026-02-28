# Phase 4–5 Implementation Changelog

Date: 2026-02-28 (Asia/Kolkata)  
Scope: Phase 4 RAG intelligence implementation + Phase 5 MLOps foundation

## Objective

Implement the approved roadmap end-to-end:

1. RAG-backed intelligence layer for contextual NBA insights.
2. Dashboard integration for context brief and intelligence workspace.
3. MLOps monitoring and retrain-policy APIs with UI visibility.

## Backend Changes

1. Added intelligence modules under `backend/src/intelligence/`:
   - `news_agent.py`
   - `embeddings.py`
   - `vector_store.py`
   - `retriever.py`
   - `summarizer.py`
   - `rules.py`
   - `service.py`
   - `types.py`
2. Added intelligence APIs:
   - `GET /api/v1/intelligence/game/{game_id}`
   - `GET /api/v1/intelligence/brief`
3. Added MLOps modules under `backend/src/mlops/`:
   - `monitoring.py`
   - `retrain_policy.py`
4. Added MLOps APIs:
   - `GET /api/v1/mlops/monitoring`
   - `GET /api/v1/mlops/retrain/policy?dry_run=true`
5. Added intelligence audit persistence:
   - new table `intelligence_audit` in `init.sql`
   - bootstrap/log utility `src/data/intelligence_audit_store.py`
6. Added deterministic context chunking with overlap in `news_agent.py` and wired chunked indexing in `service.py`.
7. Added MLOps snapshot audit logging on:
   - `mlops_monitoring`
   - `mlops_retrain_policy`
8. Added model artifact governance signal in `/api/v1/system/status` (`models` snapshot block).

## Frontend Changes

1. Added `Intelligence` top-level tab.
2. Added `Context Brief (RAG)` module to Analysis -> Match Deep Dive:
   - summary rendering
   - risk chips
   - citation table
3. Added Intelligence workspace modules:
   - daily brief table
   - selected-game citation inspector
   - MLOps monitoring summary + alerts
   - retrain-policy dry-run summary

## Config & Contract Updates

1. Added env/config keys for:
   - intelligence feature flag
   - top_k / freshness / models / vector path
   - source feed lists
   - MLOps thresholds
2. Updated `settings.yaml` with formal `intelligence` section and monitoring thresholds.
3. Added RAG dependencies to `backend/requirements.txt`.

## Tests Added

1. `backend/tests/test_intelligence_routes.py`
2. `backend/tests/test_intelligence_modules.py`
3. `backend/tests/test_mlops_routes.py`
4. Added deterministic chunk overlap test (`test_chunk_context_document_overlap_boundaries_are_deterministic`).

## Verification

1. `PYTHONPATH=. ../backend/venv/bin/pytest tests -q` -> `72 passed, 1 warning`
2. `node --check frontend/js/dashboard.js` -> pass
3. Runtime checks:
   - `/api/v1/intelligence/game/0022500859?season=2025-26`
   - `/api/v1/intelligence/brief?date=2026-02-28&season=2025-26&limit=5`
   - `/api/v1/mlops/monitoring?season=2025-26`
   - `/api/v1/mlops/retrain/policy?season=2025-26&dry_run=true`

## Notes

In restricted/local environments where external feed access is blocked, intelligence endpoints degrade gracefully and return `coverage_status="insufficient"` rather than hallucinated summaries.
