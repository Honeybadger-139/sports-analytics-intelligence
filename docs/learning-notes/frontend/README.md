# Frontend — Learning Notes

> 📌 **Status**: Implemented through **Phase 5 foundation** — Home, Raw Data Explorer, Data Quality, Intelligence, and Analysis workspaces.

## What Is the Frontend?

The frontend is the product surface for this ML system. It turns backend APIs into an operator workflow:

1. Read scope and intent (NBA-only) on Home.
2. Inspect raw Postgres records without mixing feature-engineering tables.
3. Monitor pipeline quality and load-time metrics.
4. Run model + bankroll analysis.
5. Consume citation-grounded intelligence and MLOps signals in dedicated UX surfaces.

## Current Implementation (`frontend/index.html`)

### 1) Home Tab
- Clear intro describing dashboard purpose and **NBA-only** scope.
- Explains each tab’s responsibility to keep usage simple.

### 2) Raw Data Explorer Tab
- APIs:
  - `GET /api/v1/raw/tables`
  - `GET /api/v1/raw/{table_name}`
- Shows only raw tables:
  - `matches`
  - `teams`
  - `players`
  - `team_game_stats`
  - `player_game_stats`
  - `player_season_stats`
- Explicitly excludes `match_features` from explorer.
- Includes pagination controls and season filtering.

### 3) Data Quality Tab
- API: `GET /api/v1/quality/overview`
- Tracks:
  - row counts
  - ingestion/feature load times
  - quality check payload
  - top-team performance snapshot
  - recent run history

### 4) Analysis Tab: System Health + Audit
- KPI cards for DB, pipeline, matches, features, players
- Audit table from `/api/v1/system/status`

### 5) Analysis Tab: Today's Predictions
- API: `GET /api/v1/predictions/today?persist=false`
- Shows matchup, consensus model/side, home win probability, confidence

### 6) Analysis Tab: Match Deep Dive
- APIs:
  - `GET /api/v1/matches`
  - `GET /api/v1/predictions/game/{game_id}`
  - `GET /api/v1/features/{game_id}`
- Shows per-game prediction context + top SHAP factors + compact feature snapshot
- Adds `Context Brief (RAG)` block:
  - summary from `/api/v1/intelligence/game/{game_id}`
  - deterministic risk signals
  - citation table

### 7) Intelligence Tab
- APIs:
  - `GET /api/v1/intelligence/brief`
  - `GET /api/v1/intelligence/game/{game_id}`
  - `GET /api/v1/mlops/monitoring`
  - `GET /api/v1/mlops/retrain/policy?dry_run=true`
- Shows:
  - daily intelligence brief
  - selected game citation inspector
  - MLOps alert summary
  - retrain policy dry-run outcome

### 8) Analysis Tab: Model Performance
- API: `GET /api/v1/predictions/performance`
- Displays evaluated games, accuracy, Brier score, and confidence by model

### 9) Analysis Tab: Bankroll Tracker
- APIs:
  - `GET /api/v1/bets/summary`
  - `GET /api/v1/bets`
- Shows bankroll KPIs and recent settled/pending bets

### 10) Theme Toggle (Light/Dark)
- Header button toggles between light and dark UI modes.
- Theme preference is persisted in browser `localStorage` using key `sai_theme`.
- CSS token overrides (`body.theme-dark`) update font and surface colors consistently across modules.

## Design Decisions

1. **No frontend framework (yet)**: Vanilla HTML/CSS/JS keeps deployment simple and demonstrates API-first architecture.
2. **Tab-first information architecture**: separated raw data, quality monitoring, intelligence operations, and analysis tasks into dedicated tabs.
3. **Resilient states**: Every module handles loading, empty, and error states explicitly.
4. **Responsive by default**: The same page works across desktop/mobile breakpoints with no separate build.
5. **Theme via design tokens**: Light/dark switch is implemented with CSS variables rather than duplicated styles.

## Senior Manager Perspective

This frontend is not a cosmetic layer; it is an operational dashboard. The value is in making model behavior and financial impact observable in one place, which accelerates decisions and reduces blind spots.

## Interview Angle

> "I designed the UI around operator intent: raw data inspection, quality monitoring, intelligence retrieval, and model analysis are split into focused tabs with explicit API contracts."

## Common Interview Questions

1. Why keep the frontend framework-free at this stage?
2. How did you prevent a single API failure from breaking the whole page?
3. Why keep `match_features` out of raw data explorer?
4. Why include both SHAP factors and aggregate performance metrics?
5. What would trigger a migration from vanilla JS to React/Next?
