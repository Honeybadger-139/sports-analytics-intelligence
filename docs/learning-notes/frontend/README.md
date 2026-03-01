# Frontend — Learning Notes

> 📌 **Status**: Two parallel implementations:
> - `frontend/` (vanilla HTML/CSS/JS) — production on `main`, Phase 5 complete
> - `frontend-v2/` (React + Vite + TypeScript) — staging on `ui-redesign`, Phase 7 active
>
> See sub-notes: [`ui-redesign.md`](ui-redesign.md) · [`chatbot-ui.md`](chatbot-ui.md) · [`scribble-playground.md`](scribble-playground.md)

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
  - brief sort/filter controls (risk level, citation minimum, sort mode)
  - selected game citation inspector
  - citation quality signals (stale/noisy flags + quality score)
  - source quality summary table
  - MLOps alert summary
  - trend summary from monitoring snapshots (`/mlops/monitoring/trend`)
  - action-ready alert table (`recommended_action` from escalation policy)
  - latest retrain queue status (`/mlops/retrain/jobs`)
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

## Design Decisions (vanilla `frontend/`)

1. **No frontend framework (yet)**: Vanilla HTML/CSS/JS keeps deployment simple and demonstrates API-first architecture.
2. **Tab-first information architecture**: separated raw data, quality monitoring, intelligence operations, and analysis tasks into dedicated tabs.
3. **Resilient states**: Every module handles loading, empty, and error states explicitly.
4. **Responsive by default**: The same page works across desktop/mobile breakpoints with no separate build.
5. **Theme via design tokens**: Light/dark switch is implemented with CSS variables rather than duplicated styles.

---

## `frontend-v2/` — React + Vite + TypeScript Redesign (Phase 7, `ui-redesign` branch)

> Full deep-dive in [`ui-redesign.md`](ui-redesign.md).

### Why the migration

The chatbot, Scribble playground, and future Lab/Arena modules require complex interactive state that is painful to manage in vanilla JS. React components, custom hooks, and Framer Motion animations reduce complexity and allow isolated development and testing per module.

### Tech stack

| Layer | Tool | Reason |
|---|---|---|
| Build / dev server | Vite (port 5174) | Sub-second HMR, production bundler, proxy to backend on 8000 |
| UI framework | React 18 | Component model, hooks, ecosystem (Framer Motion, Recharts) |
| Language | TypeScript | Compile-time safety across 10+ API shapes and 30+ components |
| Animations | Framer Motion | Mega-menu flyouts, page transitions |

### Navigation structure (Nike-style)

```
[SportsMark logo] ← always navigates to Overview
       ↓
[Pulse · Arena · Lab · Scribble · Chatbot]   ← centered nav
       ↓ (hover/click any item)
[Framer Motion mega-menu flyout with sub-item cards]
       ↓
[System status pill · Theme toggle]  ← right side
```

### Section map

| Section | Status | Sub-items |
|---|---|---|
| **Overview** | Live | Metric cards, navigation directory |
| **Pulse** | Stub | Top Stories, Daily Brief, Match Previews |
| **Arena** | Stub | Today's Predictions, Deep Dive, Model Performance, Bankroll |
| **Lab** | Stub | Raw Tables, Data Quality, Pipeline Runs, MLOps |
| **Scribble** | Live | Explorer, SQL Lab, Notebooks |
| **Chatbot** | Live | Full-page AI assistant wired to `/api/v1/chat` |

### Overview home page (two zones)

- **Zone 1 — Live Metric Cards**: DB, Pipeline, Matches, Features, Players, Bankroll, ROI, Open Bets — polled from real backend APIs
- **Zone 2 — Navigation Directory**: One card per section with description, sub-items, and direct deep-link — serves as onboarding/instructions page

### Design system

- Dark-first base (`#05090F`)
- Per-section accent colours: orange (Pulse), cyan (Arena), emerald (Lab/Scribble), amber (Chatbot)
- Fonts: Bebas Neue (display), Syne (UI), Fira Code (data/mono)
- Full light-mode toggle via CSS custom property overrides

### Branch strategy

```
main  (production — frontend/ never touched)
  └── ui-redesign  (staging — frontend-v2/ actively developed)
        ├── chatbot   (feature sub-branch — merged ✓)
        └── scribble  (feature sub-branch — merged ✓)
```
Merge trigger: UI approved and tested → rename `frontend-v2/` → `frontend/`, merge to `main`.

---

## Senior Manager Perspective

The vanilla dashboard demonstrates API-first, operator-intent UI design. The React redesign raises the bar: stateful components, animated navigation, and modular page structure allow each analyst workflow (predictions, data exploration, AI chat) to evolve independently without breaking others.

## Interview Angles

> **On the vanilla frontend**: "I designed the UI around operator intent: raw data inspection, quality monitoring, intelligence retrieval, and model analysis are split into focused tabs with explicit API contracts."

> **On the React migration**: "I used a parallel branch strategy — the strangler fig pattern — to build the new React UI without touching production. Once tested and approved, a single rename + merge promotes it."

> **On the tech stack choice**: "React gives us isolated, testable components for the chatbot state machine and the Scribble SQL editor. Vite's HMR and proxy make development fast. TypeScript prevents runtime bugs across 10+ API contracts."

## Common Interview Questions

1. Why keep the frontend framework-free initially?
2. What triggered the migration to React?
3. How do you run both frontends in parallel during development?
4. How did you prevent Chatbot state from leaking into other routes?
5. Why use Framer Motion instead of CSS transitions for the mega-menu?
6. How does the branch strategy prevent production regressions during UI work?
