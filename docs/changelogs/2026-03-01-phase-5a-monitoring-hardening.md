# Phase 5A Monitoring Hardening Changelog

Date: 2026-03-01 (Asia/Kolkata)  
Scope: Monitoring snapshot persistence + trend API foundation (`SCR-140`, batch 1)

## Objective

Extend MLOps monitoring from point-in-time metrics to trend-ready observability.

## Backend Changes

1. Added snapshot persistence table schema in `backend/src/data/init.sql`:
   - `mlops_monitoring_snapshot`
2. Added persistence helpers in `backend/src/data/mlops_store.py`:
   - self-healing table/index bootstrap
   - snapshot insert helper
   - trend query helper
3. Updated `backend/src/mlops/monitoring.py`:
   - monitoring overview now persists a snapshot each call
   - added `get_monitoring_trend(...)` service function
4. Updated `backend/src/api/mlops_routes.py`:
   - added `GET /api/v1/mlops/monitoring/trend?season=...&days=...&limit=...`
5. Updated root endpoint map in `backend/main.py` to include trend route.

## Frontend Changes

1. Updated Intelligence tab MLOps panel:
   - added trend summary callout (`14-day snapshots / avg accuracy / latest alert count`)
2. Frontend now calls trend API in `loadMlopsMonitoring()`:
   - `GET /api/v1/mlops/monitoring/trend`

## Tests

1. Updated `backend/tests/test_mlops_routes.py`:
   - added route test for `/api/v1/mlops/monitoring/trend`

## Validation

1. `PYTHONPATH=. ../backend/venv/bin/pytest tests -q` -> `78 passed, 1 warning`
2. `node --check frontend/js/dashboard.js` -> pass
3. Runtime checks:
   - `/api/v1/mlops/monitoring?season=2025-26` -> 200
   - `/api/v1/mlops/monitoring/trend?season=2025-26&days=14&limit=5` -> 200 with snapshot points

## Notes

Trend endpoint currently returns raw snapshot points to keep chart integration simple. Chart rendering can be added in the next UI pass without changing backend contracts.
