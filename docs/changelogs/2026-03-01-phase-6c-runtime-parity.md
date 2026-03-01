# Phase 6C Runtime Parity Changelog

Date: 2026-03-01 (Asia/Kolkata)  
Scope: local runtime parity for SSL/toolchain warning removal (`SCR-127`)

## Objective

Remove recurring `urllib3` LibreSSL/OpenSSL warning from normal test runs and align local runtime expectations with CI.

## Changes

1. Pinned compatibility dependency in `backend/requirements.txt`:
   - `urllib3<2`
2. Standardized local interpreter baseline:
   - added `.python-version` with `3.11.11`
   - updated `README.md` setup command to `python3.11 -m venv venv`
3. Reinstalled compatibility dependency in active environment:
   - `backend/venv/bin/pip install "urllib3<2"`

## Validation

1. Warning-free regression check:
   - `cd backend && PYTHONPATH=. venv/bin/pytest tests/test_ingestion_retry.py tests/test_routes.py tests/test_config.py -q`
   - Result: `30 passed`
2. Combined validation with DB-backed invariant suite:
   - `cd backend && PYTHONPATH=. venv/bin/pytest tests/test_ingestion_retry.py tests/test_routes.py tests/test_config.py tests/test_ingestion_db_invariants.py -q`
   - Result: `34 passed`

## Notes

CI already runs on Python 3.11. This batch aligns local guidance and dependency compatibility to keep local runs stable and warning-free.
