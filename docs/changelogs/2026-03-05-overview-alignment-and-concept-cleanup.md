# 2026-03-05 - Overview alignment + concept artifact cleanup

## Type
Implementation (frontend copy/state alignment + docs cleanup)

## Overview updates
- Updated `frontend/src/pages/Overview.tsx` to align with current support model:
  - Shows selected `sport · league · season` context in hero.
  - Shows support status (`LIVE` vs `COMING SOON`) in metric cards.
  - Displays rollout notice and `Switch To Basketball · NBA` action when selected context is not live.
  - Marks directory cards as `Coming Soon` and disables section subitem actions when context is unsupported.

## Cleanup performed
Deleted temporary visualization artifacts used for multi-sport concept preview:
- `docs/images/dashboard-concepts/concept-1-command-center.svg`
- `docs/images/dashboard-concepts/concept-2-sport-hub.svg`
- `docs/images/dashboard-concepts/concept-3-league-matrix.svg`
- `docs/images/dashboard-concepts/concept-4-broadcast-deck.svg`
- `docs/images/dashboard-concepts/index.html`
- `docs/changelogs/2026-03-05-multi-sport-dashboard-concepts.md`
- Removed now-empty directory: `docs/images/dashboard-concepts/`

## Validation
- `cd frontend && npm run build` ✅

## Linear
- Issue: `SCR-187`
