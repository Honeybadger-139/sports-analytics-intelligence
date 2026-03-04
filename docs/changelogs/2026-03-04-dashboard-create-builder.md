# Dashboard Create Flow + Dedicated Builder Route

Date: 2026-03-04 (Asia/Kolkata)  
Scope: Create-flow UX hardening for dashboard creation and routing

## Objective

1. Keep `/dashboard` as the default saved dashboards listing page.
2. Introduce a dedicated `/dashboard/create` page for dashboard creation.
3. Ensure every Arena `Create Dashboard` click opens the create page with source-specific context.
4. Preserve chart-builder capabilities: drag/drop fields, multiple chart types, multiple aggregates, multiple filters.

## Implemented Changes

1. Added route-level create page:
   - `frontend/src/pages/DashboardCreate.tsx`
   - `frontend/src/App.tsx` (`/dashboard/create`)
2. Refactored dashboard list page to default listing behavior:
   - Removed inline builder from `frontend/src/pages/Dashboard.tsx`
   - Added top-level `Create Dashboard` button that navigates to `/dashboard/create`
3. Added source-context handoff from Arena views into create page:
   - `frontend/src/components/Arena/TodaysPicks.tsx`
   - `frontend/src/components/Arena/MatchDeepDive.tsx`
   - `frontend/src/components/Arena/ModelPerformance.tsx`
   - `frontend/src/components/Arena/PlayerStatsView.tsx`
   - `frontend/src/components/Arena/TeamStatsView.tsx`
4. Enhanced builder component for page-level integration:
   - `frontend/src/components/Dashboard/DragDropChartBuilder.tsx`
   - Added `initialConfig` + `onConfigChange` support
   - Added table fallback handling when preferred table is unavailable
5. Extended dashboard types/storage for custom builder flow:
   - `frontend/src/types.ts`
   - `frontend/src/hooks/useDashboard.ts` (`dashboard/custom` source allowed)

## Behavior After Change

1. Dashboard tab opens as a saved-dashboards list by default.
2. User can click `Create Dashboard` in dashboard list or any Arena view.
3. Arena-origin create flow carries context (title, notes, stats, source, defaults) into `/dashboard/create`.
4. User configures chart and saves; created card appears in dashboard list.

## Validation

1. Frontend build:
   - `cd frontend && npm run build`
   - Result: success (`tsc -b` + `vite build`)

## Linear Tracking

- Planned + implemented under `SCR-178`.
