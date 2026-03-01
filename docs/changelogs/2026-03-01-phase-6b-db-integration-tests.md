# Phase 6B DB Integration Invariants Changelog

Date: 2026-03-01 (Asia/Kolkata)  
Scope: DB-backed ingestion integrity tests (`SCR-125`)

## Objective

Add true database-backed integration coverage for core ingestion audit invariants, with isolated test scope and negative-path validation.

## Changes

1. Added integration test file:
   - `backend/tests/test_ingestion_db_invariants.py`
2. Implemented real Postgres-backed test harness:
   - validates DB connectivity and skips cleanly when DB is unreachable
   - uses per-test `TEMP` tables (`matches`, `team_game_stats`, `player_game_stats`) to shadow production tables
   - wraps each test in rollback scope for isolation
3. Added invariant scenarios:
   - passing baseline (all rules satisfied)
   - failing fixture: missing one team stats row
   - failing fixture: missing player stats
   - failing fixture: null score in completed match
4. Updated top-level test instructions in `README.md` to include DB-backed invariant test command.

## Validation

1. `cd backend && PYTHONPATH=. venv/bin/pytest tests/test_ingestion_db_invariants.py -q`
   - Result: `4 passed, 1 warning`
2. Combined gate check:
   - `cd backend && PYTHONPATH=. venv/bin/pytest tests/test_ingestion_retry.py tests/test_routes.py tests/test_config.py tests/test_ingestion_db_invariants.py -q`
   - Result: `34 passed, 1 warning`

## Notes

These tests verify SQL-level audit logic against a real DB engine while remaining deterministic and non-invasive due to temp-table isolation.
