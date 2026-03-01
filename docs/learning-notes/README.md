# Learning Notes Index

This directory is your study map for interview prep and future system upgrades.

## Domains

- `data-layer/`:
  - ingestion, schema design, feature engineering, sync precision, query workflows
- `ml-engine/`:
  - rolling features, H2H metrics, resilient ETL, model selection
- `api-layer/`:
  - endpoint design and contract thinking
- `infrastructure/`:
  - docker and environment reliability
- `frontend/`:
  - dashboard implementation notes (vanilla `frontend/`) and `frontend-v2` React redesign
  - sub-notes: `ui-redesign.md`, `chatbot-ui.md`, `scribble-playground.md`
- `mlops/`:
  - deployment and lifecycle fundamentals
- `intelligence-layer/`:
  - RAG, reasoning-layer direction, and chatbot backend (hybrid RAG+DB engine)

## What To Study Next

Use this roadmap for future preparation:

- [Future Learning Roadmap](future-learning-roadmap.md)
- [Phase Execution Runbook](../architecture/phase-execution-runbook.md)

## Latest Learning Context

Recently completed and documented:

1. Phase 1A: H2H + non-leaky pregame streak reliability.
2. Phase 1B: Advanced metric completeness and targeted backfill strategy.
3. Observability hardening: self-healing `pipeline_audit` bootstrap.
4. Phase 2 backend operations: prediction persistence/performance APIs + bankroll ledger endpoints.
5. Phase 3A frontend integration: operations console modules wired to live APIs.
6. Phase 3C redesign: tab-based UX for home, raw data, quality monitoring, and analysis.
7. Phase 4 foundation: RAG intelligence endpoints + context brief integration.
8. Phase 5 foundation: MLOps monitoring + retrain policy API surfaces.
9. Phase 4B hardening batch: source-quality scoring, feed-health telemetry, and Intelligence tab filters.
10. Phase 5A hardening batch: monitoring snapshot persistence + trend API contract.
11. Phase 5A hardening batch 2: escalation policy + incident workflow mapping.
12. Phase 5B batch 1: retrain queue automation with duplicate guard + audit endpoint.
13. Phase 5B batch 2: retrain worker lifecycle integration (`run-next` endpoint + status transitions).
14. Phase 6A batch 1: GitHub Actions regression gate for ingestion/routes/config contracts.
15. Phase 6B batch 2: DB-backed integration tests for ingestion integrity invariants.
16. Phase 6C batch 3: runtime parity hardening (SSL warning removal + Python 3.11 baseline guidance).
17. Phase 7A UI redesign: React + Vite + TypeScript `frontend-v2` scaffold on `ui-redesign` branch — Nike-style navbar, animated SportsMark SVG logo, Overview home with live metric cards + navigation directory, stub pages for all sections. See `frontend/README.md` and `frontend/ui-redesign.md`.
18. Phase 7B Chatbot: AI chatbot full-stack implementation — `useChatbot` hook + `ChatbotPanel` + `ChatMessage` components (UI), `chat_service.py` hybrid RAG+DB engine + `chat_routes.py` backend (API). See `frontend/chatbot-ui.md` and `intelligence-layer/README.md`.
19. Phase 7C Scribble: Raw data playground — `scribble_routes.py` read-only SQL API (backend), `TableBrowser` + `SqlLab` + `NotebooksPanel` + `DataTable` components, `useScribble` hooks, localStorage notebooks (frontend). See `frontend/scribble-playground.md`.

## Suggested Progression

1. Master Data Layer and API Layer first.
2. Deepen ML Engine with experiment discipline.
3. Execute Intelligence Layer topics in Phase 4, then MLOps in Phase 5.
