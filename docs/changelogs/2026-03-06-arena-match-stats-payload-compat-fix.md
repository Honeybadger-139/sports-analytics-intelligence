# 2026-03-06 - Arena match stats payload compatibility fix

## Type
Bug fix (frontend runtime stability)

## Goal
Fix Arena `Match Stats` deep-dive panel disappearing after loading when opening a game.

## Root cause
- Backend prediction explanation payload moved to:
  - `{ base_value, model_name, top_factors, all_factors }`
- Frontend deep-dive views still assumed legacy shape:
  - `{ model_name: ShapFactor[] }`
- UI attempted array operations on non-array fields (for example `base_value`), causing render failure.

## What changed
- Added explanation-shape normalization + type guards:
  - `frontend/src/components/Arena/MatchDeepDive.tsx`
  - `frontend/src/components/Pulse/GameStatsModal.tsx`
- Updated prediction hook state lifecycle to avoid stale/ambiguous rendering:
  - `frontend/src/hooks/useApi.ts`
- Updated explanation typings to support current + legacy payloads:
  - `frontend/src/types.ts`
- Added explicit fallback UI in Arena deep dive when no prediction payload is returned.

## Validation
- `cd frontend && npm run build` ✅

## Linear
- Issue: `SCR-202`
