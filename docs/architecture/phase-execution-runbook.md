# Phase Execution Runbook

This is the practical step-by-step guide to execute the project phase by phase without rushing.

## Why This Runbook Exists
- Keep implementation structured and measurable.
- Prevent "half-done" phases.
- Make interview prep easier because each phase has clear outcomes and evidence.

## Global Rules (Every Phase)
1. Start from a green baseline:
   - `cd backend`
   - `PYTHONPATH=. venv/bin/pytest tests -q`
2. Apply changes in small batches (one concern at a time).
3. Re-run tests after each batch.
4. Run runtime checks (DB/API) for the phase.
5. Update:
   - `docs/decisions/decision-log.md`
   - relevant `docs/learning-notes/...`
   - Linear tracker issue and phase issue

---

## Phase 1: Data + Feature Reliability

### Objective
Ensure ingestion and feature generation are complete, leakage-safe, and observable.

### Completed Scope
1. H2H feature stage is now executed in pipeline.
2. Pregame non-leaky streak feature is implemented.
3. Advanced metrics (`off/def rating`, `pace`, `eFG`, `TS`) are populated and backfilled.
4. `pipeline_audit` self-heals on legacy DB volumes.

### Verification Commands
```bash
cd backend
PYTHONPATH=. venv/bin/python src/data/ingestion.py
PYTHONPATH=. venv/bin/python src/data/feature_store.py
PYTHONPATH=. venv/bin/pytest tests -q
```

### DB Spot Checks
```sql
-- Advanced metric completeness
SELECT
  COUNT(*) AS total_rows,
  SUM(CASE WHEN offensive_rating IS NOT NULL THEN 1 ELSE 0 END) AS off_rating_filled,
  SUM(CASE WHEN defensive_rating IS NOT NULL THEN 1 ELSE 0 END) AS def_rating_filled,
  SUM(CASE WHEN pace IS NOT NULL THEN 1 ELSE 0 END) AS pace_filled
FROM team_game_stats tgs
JOIN matches m ON m.game_id = tgs.game_id
WHERE m.season = '2025-26';

-- Audit table health
SELECT to_regclass('public.pipeline_audit');
SELECT module, status, sync_time
FROM pipeline_audit
ORDER BY sync_time DESC
LIMIT 10;
```

### Definition of Done
1. Core tests pass.
2. Advanced metrics are populated for current season rows.
3. Feature pipeline runs without audit-table failure.
4. `/api/v1/system/status` returns without crashing on audit reads.

---

## Phase 2: Prediction Operations Backend

### Objective
Move from "single game prediction endpoint" to operational prediction services.

### Planned Scope
1. Add endpoint for today's predictions list.
2. Persist predictions to `predictions` table.
3. Add model performance endpoint (accuracy/calibration over time).
4. Add basic bankroll ledger APIs for `bets`.

### Definition of Done
1. New endpoints have tests.
2. Predictions are auditable in DB.
3. Performance endpoint returns reproducible metrics from persisted outcomes.

---

## Phase 3: Frontend Expansion

### Objective
Implement dashboard modules shown in architecture (not just system health).

### Planned Scope
1. Today's Matches page.
2. Match Deep Dive (prediction + SHAP factors).
3. Bankroll Tracker view.
4. Model Performance charts.

### Definition of Done
1. Frontend consumes Phase 2 APIs.
2. Empty/error states are handled cleanly.
3. Mobile and desktop both usable.

---

## Phase 4: Intelligence Layer (LLM + Rules)

### Objective
Implement `news_agent` + rule engine to add context-aware insights.

### Planned Scope
1. News ingestion and embedding store.
2. Retrieval + LLM summarization path.
3. Rule filters for prediction confidence adjustments.

### Definition of Done
1. Intelligence output is deterministic enough for audit trails.
2. Prompt and retrieval path are documented in learning notes.

---

## Phase 5: MLOps Loop

### Objective
Production-style monitoring and retrain triggers.

### Planned Scope
1. Monitoring job for drift and performance.
2. Retrain trigger policy.
3. Versioned model artifact governance.

### Definition of Done
1. Monitoring produces actionable alerts.
2. Retraining flow is testable and repeatable.
3. Runbooks and decision records are complete.
