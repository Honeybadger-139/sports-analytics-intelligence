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

## Level 4 — Phase 6: Advanced Skill Modules (DS Interview Readiness 2026)

> Full plan: `docs/architecture/phase-6-advanced-skills-plan.md`
> Driven by gap analysis of 99 LinkedIn DS job postings (2026-02-25 snapshot)

### Module 1: LangChain / LangGraph Enhancement
- Refactor chatbot to use proper LangChain tools, structured output, PostgreSQL-backed memory
- Wraps existing services (SQL, prediction, RAG) as LangChain tools
- **Covers**: 50% of job postings requiring LangChain

### Module 2: PyTorch Neural Network Baseline
- MLP for game prediction alongside XGBoost/LightGBM
- Entity embeddings for team_id (reusable in LSTM later)
- Deliberately shows trees-vs-NNs trade-off on tabular data
- **Covers**: 65% of job postings requiring PyTorch/TensorFlow

### Module 3: Agentic AI — Multi-Agent System
- Supervisor + 3 specialist agents (Stats, News, Prediction)
- LangGraph state machine orchestration
- Parallel agent execution, conflict resolution
- **Covers**: 35% of job postings requiring Agentic AI
- **Depends on**: Modules 1, 5

### Module 4: Statistics (A/B Testing, Bayesian, Causal)
- Champion/challenger A/B testing with sequential testing (SPRT)
- Bayesian team strength ratings with credible intervals
- Causal inference: home court advantage via DiD (COVID natural experiment)
- **Covers**: 30% of job postings requiring statistical rigor

### Module 5: NLP Engine (Classification, Embeddings, Sentiment)
- Team-level sentiment from sports news (HuggingFace transformers)
- Named entity recognition for players/teams (spaCy)
- News text classification to filter RAG noise
- Embedding model comparison benchmark
- **Covers**: 35% of job postings requiring NLP

### Module 6: LLM Fine-tuning (LoRA/PEFT)
- Generate 5K-10K Q&A pairs from platform API responses
- LoRA fine-tune Phi-3-mini on sports analytics domain
- Evaluation: fact accuracy, hallucination rate, latency
- LLM router: simple queries → local fine-tuned, complex → Gemini
- **Covers**: 25% of job postings requiring fine-tuning
- **Depends on**: Modules 2, 5

### Module 7: Knowledge Graphs (Neo4j)
- Team-player-game graph with Neo4j
- Graph analytics: PageRank chemistry, trade impact, community detection
- Graph-derived features for prediction model
- **Covers**: 10% of job postings (senior-level roles at JPMorgan, Deloitte)

### Module 8: Time-Series Forecasting
- Prophet + ARIMA for team trajectory forecasting
- LSTM sequence model (genuine NN advantage over trees)
- Changepoint detection for form shifts
- 14-day win probability forecast with confidence bands
- **Covers**: 20% of job postings requiring time-series

### Build Order
```
Module 1 (LangChain) → Module 5 (NLP) → Module 2 (PyTorch) →
Module 3 (Multi-Agent) → Module 4 (Stats) → Module 8 (Time-Series) →
Module 7 (Knowledge Graphs) → Module 6 (Fine-tuning)
```

---

## Level 5 — Senior/Architect Interview Prep

1. Prepare a "trade-off ledger": where you chose speed vs rigor and why.
2. Prepare one resilience incident story (failure, diagnosis, prevention).
3. Prepare one scaling story (where bottlenecks will appear and mitigation plan).
4. Prepare one AI-governance story (how guardrails prevent bad outputs).
5. Prepare one migration story (how to roll out big changes safely with feature flags).

## Suggested Study Flow

1. Start with Level 1 to deepen confidence in current architecture.
2. Move to Level 2 to demonstrate production thinking.
3. Use Level 3 for future roadmap discussions in interviews.
4. **Level 4 (Phase 6) is the priority for 2026 DS interview readiness.**
5. Finish with Level 5 narrative drills so your answers sound senior and specific.
