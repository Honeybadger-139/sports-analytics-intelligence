# 2026-03-07 - Route all Create Dashboard actions to Grafana

## Type
Feature behavior change (dashboard creation flow)

## Goal
Make Grafana the primary dashboard builder. Any `Create Dashboard` action now opens Grafana dashboard creation UI.

## What changed
- Added shared Grafana helper:
  - `frontend/src/utils/grafana.ts`
  - `getGrafanaCreateDashboardUrl()`
  - `openGrafanaCreateDashboard()`
- Rewired `Create Dashboard` actions in:
  - `frontend/src/components/Arena/TodaysPicks.tsx`
  - `frontend/src/components/Arena/ModelPerformance.tsx`
  - `frontend/src/components/Arena/MatchDeepDive.tsx`
  - `frontend/src/components/Arena/PlayerStatsView.tsx`
  - `frontend/src/components/Arena/TeamStatsView.tsx`
  - `frontend/src/pages/Dashboard.tsx`
- Repurposed `/dashboard/create` route page into a Grafana launcher/redirect fallback:
  - `frontend/src/pages/DashboardCreate.tsx`
- Added configurable frontend env keys:
  - `.env.example`
    - `VITE_GRAFANA_URL`
    - `VITE_GRAFANA_CREATE_PATH`

## Validation
- `cd frontend && npm run build` ✅

## Notes
- Existing saved/local dashboard cards remain viewable.
- Creation path now consistently targets Grafana.

## Linear
- Issue: `SCR-208`
