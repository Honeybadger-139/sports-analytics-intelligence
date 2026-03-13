# Learning Notes Index

This directory is your study map for interview prep and quick re-onboarding after short breaks.

## Domains

- `data-layer/`
  - ingestion reliability, feature engineering, schema and query strategy
- `ml-engine/`
  - model training, rolling/H2H features, explainability and bet sizing
- `api-layer/`
  - FastAPI contract design, route families, reliability patterns
- `intelligence-layer/`
  - RAG retrieval, citation guardrails, chatbot orchestration
- `frontend/`
  - React architecture, routing, page modules, UX/interaction patterns
- `mlops/`
  - monitoring snapshots, escalation, retrain policy and worker lifecycle
- `infrastructure/`
  - Docker/runtime setup and operational runbooks

## Fast Revisions

- `interview-2-day-refresh.md` -> short memory refresh when returning after 1-3 days
- `future-learning-roadmap.md` -> next-step progression once baseline is stable

## Current Baseline Snapshot

1. End-to-end NBA ingestion + feature pipeline with idempotent reruns.
2. Prediction serving with SHAP explainability and persisted performance tracking.
3. Intelligence endpoints with citation-grounded summaries and deterministic risk overlays.
4. MLOps monitoring snapshots + retrain policy + queue/worker lifecycle endpoints.
5. Chatbot dual-engine support (`legacy` + `langgraph`) with stream-first SSE UX.
6. Scribble SQL workspace with read-only query controls, notebooks, and managed views.
7. React command center (Overview/Pulse/Arena/Lab/Dashboard/Scribble/Chatbot) with sport-context gating for staged multi-sport rollout.

## Suggested Study Order

1. Start with `api-layer/README.md` and `architecture/system-design.md`.
2. Move to `data-layer/` and `ml-engine/` for model/data depth.
3. Review `intelligence-layer/` and `mlops/` for advanced system design discussion.
4. Finish with `frontend/` for product delivery and UX architecture framing.
