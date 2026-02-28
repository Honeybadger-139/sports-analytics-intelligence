# Phase 3C Tabbed Redesign Changelog

Date: 2026-02-28 (Asia/Kolkata)  
Scope: Tab-based dashboard redesign + raw-data and quality-monitoring API integration

## Objective

Restructure the dashboard into clear workspaces and support your requested workflow:

1. NBA-focused home page
2. Raw Postgres table explorer (without features table)
3. Data quality / load-time / row-count monitoring tab
4. Analysis tab for model-level work

## Changes Implemented

1. Rebuilt frontend structure into tabs:
   - `Home`
   - `Raw Data Explorer`
   - `Data Quality`
   - `Analysis`
2. Added backend APIs for tab support:
   - `GET /api/v1/raw/tables`
   - `GET /api/v1/raw/{table_name}`
   - `GET /api/v1/quality/overview`
3. Added raw data pagination + season filtering in frontend JS.
4. Added quality panel renderers for:
   - row counts
   - timing metrics
   - quality checks
   - top-team performance
   - recent pipeline runs
5. Retained and integrated existing analysis modules:
   - predictions today
   - deep dive
   - model performance
   - bankroll tracker
6. Kept dark/light theme support and persistence.

## Files Changed

- `backend/src/api/routes.py`
- `backend/tests/test_routes.py`
- `frontend/index.html`
- `frontend/css/style.css`
- `frontend/js/dashboard.js`
- `docs/learning-notes/frontend/README.md`
- `docs/architecture/phase-execution-runbook.md`

## Validation

1. Backend tests:
   - `PYTHONPATH=. venv/bin/pytest tests -q` -> `63 passed, 1 warning`
2. Frontend script check:
   - `node --check frontend/js/dashboard.js`
3. Runtime endpoint checks:
   - `GET /api/v1/raw/tables?season=2025-26`
   - `GET /api/v1/raw/matches?season=2025-26&limit=2&offset=0`
   - `GET /api/v1/quality/overview?season=2025-26`
4. Browser launch:
   - `http://127.0.0.1:8001/`

## Follow-Up

1. Add column-level filters and search in Raw Data Explorer.
2. Add charts in Data Quality tab (timing trend + quality trend).
3. Add drag-and-pin metric cards for customizable quality monitoring.
