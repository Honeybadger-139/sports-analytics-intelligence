# Future Learning Roadmap

This roadmap prioritizes what to study next after the current GameThread baseline.

## Current Baseline (Already Implemented)

1. Reliable ingestion and feature pipeline with idempotent reruns.
2. Prediction serving with SHAP explainability and persisted outcomes.
3. RAG intelligence services with citations and deterministic risk overlays.
4. Chatbot with dual-engine orchestration (`legacy` + `langgraph`) and SSE streaming.
5. MLOps monitoring snapshots + retrain policy + retrain worker lifecycle.
6. React operations console with route-level modules and sport-context gating.
7. Scribble SQL workspace (safe query execution, notebooks, and managed views).

## Level 1 — Strengthen What Exists

1. Add structured offline evals for intelligence retrieval quality (Recall@K, citation precision).
2. Add richer chatbot eval metrics (groundedness, SQL correctness, latency percentiles).
3. Add frontend test coverage for critical hooks (`useChatbot`, `useApi`, `useScribble`).
4. Add route contract tests for advanced query params and edge-case filters.
5. Add data-drift feature diagnostics beyond aggregate accuracy/Brier thresholds.

## Level 2 — Product/Platform Hardening

1. Introduce auth/role controls for Scribble and retrain execution endpoints.
2. Add pagination + cursor strategy for heavy data endpoints.
3. Add dashboard export/share workflow with versioned snapshots.
4. Add environment-specific config safety checks at startup.
5. Add SLO dashboards (p50/p95 latency, error-rate by route family).

## Level 3 — Multi-Sport Expansion (Staged)

1. Define adapter contract per sport (ingest -> feature -> prediction -> intelligence).
2. Implement first non-NBA adapter end-to-end with minimal UI changes.
3. Replace hard-coded NBA assumptions in route defaults where needed.
4. Add sport-aware intent routing and schema selection in chatbot paths.
5. Add cross-sport benchmark dashboard for quality/freshness comparison.

## Level 4 — Senior/Architect Interview Prep

1. Prepare a "trade-off ledger": where you chose speed vs rigor and why.
2. Prepare one resilience incident story (failure, diagnosis, prevention).
3. Prepare one scaling story (where bottlenecks will appear and mitigation plan).
4. Prepare one AI-governance story (how guardrails prevent bad outputs).
5. Prepare one migration story (how to roll out big changes safely with feature flags).

## Suggested Study Flow

1. Start with Level 1 to deepen confidence in current architecture.
2. Move to Level 2 to demonstrate production thinking.
3. Use Level 3 for future roadmap discussions in interviews.
4. Finish with Level 4 narrative drills so your answers sound senior and specific.
