# Future Learning Roadmap

This roadmap captures learning priorities across all completed and upcoming phases of the Sports Analytics Intelligence Platform.

## Current Baseline (Completed — Phases 0 through 7C)

1. Structured ingestion resilience (rate limiting, retries, idempotent upserts).
2. Feature reliability hardening (H2H execution + non-leaky pregame streaks).
3. Advanced metric completeness with targeted backfill.
4. Self-healing observability bootstrap for legacy DB volumes.
5. Data quality contracts and API exposure design.
6. DB-backed integration testing patterns for ingestion pipelines.
7. FastAPI route contract testing (including failure-mode behavior).
8. Prediction persistence and outcome reconciliation (`was_correct` sync).
9. Model-performance API contracts (accuracy, Brier score, calibration).
10. Bankroll ledger design (`bets` lifecycle, PnL accounting, Kelly sizing).
11. Phase 3A frontend integration: operations console wired to live APIs.
12. Phase 4 RAG intelligence: ChromaDB, Gemini embeddings, citation enforcement.
13. Phase 5 MLOps: monitoring snapshots, escalation policy, retrain queue.
14. Phase 6 CI/CD: GitHub Actions regression gate + DB-backed integration tests.
15. Phase 7A UI redesign: React + Vite + TypeScript `frontend-v2` on `ui-redesign` branch.
16. Phase 7B Chatbot: hybrid RAG+DB engine, LLMClient Adapter, IntentRouter, off-topic gate.
17. Phase 7C Scribble: read-only SQL API, DataTable reuse, CustomEvent bus, localStorage notebooks.

---

## Level 1: Deepen Existing Implementations

These topics are partially implemented — deepen the interview narrative and edge-case handling.

1. **RAG evaluation**: How do you measure retrieval quality? Recall@K, MRR, citation accuracy. Add offline eval harness for the intelligence layer.
2. **LLM prompt engineering**: Structured prompts for NL→SQL (schema injection, few-shot examples, output format constraints). Study hallucination failure modes.
3. **React performance patterns**: `useMemo`, `useCallback`, `React.memo` — when do they help vs add noise? Apply to the metric cards polling loop.
4. **Custom hook testing**: How to test `useChatbot` and `useScribble` with React Testing Library + `msw` (Mock Service Worker) for API mocking.
5. **AbortController patterns**: Cancellation in fetch, streaming responses, timeout vs abort semantics.

## Level 2: Frontend Architecture Deepening

1. **React Router v6 patterns**: Nested routes, `Outlet`, lazy-loaded routes with `React.lazy` + `Suspense` — apply to Arena and Lab sub-routes.
2. **Framer Motion advanced**: `useMotionValue`, `useTransform`, scroll-linked animations, shared layout animations (`layoutId`) for smooth page transitions.
3. **Design system evolution**: Moving from a single `index.css` to CSS Modules or `styled-components` — trade-offs, scope isolation, dynamic theming.
4. **Accessibility (a11y)**: ARIA roles for the mega-menu flyout, keyboard navigation (Escape to close, Tab through sub-items), focus management.
5. **Storybook**: Isolate and document `SportsMark`, `DataTable`, `ChatMessage` components independently.

## Level 3: Full-Stack Feature Expansion

1. **Arena module**: Wire `Today's Predictions`, `Model Performance`, and `Bankroll Tracker` pages to live backend APIs — migrate from stub to live.
2. **Lab module**: Wire `Data Quality`, `Pipeline Runs`, and `MLOps Monitor` pages — the backend already has all required endpoints.
3. **Pulse module**: Implement `Top Stories` and `Daily Brief` using the intelligence brief API (`GET /api/v1/intelligence/brief`).
4. **Chatbot streaming**: Upgrade `POST /api/v1/chat` to use Server-Sent Events (SSE) for streaming tokens. Update `useChatbot` to read `ReadableStream`.
5. **Multi-sport extensibility**: Add `sport` selector to the chatbot UI; extend `IntentRouter` keyword sets for football/cricket.

## Level 4: Production & Platform Hardening

1. **Frontend build and deployment**: Vite `npm run build` output, static hosting (Netlify, Vercel, S3+CloudFront), environment variable injection at build time.
2. **Reverse proxy config**: Nginx or Caddy to serve `frontend-v2/dist/` and proxy `/api/v1/*` to FastAPI — eliminates the Vite dev proxy in production.
3. **LLM provider migration**: Swap Gemini for Minimax (or OpenAI) via `LLMClient` — document the one-class change process.
4. **Scribble hardening**: Add PostgreSQL RLS as a second security layer alongside application-layer validation.
5. **Notebook persistence**: Migrate `useNotebooks` from localStorage to `POST /api/v1/notebooks` for multi-user support.

## Level 5: Senior / Architect Interview Preparation

1. **Strangler fig migration pattern**: Articulate the `frontend` → `frontend-v2` promotion strategy at depth — parallel coexistence, feature flags, traffic splitting.
2. **Adapter design pattern in practice**: LLMClient as a case study — interface stability vs implementation flexibility, versioning, testing the adapter.
3. **Intent routing architecture**: Tradeoffs between keyword heuristics, embedding similarity, and LLM classification for intent detection. Cost/latency/accuracy triangle.
4. **Event-driven UI patterns**: CustomEvent bus vs Zustand vs React Context — when each is appropriate, scalability limits of each.
5. **API contract evolution**: Adding new fields to existing endpoints (additive change vs breaking change), versioning strategies, client compatibility.

## Recommended Study Flow

1. Deepen Level 1 topics while continuing Phase 7 development.
2. Tackle Level 2 when wiring Arena/Lab/Pulse stub pages to live data.
3. Execute Level 3 to complete the full `frontend-v2` feature set before merging to `main`.
4. Address Level 4 before the `ui-redesign → main` merge (deployment readiness).
5. Use Level 5 to prepare for senior/architect interview scenarios.
