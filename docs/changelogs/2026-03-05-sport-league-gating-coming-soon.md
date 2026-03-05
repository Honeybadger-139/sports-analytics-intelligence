# 2026-03-05 - Sport/League consistency fix and Coming Soon gating

## Type
Implementation (frontend behavior correction)

## Why
After introducing global sport/league selectors, non-supported selections could still navigate into NBA-only pages, which created mismatched expectations.

## What changed
- Updated sport naming:
  - Sport selector now shows `Basketball` as sport label.
  - `NBA` remains a league under Basketball.
- Added support gate utility:
  - `isLiveDataSelection(selection)` returns `true` only for `Basketball + NBA`.
- Added route-level hold state:
  - For unsupported selections (all non-NBA leagues and non-Basketball sports), app pages render a uniform `Coming Soon` hold screen.
  - Applied across `Pulse`, `Arena`, `Lab`, `Dashboard`, `Dashboard Builder`, `Scribble`, and `Chatbot` routes.
- Updated navbar support badge:
  - Uses sport+league gate (not sport-only).
  - Shows `Live Data` for Basketball+NBA, otherwise `Coming Soon`.
- Updated dashboard metadata display to show proper sport and league labels.

## Files
- `frontend/src/config/sports.ts`
- `frontend/src/components/ComingSoonHold.tsx`
- `frontend/src/App.tsx`
- `frontend/src/components/Navbar.tsx`
- `frontend/src/index.css`
- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/pages/DashboardCreate.tsx`

## Validation
- `cd frontend && npm run build` ✅

## Linear
- Issue: `SCR-185`
