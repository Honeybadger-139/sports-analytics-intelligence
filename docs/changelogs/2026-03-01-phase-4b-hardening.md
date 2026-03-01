# Phase 4B Hardening Changelog

Date: 2026-03-01 (Asia/Kolkata)  
Scope: Intelligence quality controls + Intelligence tab UX hardening (`SCR-139`)

## Objective

Execute the first hardening batch after Phase 4 baseline:

1. Improve source quality controls to reduce noisy context.
2. Surface feed/source quality telemetry to the UI.
3. Add operator controls for filtering and sorting intelligence brief rows.

## Backend Changes

1. Extended intelligence contracts in `backend/src/intelligence/types.py`:
   - citation-level quality fields (`quality_score`, `freshness_hours`, `is_stale`, `is_noisy`)
   - source quality summary model in retrieval payload
   - feed health model in game intelligence payload
2. Added feed-health telemetry collection in `backend/src/intelligence/news_agent.py`:
   - new `fetch_context_documents_with_health(...)`
   - existing `fetch_context_documents(...)` preserved as compatibility wrapper
3. Added source-quality scoring and noise penalties in `backend/src/intelligence/service.py`:
   - heuristic noise detection (`parlay/odds/promo code/...`)
   - per-doc quality scoring + filtering threshold
   - source-level aggregate quality summary
4. Added feed-health fallback lookup from latest `intelligence_audit` indexer record when index is already warm.
5. Refined deterministic rule precision in `backend/src/intelligence/rules.py`:
   - ignores noisy context docs for injury signals
   - emits explicit injury conflict signal when high + medium certainty cues coexist
   - adds `both_short_rest` high-severity rule for dual short-rest matchups
   - adds low-signal fallback when all retrieved docs are noisy

## Frontend Changes

1. Intelligence tab controls added in `frontend/index.html`:
   - sort selector
   - risk filter selector
   - minimum citations filter
2. Selected-game citation inspector upgraded:
   - citation quality column
   - stale/noisy visual tags
   - source-quality table
3. `frontend/js/dashboard.js` updates:
   - brief filtering/sorting pipeline
   - source-quality rendering
   - feed issue note in selected-game summary
4. `frontend/css/style.css` updates:
   - stale/noisy citation row highlighting
   - control sizing polish for Intelligence filters

## Tests Added/Updated

1. `backend/tests/test_intelligence_modules.py`
   - feed-health status reporting test (ok/error source mix)
   - noisy-content quality penalty test
   - noisy-doc injury suppression test
   - injury conflict signal test

## Validation

1. `PYTHONPATH=. ../backend/venv/bin/pytest tests -q` -> `77 passed, 1 warning`
2. `node --check frontend/js/dashboard.js` -> pass
3. Runtime checks:
   - `GET /api/v1/intelligence/game/{game_id}` includes citation quality + source quality summary
   - `GET /api/v1/intelligence/brief` still stable
   - `GET /api/v1/mlops/monitoring` unchanged and healthy

## Notes

1. In this local environment, Gemini/Chroma packages are unavailable in the active venv, so deterministic fallbacks are used.
2. Feed-health can be empty when no indexer audit record exists yet; fallback lookup now attempts to load latest stored health snapshot.
