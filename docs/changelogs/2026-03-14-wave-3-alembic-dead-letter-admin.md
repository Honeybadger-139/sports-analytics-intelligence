# Wave 3 — Alembic Auto-Migration, Dead-Letter Inspection & Runtime Admin

**Date:** 2026-03-14
**Linear:** SCR-298 (Wave 3)
**Status:** Complete

---

## Summary

Wave 3 hardened operational reliability by automating database schema migrations at startup, exposing a dead-letter queue inspection API for the ingestion pipeline, and adding a runtime configuration management endpoint so operators can tune system parameters without a redeploy.

---

## Changes

### 1. Alembic Auto-Migration on Startup (`backend/main.py`)

- Added Alembic `upgrade head` subprocess call inside the FastAPI `lifespan` context manager
- Runs before the scheduler starts and before any request is served
- Captures `stdout`/`stderr`; logs success or warnings — never hard-fails startup
- Ensures production containers are always schema-current on boot without a manual migration step

**Why this matters:** Eliminates the "forgot to run migrations" class of production incidents. The migration is idempotent (`upgrade head` is a no-op if already current), so running it on every restart is safe.

### 2. Dead-Letter Lab Routes (`backend/src/api/lab_routes.py`)

- New `GET /api/v1/lab/dead-letter` endpoint exposing the ingestion dead-letter queue
- Returns failed ingestion records with retry count, last error, and first/last attempt timestamps
- Supports `limit` and `season` query parameters
- Registered via `app.include_router(lab_router)` in `main.py`

**Why this matters:** Without visibility into dead-letter records, silent ingestion failures go unnoticed until a data quality alert fires hours later. This endpoint gives operators immediate inspection capability.

### 3. Runtime Config Admin Routes (`backend/src/api/admin_routes.py`)

- New `GET /api/v1/admin/config` and `PATCH /api/v1/admin/config` endpoints
- Allows runtime adjustment of tunable parameters: MLOps thresholds, scheduler hours, rate limits
- Changes are in-memory only (restart resets to env var defaults) — intentional for safety
- Returns current effective config values for observability

**Why this matters:** Avoids code redeploys for threshold tuning during incidents. When accuracy drops mid-season, an operator can lower `MLOPS_ACCURACY_THRESHOLD` to stop false-positive retrain triggers without touching CI/CD.

---

## Files Changed

| File | Change Type |
|---|---|
| `backend/main.py` | Modified — Alembic lifespan startup block; `lab_router` + `admin_router` registration |
| `backend/src/api/lab_routes.py` | New — Dead-letter inspection API |
| `backend/src/api/admin_routes.py` | New — Runtime config management API |
| `backend/tests/test_lab_admin_routes.py` | New — Route-level tests for both routers |

---

## Test Results

All existing tests pass. New tests in `test_lab_admin_routes.py` cover:
- Dead-letter list (empty state, populated state)
- Admin config GET (returns all tunables)
- Admin config PATCH (validates key names, rejects unknown keys)

---

## Interview Angle

> "How do you handle zero-downtime schema changes in a FastAPI + PostgreSQL system?"

**Senior answer:** Alembic migrations are idempotent and can be run at container startup via a subprocess call in the FastAPI `lifespan` hook. This eliminates drift between code and schema without requiring a separate migration job in the CI/CD pipeline. The key trade-off is that startup time increases slightly — acceptable for a backend service, not acceptable for a Lambda cold-start scenario.
