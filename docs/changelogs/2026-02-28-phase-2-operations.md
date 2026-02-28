# Phase 2 Operations Changelog

Date: 2026-02-28 (Asia/Kolkata)  
Scope: Prediction operations APIs + bankroll ledger APIs + validation and documentation

## Objective

Complete Phase 2 backend scope from the architecture/runbook:

1. Daily prediction feed + persistence
2. Historical performance metrics from persisted outcomes
3. Basic bankroll ledger operations for `bets`

## Step-By-Step Execution

1. Added prediction persistence utility (`prediction_store.py`) for idempotent upsert and outcome sync.
2. Added `/api/v1/predictions/today` for batch inference and optional persistence.
3. Added `/api/v1/predictions/performance` for season/model-level accuracy and Brier metrics.
4. Added dedicated bet ledger store (`bet_store.py`) with:
   - create bet (`pending`)
   - list bets (filters)
   - settle bet (`win/loss/push`) with deterministic PnL
   - bankroll summary (stake, pnl, roi, open/settled counts)
5. Added API endpoints:
   - `POST /api/v1/bets`
   - `GET /api/v1/bets`
   - `POST /api/v1/bets/{bet_id}/settle`
   - `GET /api/v1/bets/summary`
6. Added/updated tests for route contracts and store behavior.
7. Updated docs (`runbook`, `decision log`, `learning notes`, architecture references).

## Files Changed In This Session

- `backend/src/api/routes.py`
- `backend/src/data/prediction_store.py`
- `backend/src/data/bet_store.py`
- `backend/main.py`
- `backend/tests/test_routes.py`
- `backend/tests/test_prediction_store.py`
- `backend/tests/test_bet_store.py`
- `docs/architecture/phase-execution-runbook.md`
- `docs/architecture/data-pipeline.md`
- `docs/architecture/system-design.md`
- `docs/decisions/decision-log.md`
- `docs/learning-notes/api-layer/README.md`

## Validation Evidence

Test gate:

```bash
cd backend
PYTHONPATH=. venv/bin/pytest tests -q
```

Result:

- `60 passed, 1 warning`
- warning remains environment-level SSL/runtime warning (tracked in backlog)

Runtime smoke checks (`uvicorn` on `127.0.0.1:8001`):

1. `GET /api/v1/predictions/today` returns valid payload.
2. `GET /api/v1/bets/summary` returns zeroed ledger metrics initially.
3. `POST /api/v1/bets` successfully creates ledger row.
4. `POST /api/v1/bets/1/settle` updates result and computes expected PnL.
5. `GET /api/v1/bets?limit=3` returns enriched history row with teams + season.

## Follow-Up Backlog

1. Add idempotency key / external reference for bet ingestion from future sportsbook connectors.
2. Add bankroll time-series endpoint for charting equity curve on frontend.
3. Add role-based safeguards before enabling any automated bet execution flow.
