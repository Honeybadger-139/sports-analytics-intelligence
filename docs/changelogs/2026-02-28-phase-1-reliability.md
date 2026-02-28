# Phase 1 Reliability Changelog

Date: 2026-02-28 (Asia/Kolkata)  
Scope: Feature correctness, advanced-metric completeness, observability schema hardening

## Objective

Close architecture-to-implementation gaps from `system-architecture.png` and stabilize the data/feature layer before Phase 2 API expansion.

## Step-By-Step Execution

1. Enabled missing feature stage execution:
   - Wired `compute_h2h_features()` into the feature pipeline.
2. Replaced placeholder streak feature:
   - Implemented `compute_streak_features()` for leakage-safe **pregame** streaks.
3. Added advanced metric derivation in ingestion:
   - `offensive_rating`, `pace`, `effective_fg_pct`, `true_shooting_pct`.
4. Added targeted incremental backfill:
   - Included historical `game_id`s with missing advanced columns while preserving watermark logic.
5. Added defensive rating fallback:
   - SQL self-join backfill using opponent points and pace when row-level path is unavailable.
6. Fixed observability schema drift:
   - Added runtime bootstrap for `pipeline_audit` and bounded retry on audit insert.
7. Hardened read path:
   - `/api/v1/system/status` now degrades gracefully if `pipeline_audit` is absent.
8. Updated tests and re-validated end-to-end runtime behavior.
9. Updated architecture and learning docs to reflect all above changes.

## Files Changed In This Session

- `backend/src/data/feature_store.py`
- `backend/src/data/ingestion.py`
- `backend/src/data/audit_store.py`
- `backend/src/api/routes.py`
- `backend/tests/test_feature_store_pipeline.py`
- `backend/tests/test_ingestion_advanced_metrics.py`
- `backend/tests/test_audit_bootstrap.py`
- `backend/tests/test_routes.py`
- `docs/architecture/data-pipeline.md`
- `docs/architecture/phase-execution-runbook.md`
- `docs/decisions/decision-log.md`
- `docs/learning-notes/data-layer/data-ingestion.md`
- `docs/learning-notes/data-layer/feature-engineering.md`
- `docs/learning-notes/data-layer/README.md`
- `docs/learning-notes/future-learning-roadmap.md`
- `docs/README.md`

## Decision Notes

1. Prefer selective backfill over full historical replay for cost and API stability.
2. Keep feature semantics pregame-only to prevent leakage.
3. Use bounded auto-bootstrap for critical observability schema to reduce operational toil.
4. Keep API changes additive and failure-tolerant for existing frontend compatibility.

## Validation Evidence

Test gate:

```bash
cd backend
PYTHONPATH=. venv/bin/pytest tests -q
```

Result:

- `48 passed, 1 warning`

Runtime evidence:

1. Ingestion completed and persisted advanced metrics.
2. Feature pipeline recomputed advanced rolling fields + H2H + streak.
3. `pipeline_audit` auto-created and now records successful `feature_store` and `ingestion` entries.

## Follow-Up Backlog

1. Start Phase 2 backend expansion:
   - prediction persistence
   - today's prediction feed
   - model performance endpoints
2. Keep observability contract stable as new services are added.
3. Add DB-backed integration tests for ingestion + audit bootstrap behavior.

## Learning Topics For Future

1. Leakage-safe temporal feature design patterns.
2. Migration-safe schema evolution for long-lived Docker volumes.
3. Robust fallback derivations for partially available source signals.
4. Audit-table-driven SLOs and alert design.
