# Frontend — Learning Notes

> Status: Current production frontend is React + Vite + TypeScript in `frontend/`.

## What This Frontend Solves

The UI is an operator workflow surface, not a generic dashboard.

It is organized by intent:
1. **Overview** -> system snapshot + navigation
2. **Pulse** -> intelligence briefs, stories, match previews
3. **Arena** -> predictions, deep dives, model performance
4. **Lab** -> data quality, pipeline runs, MLOps monitor
5. **Dashboard** -> created dashboards and Grafana launch path
6. **Scribble** -> raw table exploration + SQL + notebooks/views
7. **Chatbot** -> natural-language assistant over live data and context

## Runtime Architecture

### Router and gating
- `frontend/src/App.tsx` defines all page routes.
- Sport context comes from `SportContextProvider`.
- Live data routes are gated by `isLiveDataSelection(...)`.
- Current live gate: `sport=nba` and `league=nba`; other contexts render `ComingSoonHold`.

### Navigation system
- `frontend/src/components/Navbar.tsx`
- Nike-style center navigation + animated mega menu (Framer Motion)
- Right rail includes system-health pill and theme toggle
- Second row includes sport/league/season context selectors

### Data fetching model
- Shared hooks in `frontend/src/hooks/useApi.ts`, `useChatbot.ts`, `useScribble.ts`
- `API_BASE=/api/v1` keeps frontend decoupled from host/port changes
- Critical pages use explicit loading/empty/error states

## Page-Level Notes

### Overview
- Live metric cards from `/api/v1/system/status`
- Context card reflects live/coming-soon data availability
- Directory cards deep-link into each module

### Pulse
- `Daily Brief` -> `/api/v1/intelligence/brief`
- `Top Stories` and `Match Previews` connect intelligence + match endpoints
- Date and filter patterns prioritize analyst triage flow

### Arena
- `Today's Picks` -> `/api/v1/predictions/today`
- `Deep Dive` -> predictions + features + team/player stat views
- `Model Performance` -> `/api/v1/predictions/performance`

### Lab
- `Data Quality` -> `/api/v1/quality/overview`
- `Pipeline Runs` -> audit histories from status/quality payloads
- `MLOps Monitor` -> monitoring, trend, retrain policy, job queue

### Dashboard + Grafana
- Internal dashboard list/create flows exist in React routes.
- Grafana launch helpers centralize environment-aware create URL behavior.

### Scribble
- Explorer tab uses raw table catalog/rows APIs.
- SQL Lab uses read-only query execution endpoint.
- Notebooks and view management are first-class UX flows.

### Chatbot
- Stream-first client via `/api/v1/chat/stream`.
- Fallback to `/api/v1/chat` keeps backward compatibility.
- Session id persistence supports trace grouping for observability tools.

## Design Principles

1. **Intent-first IA**: each route maps to one analyst job.
2. **Operational resilience in UX**: failures are surfaced with actionable messaging.
3. **Type-safe contracts**: API payloads are centrally typed in `src/types.ts`.
4. **Incremental platform rollout**: multi-sport context can ship before live adapters.

## Interview Angles

1. "I organized the UI by operational workflow, not by component taxonomy."
2. "We use route-level gating so future sports are visible without pretending data is live."
3. "Chatbot is stream-first with fallback to preserve UX and contract compatibility."
4. "The frontend depends on API contracts, so backend evolution stays additive and testable."
