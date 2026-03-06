# 2026-03-07 - Dashboard starter trends + dynamic team/player filter UX

## Type
Feature enhancement (dashboard usability + trend presets)

## Goal
Create practical custom dashboards for team/player trend analysis with dynamic selection support.

## What changed
- Added **Starter Dashboards** on Dashboard home:
  - Team Trends Dashboard
  - Player Trends Dashboard
- Each starter opens `/dashboard/create` with useful defaults:
  - Team trends: line chart by `game_date` with `avg(points)`, `avg(rebounds)`, `avg(assists)`, filtered by `team_abbreviation`
  - Player trends: line chart by `game_date` with `avg(points)`, `avg(rebounds)`, `avg(assists)`, filtered by `team_abbreviation` + `player_name`
- Upgraded builder filter UX for dynamic selection:
  - Distinct value options are extracted per field from loaded table rows.
  - `eq/neq` filters auto-render as dropdowns for low-cardinality fields (for example, team selection).
  - Higher-cardinality fields use input + datalist suggestions (for example, player names).
- Added preset guidance copy in Dashboard Create page for team/player starter flows.

## Files changed
- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/components/Dashboard/DragDropChartBuilder.tsx`
- `frontend/src/pages/DashboardCreate.tsx`

## Validation
- `cd frontend && npm run build` ✅

## Linear
- Issue: `SCR-204`
