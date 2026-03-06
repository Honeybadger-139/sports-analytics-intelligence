# 2026-03-06 - Arena model performance bootstrap fix

## Type
Bug fix (backend data availability + frontend model-key consistency)

## Goal
Fix Arena `Model Performance` showing a permanent empty state even when season games exist.

## Root cause
- Performance endpoint was reading only from persisted `predictions` rows.
- Daily prediction persistence can write zero rows on dates with no games.
- Result: `predictions/performance` returned no metrics (`evaluated_models=0`) although completed matches existed.

## What changed
- Added historical bootstrap path in:
  - `backend/src/api/routes.py`
  - new helper `_bootstrap_predictions_from_completed_games(...)`
  - `/api/v1/predictions/performance` now supports:
    - `bootstrap_if_empty` (default `true`)
    - `bootstrap_limit` (default `1500`)
    - `bootstrap` metadata in response
- Added safer feature-frame construction in bootstrap loop to avoid noisy pandas dtype warnings.
- Added `lightgbm` model-key compatibility in Arena UI:
  - `frontend/src/components/Arena/ModelPerformance.tsx`
  - `frontend/src/components/Arena/MatchDeepDive.tsx`
  - `frontend/src/components/Arena/TodaysPicks.tsx`

## Validation
- `cd backend && PYTHONPATH=. venv/bin/pytest tests/test_routes.py -q` ✅
- `cd frontend && npm run build` ✅
- Live check:
  - `GET /api/v1/predictions/performance?season=2025-26`
  - returned non-empty metrics (`evaluated_models=4`, 935 evaluated games per model)

## Linear
- Issue: `SCR-203`
