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

### Implemented Scope
1. `GET /api/v1/predictions/today` with optional persistence toggle (`persist=true` default).
2. Prediction upsert service with legacy-table bootstrap fallback.
3. `GET /api/v1/predictions/performance` with accuracy/confidence/Brier aggregation.
4. Bankroll ledger API set:
   - `POST /api/v1/bets`
   - `GET /api/v1/bets`
   - `POST /api/v1/bets/{bet_id}/settle`
   - `GET /api/v1/bets/summary`
5. Route + store regression tests covering persistence, settlement, and summaries.
6. Phase 2 operations flow diagram saved at `docs/images/phase-2-ops-flow.mmd`.

### Verification Commands
```bash
cd backend
PYTHONPATH=. venv/bin/pytest tests -q
curl -sS http://127.0.0.1:8001/api/v1/predictions/today
curl -sS http://127.0.0.1:8001/api/v1/predictions/performance?season=2025-26
curl -sS http://127.0.0.1:8001/api/v1/bets/summary
```

### Definition of Done
1. New endpoints have tests.
2. Predictions are auditable in DB.
3. Performance endpoint returns reproducible metrics from persisted outcomes.
4. Bets ledger supports create/list/settle/summary with deterministic PnL.

---

## Phase 3: Frontend Expansion

### Objective
Implement dashboard modules shown in architecture (not just system health).

### Planned Scope
1. Today's Matches page.
2. Match Deep Dive (prediction + SHAP factors).
3. Bankroll Tracker view.
4. Model Performance charts.

### Implemented Scope (Phase 3A)
1. Rebuilt `frontend/index.html` into an operations console with modular sections.
2. Integrated live API modules:
   - Today's Predictions (`/predictions/today`)
   - Match Deep Dive (`/matches`, `/predictions/game/{id}`, `/features/{id}`)
   - Model Performance (`/predictions/performance`)
   - Bankroll Tracker (`/bets/summary`, `/bets`)
3. Added explicit loading, empty, and error states in each module.
4. Updated responsive layout and visual hierarchy for desktop/mobile usage.

### Implemented Scope (Phase 3C Redesign)
1. Converted frontend into tab-based information architecture:
   - `Home`
   - `Raw Data Explorer`
   - `Data Quality`
   - `Analysis`
2. Added raw-table APIs for Postgres exploration (excluding feature table):
   - `GET /api/v1/raw/tables`
   - `GET /api/v1/raw/{table_name}`
3. Added quality-monitoring API:
   - `GET /api/v1/quality/overview`
4. Wired tab-specific frontend interactions:
   - raw table selector + pagination
   - quality metrics + recent run history
   - analysis workspace retained for predictions/deep-dive/performance/bankroll
5. Preserved light/dark theme toggle with persisted preference.
6. Added tabbed frontend flow diagram: `docs/images/phase-3c-tabbed-dashboard.mmd`.

### Verification Commands
```bash
cd backend
PYTHONPATH=. venv/bin/pytest tests -q
PYTHONPATH=. venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001
curl -sS http://127.0.0.1:8001/
curl -sS http://127.0.0.1:8001/api/v1/predictions/today
curl -sS 'http://127.0.0.1:8001/api/v1/matches?season=2025-26&limit=1'
curl -sS http://127.0.0.1:8001/api/v1/predictions/game/0022500859
curl -sS http://127.0.0.1:8001/api/v1/features/0022500859
curl -sS http://127.0.0.1:8001/api/v1/bets/summary
curl -sS 'http://127.0.0.1:8001/api/v1/bets?season=2025-26&limit=3'
curl -sS 'http://127.0.0.1:8001/api/v1/raw/tables?season=2025-26'
curl -sS 'http://127.0.0.1:8001/api/v1/raw/matches?season=2025-26&limit=2&offset=0'
curl -sS 'http://127.0.0.1:8001/api/v1/quality/overview?season=2025-26'
```

