# Phase 0 Hardening Changelog

Date: 2026-02-28 (Asia/Kolkata)
Scope: Data Foundation reliability, observability, tests, and documentation consistency

## Objective

Harden Phase 0 so ingestion and system-status behaviors are reliable, testable, and documented for future handoffs.

## Step-By-Step Execution

1. Fixed ingestion retry constant references.
2. Removed invalid duplicate script tail from ingestion entrypoint.
3. Introduced structured audit summary from ingestion integrity checks.
4. Persisted audit summary into `pipeline_audit.details.audit_violations`.
5. Exposed audit summary additively via `/api/v1/system/status` under `pipeline.audit_violations`.
6. Switched pipeline file logging to rotating handlers for ingestion and feature store.
7. Added regression tests for retry behavior and structured audit persistence.
8. Updated route tests to match runtime behavior:
   - `/` serves frontend HTML
   - `/api/v1/health` returns `status=healthy`
9. Standardized phase naming in docs:
   - Phase 0: Data Foundation
   - Phase 0.5: Resilience/Observability
   - Phase 1: Prediction Engine
10. Added Phase 0 Definition of Done in project documentation.

## Files Changed In This Session

- `backend/src/data/ingestion.py`
- `backend/src/data/feature_store.py`
- `backend/src/api/routes.py`
- `backend/tests/test_ingestion_retry.py`
- `backend/tests/test_routes.py`
- `README.md`
- `docs/decisions/decision-log.md`
- `docs/learning-notes/data-layer/README.md`
- `docs/learning-notes/data-layer/data-ingestion.md`
- `docs/learning-notes/data-layer/api-header-engineering.md`
- `docs/learning-notes/ml-engine/README.md`

## Decision Notes

1. Keep API change additive (`pipeline.audit_violations`) to avoid client breakage.
2. Represent integrity checks as structured data, not only logs, to improve observability.
3. Use rotating log files to avoid unbounded local file growth.
4. Align tests to product behavior when mount order causes `/` to serve static HTML.

## Validation Evidence

Environment setup:

- Installed `pytest` and `httpx` in `backend/venv`.

Test command:

```bash
cd backend
../backend/venv/bin/python -m pytest -q tests/test_ingestion_retry.py tests/test_routes.py tests/test_config.py
```

Result:

- `20 passed, 1 warning`
- Warning: local SSL/urllib3 runtime warning (non-blocking, environment-level)

## Follow-Up Backlog

1. Add DB-backed integration tests for ingestion invariants.
2. Add CI workflow for regression test suite.
3. Resolve local runtime SSL warning for environment parity.

## Learning Topics For Future

1. Contract-driven observability patterns for data pipelines.
2. Test architecture for mixed mocked + DB-backed validation.
3. FastAPI routing/mount precedence and testing strategy.
4. Logging lifecycle management and rotation policies.
5. Runtime/toolchain parity (local vs CI vs deployment).
