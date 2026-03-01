# Phase 6A CI Regression Gate Changelog

Date: 2026-03-01 (Asia/Kolkata)  
Scope: GitHub Actions regression workflow for backend contracts (`SCR-126`)

## Objective

Add an automated regression gate on every push/PR to `main` so critical API and reliability contracts are continuously validated.

## Changes

1. Added workflow file:
   - `.github/workflows/backend-regression.yml`
2. Workflow behavior:
   - triggers on `push` and `pull_request` to `main`
   - uses Python 3.11 on `ubuntu-latest`
   - enables pip dependency cache keyed by `backend/requirements.txt`
   - runs targeted regression suite from `backend/`:
     - `tests/test_ingestion_retry.py`
     - `tests/test_routes.py`
     - `tests/test_config.py`

## Validation

1. Local parity check executed with the same suite:
   - `PYTHONPATH=. venv/bin/pytest tests/test_ingestion_retry.py tests/test_routes.py tests/test_config.py -q`
2. Working tree confirms workflow file and docs updates only for this batch.

## Notes

This is a fast CI guardrail by design. Full-suite runtime checks and phase-gate validations remain part of release runbook execution.
