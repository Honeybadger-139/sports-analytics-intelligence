# 2026-03-05 - Phase 6A: Global sport/league/season context foundation

## Type
Implementation (frontend foundation)

## Goal
Start approved multi-sport expansion with a safe first step: global context selection without breaking existing NBA-only backend paths.

## What changed
- Added `frontend/src/config/sports.ts`
  - Sport catalog: NBA, F1, Tennis, Football, Cricket
  - League options per sport
  - Season option helpers and default context
- Added `frontend/src/context/SportContext.tsx`
  - Global `sport + league + season` context
  - LocalStorage persistence (`sai_global_sport_context_v1`)
  - Hooks for selector updates
- Updated `frontend/src/App.tsx`
  - Wrapped app shell with `SportContextProvider`
- Updated `frontend/src/components/Navbar.tsx`
  - Added compact global selectors: Sport / League / Season
  - Added availability badge: `Live Data` for NBA, `Planned` for others
- Updated `frontend/src/index.css`
  - Added styling for navbar context controls and responsive behavior
- Updated dashboard metadata contracts and usage:
  - `frontend/src/types.ts`
  - `frontend/src/pages/DashboardCreate.tsx`
  - `frontend/src/pages/Dashboard.tsx`
  - Saved dashboards now keep selected sport/league/season context

## Guardrail behavior
- Backend/API behavior remains NBA-first.
- Non-NBA selection is allowed in UI context but marked as `Planned`.
- Dashboard builder displays a warning when non-NBA is selected, while current dataset remains NBA.

## Validation
- `cd frontend && npm run build` ✅

## Linear
- Issue: `SCR-184`
- Status: implementation batch completed for Phase 6A foundation scope
