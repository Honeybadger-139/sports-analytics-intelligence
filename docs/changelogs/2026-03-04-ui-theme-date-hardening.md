# UI Theme + Date Picker Hardening

Date: 2026-03-04 (Asia/Kolkata)  
Scope: Fix calendar visibility, cross-theme contrast, and modernize section color language.

## Objective

1. Make native date picker/calendar controls clearly visible in both dark and light themes.
2. Fix dark/light font and UI contrast inconsistencies caused by missing theme tokens and low-contrast color usage.
3. Refresh section accent colors to a cleaner, modern palette.

## Frontend Changes

1. Theme token hardening in:
   - `frontend/src/index.css`
2. Navigation color modernization in:
   - `frontend/src/components/Navbar.tsx`
3. Section accent updates across page/component shells:
   - `frontend/src/pages/Pulse.tsx`
   - `frontend/src/pages/Arena.tsx`
   - `frontend/src/pages/Lab.tsx`
   - `frontend/src/pages/Dashboard.tsx`
   - `frontend/src/pages/DashboardCreate.tsx`
4. Pulse contrast and date-filter polish:
   - `frontend/src/components/Pulse/MatchPreviews.tsx`
   - `frontend/src/components/Pulse/DailyBrief.tsx`
   - `frontend/src/components/Pulse/TopStories.tsx`
5. Arena/Lab/Scribble accent consistency:
   - `frontend/src/components/Arena/*.tsx` (DeepDive, TodaysPicks, MatchDeepDive, ModelPerformance, PlayerStatsView, TeamStatsView)
   - `frontend/src/components/Lab/*.tsx` (DataQuality, PipelineRuns, MLOpsMonitor, LabRawExplorer)
   - `frontend/src/components/Scribble/*.tsx` (TableBrowser, SqlLab, NotebooksPanel)
   - `frontend/src/components/Dashboard/DragDropChartBuilder.tsx`

## What Was Fixed

1. Added missing theme tokens used by existing components:
   - `--bg-card`
   - `--accent-green`
   - `--accent-red`
2. Added global native date input rules:
   - explicit `color-scheme` per theme
   - visible `::-webkit-calendar-picker-indicator` styling
   - stronger date text visibility via `::-webkit-datetime-edit`
3. Updated base palettes for a more modern visual tone in both themes.
4. Improved warning/error/success badge tints with token-driven `color-mix(...)` where needed.

## Browser Verification

Opened and checked key routes:
1. `/pulse/previews`
2. `/pulse/brief`
3. `/arena/deep-dive`
4. `/lab/quality`
5. `/dashboard`
6. `/dashboard/create`

## Validation

1. Frontend build:
   - `cd frontend && npm run build`
   - Result: success (`tsc -b` + `vite build`)

## Linear Tracking

- Planned and executed under `SCR-179`.
