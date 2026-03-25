# Agent Handoff — What To Do Next

> **Purpose**: This file tells any agent (Claude Code, Codex, or human) exactly what to implement next.
> Read this file FIRST before starting any Phase 6 work.
>
> **Last updated**: 2026-03-25

---

## Current State

The Sports Analytics Intelligence Platform has completed Phases 1-5:
- Data ingestion, feature engineering, prediction serving (Phase 1)
- GCP Cloud Run deployment, CI/CD, Pub/Sub (Phase 2-3)
- Vertex AI Experiments, Model Registry, Pipelines (Phase 4)
- Cloud Monitoring, drift detection, MLOps dashboards (Phase 5)
- React + TypeScript frontend with chatbot, Scribble SQL, dashboards
- LangGraph chatbot with SSE streaming and Langfuse observability

**Phase 6** adds 8 advanced skill modules. 6 are active, 2 are deferred.

---

## What To Build Next (In Order)

### Step 1: Check Linear for current status
```
Linear Master Issue: SCR-307
```
Check which sub-issues are already completed before starting.

### Step 2: Follow this build order

| Priority | Module | Linear | Status | What To Build |
|----------|--------|--------|--------|---------------|
| 1 | **LangChain/LangGraph** | SCR-313 | TODO | LangChain tools wrapping existing services, Pydantic structured output, PostgreSQL chat memory, refactored LangGraph workflow |
| 2 | **PyTorch** | SCR-308 | TODO | MLP model (24→64→32→16→1), entity embeddings for team_id, integrate into trainer.py model registry + ensemble |
| 3 | **Multi-Agent** | SCR-309 | TODO | Supervisor + 3 specialist agents (Stats, News, Prediction) via LangGraph. Depends on SCR-313 |
| 4 | **Statistics** | SCR-310 | TODO | A/B testing (SPRT), Bayesian team ratings (PyMC), causal inference (DiD using COVID empty arenas) |
| 5 | **Time-Series** | SCR-311 | TODO | Prophet + ARIMA + LSTM sequence model, momentum engine, changepoint detection. Depends on SCR-308 |
| 6 | **Fine-tuning** | SCR-312 | TODO | Generate 5K-10K Q&A pairs from platform, LoRA fine-tune Phi-3-mini, eval suite, LLM router. Depends on SCR-308 |
| DEFER | **NLP Engine** | SCR-314 | DEFERRED | Sentiment, NER, text classification. Do NOT start until active wave is done |
| DEFER | **Knowledge Graphs** | SCR-315 | DEFERRED | Neo4j graph. Do NOT start until active wave is done |

### Step 3: For each module, follow this pattern

1. **Read the full plan**: `docs/architecture/phase-6-advanced-skills-plan.md` — contains exact files to create/modify, dependencies, architecture, and interview angles
2. **Read the Linear issue** for that module — contains the same info in ticket form
3. **Update Linear status** to "In Progress" when you start
4. **Create files** listed in the plan
5. **Write tests** for the module
6. **Create learning notes** at `docs/learning-notes/{module}-deep-dive.md`
7. **Update decision log** at `docs/decisions/decision-log.md`
8. **Update Linear status** to "Done" and add a completion comment

---

## Key Files To Read Before Starting

| File | Why |
|------|-----|
| `docs/architecture/phase-6-advanced-skills-plan.md` | The full implementation plan with all 8 modules |
| `docs/decisions/decision-log.md` | All prior architectural decisions (entries 98-103 cover Phase 6 rationale) |
| `docs/decisions/claude-agent-rules.md` | Operating rules for this project |
| `CLAUDE.md` | Session start instructions |
| `docs/learning-notes/future-learning-roadmap.md` | Roadmap with Phase 6 as Level 4 |

---

## Key Integration Points

When building any module, these are the files you'll most commonly need to read/modify:

| Existing File | Purpose | Modules That Touch It |
|---------------|---------|----------------------|
| `backend/src/models/trainer.py` | Model training orchestration | PyTorch, Time-Series |
| `backend/src/models/predictor.py` | Inference engine | PyTorch, Time-Series |
| `backend/src/intelligence/langgraph_chat_service.py` | Chatbot graph | LangChain, Multi-Agent |
| `backend/src/api/chat_routes.py` | Chat endpoints | LangChain, Multi-Agent |
| `backend/src/data/feature_store.py` | Feature engineering SQL | Statistics, Time-Series |
| `backend/src/intelligence/vector_store.py` | pgvector RAG | LangChain |
| `backend/src/intelligence/chat_service.py` | Legacy chatbot engine | LangChain (wraps as tools) |
| `backend/requirements.txt` | Dependencies | ALL modules |
| `frontend/src/App.tsx` | Frontend router | Stats page, Forecast page |

---

## Dependencies To Add (Per Module)

```
# 6.1 LangChain
langchain-google-genai>=2.0.0
langchain-community>=0.2.0

# 6.2 PyTorch
torch>=2.2.0
tensorboard>=2.16.0

# 6.4 Statistics
statsmodels>=0.14.0
pymc>=5.10.0
arviz>=0.17.0

# 6.5 Time-Series
prophet>=1.1.5
ruptures>=1.1.0

# 6.6 Fine-tuning
peft>=0.9.0
trl>=0.7.0
bitsandbytes>=0.42.0
accelerate>=0.27.0
evaluate>=0.4.0
transformers>=4.38.0
```

---

## Database Migrations Needed

| Migration | Module | What |
|-----------|--------|------|
| `0003_add_chat_memory_table.py` | 6.1 LangChain | `chat_sessions`, `chat_messages` tables |
| `0004_add_experiments_table.py` | 6.4 Statistics | `ab_experiments`, `experiment_assignments` tables |
| `0005_add_forecasts_table.py` | 6.5 Time-Series | `team_forecasts` table |

---

## Rules For This Project

- **Teach before code**: Explain WHAT and WHY before writing code
- **Decision log**: Update `docs/decisions/decision-log.md` for every architectural decision
- **Learning notes**: Create `docs/learning-notes/{module}-deep-dive.md` after each module
- **Linear sync**: Update ticket status and add completion comments
- **Tests required**: Every module needs unit + integration tests
- **No standalone scripts**: Everything integrates into the existing platform

---

## Success Criteria

| Module | Metric | Target |
|--------|--------|--------|
| LangChain | Tool execution success rate | >95% |
| PyTorch | MLP vs XGBoost AUC comparison documented | Any result valid |
| Multi-Agent | Complex query decomposition accuracy | >80% |
| Statistics | A/B test detects 2% accuracy diff at p<0.05 | Demonstrated |
| Time-Series | 14-day forecast MAPE | <15% |
| Fine-tuning | Sports-fact accuracy improvement over base | >15% |
