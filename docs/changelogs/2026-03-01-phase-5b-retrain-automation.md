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
   - added `POST /api/v1/mlops/retrain/worker/run-next`
5. Updated endpoint map in `backend/main.py` to include retrain jobs route.
6. Added retrain worker integration:
   - `backend/src/mlops/retrain_worker.py`
   - claims queued jobs, marks `running`, finalizes to `completed/failed`
   - supports `execute=true` (actual training pipeline) and `execute=false` (safe simulation)
   - records audit events for worker runs
7. Expanded retrain job lifecycle fields:
   - `started_at`, `completed_at`, `run_details`, `error`

## Frontend Changes

1. MLOps policy callout now includes latest retrain queued job status from:
   - `GET /api/v1/mlops/retrain/jobs`

## Tests

1. Added unit tests:
   - `backend/tests/test_retrain_policy.py`
     - execute-mode queue behavior
     - duplicate-guard behavior
   - `backend/tests/test_retrain_worker.py`
     - simulate completion path
     - no-op path
     - failure path
2. Updated route tests:
   - `backend/tests/test_mlops_routes.py`
     - retrain execute-mode response shape
     - retrain jobs route shape
     - retrain worker route shape

## Validation

1. `PYTHONPATH=. ../backend/venv/bin/pytest tests -q` -> `87 passed, 1 warning`
2. `node --check frontend/js/dashboard.js` -> pass
3. Runtime checks:
   - `GET /api/v1/mlops/retrain/policy?season=2025-26&dry_run=false`
     - first call: `action=queued-retrain`
     - subsequent call: `action=already-queued` (duplicate guard)
   - `GET /api/v1/mlops/retrain/jobs?season=2025-26&limit=5` returns queued job history
   - `POST /api/v1/mlops/retrain/worker/run-next?execute=false`
     - consumes queued job and transitions lifecycle to `completed`
     - next call returns `noop` when queue is empty

## Notes

This implementation keeps a queue-first control model while adding worker lifecycle integration. `execute=true` is available for actual trainer execution, while `execute=false` provides a safe operational simulation mode.