### Definition of Done
1. Frontend consumes Phase 2 APIs.
2. Empty/error states are handled cleanly.
3. Mobile and desktop both usable.

---

## Phase 4: Intelligence Layer (RAG + Rules)

### Objective
Add Retrieval-Augmented Generation (RAG) so predictions are accompanied by grounded context, not just model probabilities.

### Why This Phase Matters
1. Makes predictions explainable in business terms (injuries, lineup news, fatigue, matchup context).
2. Demonstrates practical LLM usage in daily operations.
3. Creates interview-ready evidence of AI orchestration (retrieval + generation + guardrails).

### Planned Scope
1. **Phase 4A — Context Ingestion + Vector Index**
   - Build `news_agent.py` pipeline to ingest NBA context sources (news/injury reports/team updates).
   - Chunk and embed documents with metadata (`team`, `game_date`, `source`, `published_at`).
   - Store embeddings in vector store (ChromaDB in current architecture).
2. **Phase 4B — Retrieval + Summarization Service**
   - Add API endpoint for game-specific context retrieval and summarization:
     - `GET /api/v1/intelligence/game/{game_id}`
   - Add API endpoint for daily intelligence brief:
     - `GET /api/v1/intelligence/brief?date=YYYY-MM-DD`
   - Return structured payload: summary, risk signals, confidence, and citations.
3. **Phase 4C — Rule Engine Overlay**
   - Implement deterministic post-retrieval rules:
     - injury severity thresholds
     - back-to-back/rest/travel flags
     - stale-context rejection
   - Rules adjust confidence bands but never mutate raw model probabilities silently.
4. **Phase 4D — Dashboard Integration**
   - Add an `Intelligence` workspace/tab in frontend.
   - Add "Context Brief" card to Match Deep Dive with source citations.
   - Add "Ask" interaction scoped to retrieved context only (no free-form ungrounded output).

### Validation Gates
1. Retrieval relevance checks on sampled games (`top_k` quality and source freshness).
2. Response schema contract tests for intelligence endpoints.
3. Hallucination guard: every generated insight must include at least one citation.
4. Latency SLO target for intelligence endpoints (p95 under agreed threshold).
5. Prompt + retrieval strategy documented in learning notes with example traces.

### Definition of Done
1. RAG endpoints are available and tested.
2. Dashboard shows grounded context with citations.
3. Rule overlays are deterministic and auditable.
4. Intelligence outputs are reproducible from stored retrieval context.

### Implemented Scope (Phase 4A + 4B Baseline)
1. Added intelligence backend modules:
   - `news_agent.py` (RSS ingestion + normalization)
   - `embeddings.py` (Gemini primary, deterministic fallback)
   - `vector_store.py` (Chroma primary, JSON fallback)
   - `retriever.py`, `summarizer.py`, `rules.py`, `service.py`
2. Added intelligence APIs:
   - `GET /api/v1/intelligence/game/{game_id}`
   - `GET /api/v1/intelligence/brief`
3. Added `intelligence_audit` persistence with self-healing bootstrap logic.
4. Added Analysis-tab `Context Brief (RAG)` card:
   - summary + risk chips + citation table
5. Added full `Intelligence` tab baseline:
   - daily brief table
   - selected-game citation inspector
   - risk signal display
6. Added architecture flow diagram: `docs/images/phase-4-5-intelligence-mlops-flow.mmd`.
7. Added Phase 4B hardening controls:
   - source-quality scoring + noisy-content penalties
   - feed-health telemetry in intelligence responses
   - rule precision pass (noise-aware injury signals + conflict detection)
   - Intelligence tab sorting/filtering and stale/noisy citation highlighting

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

### Implemented Scope (Phase 5 Foundation)
1. Added `src/mlops/monitoring.py` for:
   - evaluated prediction counts
   - accuracy/Brier aggregation
   - freshness checks and alert generation
