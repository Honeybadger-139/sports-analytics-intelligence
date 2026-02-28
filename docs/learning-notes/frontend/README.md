# Frontend — Learning Notes

> 📌 **Status**: Implemented (Phase 3A) — operations console integrating prediction, explainability, performance, bankroll, and system-health modules.

## What Is the Frontend?

The frontend is the product surface for this ML system. It turns backend APIs into an operator workflow:

1. Check system health and data freshness.
2. Review today's predictions.
3. Deep-dive into one game's factors.
4. Track model quality and bankroll outcomes.

## Current Implementation (`frontend/index.html`)

### 1) System Health + Audit
- KPI cards for DB, pipeline, matches, features, players
- Audit table from `/api/v1/system/status`

### 2) Today's Predictions
- API: `GET /api/v1/predictions/today?persist=false`
- Shows matchup, consensus model/side, home win probability, confidence

### 3) Match Deep Dive
- APIs:
  - `GET /api/v1/matches`
  - `GET /api/v1/predictions/game/{game_id}`
  - `GET /api/v1/features/{game_id}`
- Shows per-game prediction context + top SHAP factors + compact feature snapshot

### 4) Model Performance
- API: `GET /api/v1/predictions/performance`
- Displays evaluated games, accuracy, Brier score, and confidence by model

### 5) Bankroll Tracker
- APIs:
  - `GET /api/v1/bets/summary`
  - `GET /api/v1/bets`
- Shows bankroll KPIs and recent settled/pending bets

## Design Decisions

1. **No frontend framework (yet)**: Vanilla HTML/CSS/JS keeps deployment simple and demonstrates API-first architecture.
2. **Module-first page structure**: Every dashboard section maps to one backend capability for easier debugging and interview storytelling.
3. **Resilient states**: Every module handles loading, empty, and error states explicitly.
4. **Responsive by default**: The same page works across desktop/mobile breakpoints with no separate build.

## Senior Manager Perspective

This frontend is not a cosmetic layer; it is an operational dashboard. The value is in making model behavior and financial impact observable in one place, which accelerates decisions and reduces blind spots.

## Interview Angle

> "I built a thin, API-driven operations console that visualizes the full ML loop: data health, prediction output, explainability, model quality, and bankroll outcomes. Each module is independently resilient, so one failed endpoint does not collapse the whole dashboard."

## Common Interview Questions

1. Why keep the frontend framework-free at this stage?
2. How did you prevent a single API failure from breaking the whole page?
3. Why include both SHAP factors and aggregate performance metrics?
4. What would trigger a migration from vanilla JS to React/Next?
5. How would you enforce role-based access for bankroll actions?
