# Phase 5B Retrain Automation Changelog

Date: 2026-03-01 (Asia/Kolkata)  
Scope: Controlled retrain queue automation (`SCR-141`, batch 1)

## Objective

Move retrain policy from recommendation-only output to guarded execution flow.

## Backend Changes

1. Added retrain queue persistence schema in `backend/src/data/init.sql`:
   - `retrain_jobs` table + season/status/time index
2. Added retrain store helpers in `backend/src/data/retrain_store.py`:
   - self-healing table bootstrap
   - active-job duplicate guard lookup
   - queued job creation with:
     - reasons/metrics/threshold snapshots
     - artifact snapshot metadata
     - rollback strategy metadata
   - retrain jobs listing query
3. Updated `backend/src/mlops/retrain_policy.py`:
   - execute mode (`dry_run=false`) now queues retrain jobs
   - duplicate-guard prevents repeated queued/running jobs for same season window
   - response now includes `execution` block (`duplicate_guard_triggered`, `retrain_job`, rollback strategy)
4. Updated `backend/src/api/mlops_routes.py`:
   - added `GET /api/v1/mlops/retrain/jobs`
5. Updated endpoint map in `backend/main.py` to include retrain jobs route.

## Frontend Changes

1. MLOps policy callout now includes latest retrain queued job status from:
   - `GET /api/v1/mlops/retrain/jobs`

## Tests

1. Added unit tests:
   - `backend/tests/test_retrain_policy.py`
     - execute-mode queue behavior
     - duplicate-guard behavior
2. Updated route tests:
   - `backend/tests/test_mlops_routes.py`
     - retrain execute-mode response shape
     - retrain jobs route shape

## Validation

1. `PYTHONPATH=. ../backend/venv/bin/pytest tests -q` -> `83 passed, 1 warning`
2. `node --check frontend/js/dashboard.js` -> pass
3. Runtime checks:
   - `GET /api/v1/mlops/retrain/policy?season=2025-26&dry_run=false`
     - first call: `action=queued-retrain`
     - subsequent call: `action=already-queued` (duplicate guard)
   - `GET /api/v1/mlops/retrain/jobs?season=2025-26&limit=5` returns queued job history

## Notes

This batch intentionally implements a queue-first control path, not direct model retraining execution. Full trainer worker integration can proceed safely in the next batch using the persisted `retrain_jobs` queue.