2. Added `src/mlops/retrain_policy.py` for deterministic dry-run policy evaluation.
3. Added MLOps APIs:
   - `GET /api/v1/mlops/monitoring`
   - `GET /api/v1/mlops/retrain/policy?dry_run=true`
4. Exposed model artifact snapshot in `/api/v1/system/status`.
5. Integrated MLOps cards into frontend Intelligence tab (monitoring + dry-run policy summary).
6. Added snapshot persistence + trend readiness:
   - `mlops_monitoring_snapshot` persistence layer
   - `GET /api/v1/mlops/monitoring/trend`
   - frontend trend summary callout wired to trend API
7. Added deterministic escalation policy:
   - alert-level `recommended_action`
   - payload-level escalation summary (`none|active|watch|incident`)
8. Added retrain queue automation baseline:
   - execute mode queueing in `/api/v1/mlops/retrain/policy?dry_run=false`
   - duplicate-guard to avoid repeated queued jobs
   - `GET /api/v1/mlops/retrain/jobs` for audit visibility
9. Added worker lifecycle integration:
   - `POST /api/v1/mlops/retrain/worker/run-next`
   - lifecycle states now observable: `queued -> running -> completed/failed`

### Verification Commands
```bash
cd backend
PYTHONPATH=. venv/bin/pytest tests -q
curl -sS 'http://127.0.0.1:8001/api/v1/intelligence/game/0022500859?season=2025-26'
curl -sS 'http://127.0.0.1:8001/api/v1/intelligence/brief?date=2026-02-28&season=2025-26&limit=5'
curl -sS 'http://127.0.0.1:8001/api/v1/mlops/monitoring?season=2025-26'
curl -sS 'http://127.0.0.1:8001/api/v1/mlops/monitoring/trend?season=2025-26&days=14&limit=5'
curl -sS 'http://127.0.0.1:8001/api/v1/mlops/retrain/policy?season=2025-26&dry_run=true'
curl -sS 'http://127.0.0.1:8001/api/v1/mlops/retrain/policy?season=2025-26&dry_run=false'
curl -sS 'http://127.0.0.1:8001/api/v1/mlops/retrain/jobs?season=2025-26&limit=5'
curl -sS -X POST 'http://127.0.0.1:8001/api/v1/mlops/retrain/worker/run-next?season=2025-26&execute=false'
```

### Incident Workflow (Phase 5A)
1. Poll `GET /api/v1/mlops/monitoring` on schedule.
2. Check `escalation.state`:
   - `none`: continue normal monitoring.
   - `active`: monitor next snapshot and confirm no upward trend.
   - `watch`: investigate now (data freshness, model outcomes, ingestion anomalies).
   - `incident`: open incident and freeze non-essential model/retrain changes until triage completes.
3. Use `recommended_action` at alert row level for immediate operator action.
4. Confirm stabilization when two consecutive snapshots return `escalation.state=none`.

### Retrain Guardrail Workflow (Phase 5B Baseline)
1. Evaluate policy in dry-run:
   - `GET /api/v1/mlops/retrain/policy?season=...&dry_run=true`
2. Queue retrain only when ready:
   - `GET /api/v1/mlops/retrain/policy?season=...&dry_run=false`
3. Confirm duplicate guard behavior:
   - repeated execute-mode calls should return `action=already-queued` while queued/running job exists.
4. Inspect queued jobs:
   - `GET /api/v1/mlops/retrain/jobs?season=...`
5. Run worker lifecycle (safe mode first):
   - `POST /api/v1/mlops/retrain/worker/run-next?season=...&execute=false`
6. If approved for full training execution:
   - `POST /api/v1/mlops/retrain/worker/run-next?season=...&execute=true`
7. Verify completion/failed status and artifact snapshot in retrain jobs list.
8. Rollback rule (documented baseline):
   - revert to previous model artifact if post-retrain accuracy drops by >0.03 or Brier worsens by >0.02.
