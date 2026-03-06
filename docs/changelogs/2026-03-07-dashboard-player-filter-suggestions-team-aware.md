# 2026-03-07 - Dashboard player filter suggestions made complete + team-aware

## Type
Bug fix (dashboard filter suggestions)

## Goal
Ensure `player_name` suggestions are complete and respond to selected `team_abbreviation`.

## Problem
- Player suggestions were derived from only currently loaded sample rows, so many players were missing.
- Player suggestions were not constrained by selected team filter.

## What changed
- Updated `DragDropChartBuilder` to load player directory from `raw/players` with pagination (`limit=300`, increasing `offset`) when table is `player_game_stats`.
- Built:
  - complete `allPlayers` suggestion list
  - `playersByTeam` lookup
  - `teamList` lookup
- Filter behavior now:
  - `player_name` suggestions are **team-aware** when `team_abbreviation = <TEAM>` is set.
  - if team is not selected, `player_name` suggestions show all players.
  - `team_abbreviation` filter options use complete team list from loaded player directory.
- Datalist suggestions are no longer hard-truncated to 120 options.

## File changed
- `frontend/src/components/Dashboard/DragDropChartBuilder.tsx`

## Validation
- `cd frontend && npm run build` ✅

## Linear
- Issue: `SCR-205`
