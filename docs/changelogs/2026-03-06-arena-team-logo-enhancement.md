# 2026-03-06 - Arena team-logo enhancement (NBA)

## Type
Implementation (frontend UX enhancement)

## Goal
Improve team recognizability in Arena matchup/stat views by rendering NBA team logos next to team names.

## What changed
- Added reusable NBA logo mapping + resolver:
  - `frontend/src/utils/nbaTeams.ts`
- Added reusable logo component with graceful fallback:
  - `frontend/src/components/NbaTeamLogo.tsx`
- Integrated team logos into Arena surfaces:
  - `frontend/src/components/Arena/TodaysPicks.tsx`
    - Home/away logos in matchup card headers
  - `frontend/src/components/Arena/MatchDeepDive.tsx`
    - Logos in sidebar game list rows
    - Logos in main matchup header
    - Logo beside predicted winner in model cards
  - `frontend/src/components/Arena/TeamStatsView.tsx`
    - Logos in team sidebar rows
    - Logo in selected team header
    - Opponent logos in game-log table

## Validation
- `cd frontend && npm run build` ✅

## Linear
- Issue: `SCR-195`
