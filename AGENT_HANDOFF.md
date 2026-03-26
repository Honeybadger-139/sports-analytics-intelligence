# Agent Handoff — What To Do Next

> **Purpose**: This file tells any agent (Claude Code, Codex, or human) exactly what to implement next.
> Read this file FIRST before starting any Phase 6 work.
>
> **Last updated**: 2026-03-26

---

## Current State

The Sports Analytics Intelligence Platform has completed Phases 1-5 and all 6 active Phase 6 modules:
- Data ingestion, feature engineering, prediction serving (Phase 1)
- GCP Cloud Run deployment, CI/CD, Pub/Sub (Phase 2-3)
- Vertex AI Experiments, Model Registry, Pipelines (Phase 4)
- Cloud Monitoring, drift detection, MLOps dashboards (Phase 5)
- React + TypeScript frontend with chatbot, Scribble SQL, dashboards
- LangGraph chatbot with SSE streaming and Langfuse observability
- **Phase 6**: All 6 advanced skill modules implemented (see below)

---

## Phase 6 Status — All Active Modules DONE

| Priority | Module | Linear | Status | Files |
|----------|--------|--------|--------|-------|
| 1 | **LangChain/LangGraph Enhancement** | SCR-317 | ✅ DONE + API | `output_schemas.py`, `memory.py`, `langchain_tools.py`, alembic `0003_add_chat_memory_table.py` |
| 2 | **PyTorch Neural Network** | SCR-318 | ✅ DONE (training pipeline) | `pytorch_model.py`, `pytorch_trainer.py`, `trainer.py` (modified) |
| 3 | **Multi-Agent System** | SCR-319 | ✅ DONE + API | `multi_agent_system.py`, `chat_routes.py` → `POST /api/v1/chat/agents` |
| 4 | **Statistics Module** | SCR-320 + SCR-326 | ✅ DONE + **API + FRONTEND** | `ab_testing.py`, `bayesian_ratings.py`, `causal_inference.py` → `stats_routes.py` → `/ratings` UI |
| 5 | **Time-Series Forecasting** | SCR-324 + SCR-327 | ✅ DONE + **API + FRONTEND** | `timeseries_forecaster.py` → `forecast_routes.py` → `/forecast` UI |
| 6 | **LLM Fine-tuning** | SCR-325 | ✅ DONE (offline tool) | `dataset_generator.py`, `lora_trainer.py` |
| DEFER | **NLP Engine** | SCR-322 | DEFERRED | Sentiment, NER, text classification. Start this next wave |
| DEFER | **Knowledge Graphs** | SCR-323 | DEFERRED | Neo4j graph. Start after NLP Engine |

**Master Linear issue**: SCR-316

### New API Endpoints Added (SCR-326 + SCR-327)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/stats/team-ratings` | GET | Bradley-Terry strength rankings, tier labels |
| `/api/v1/stats/home-court-effect` | GET | DiD causal estimate (COVID natural experiment) |
| `/api/v1/stats/ab-test` | POST | SPRT sequential A/B model comparison |
| `/api/v1/forecast/{team_name}` | GET | 14-day Prophet+ARIMA win-rate forecast |
| `/api/v1/forecast/{team_name}/momentum` | GET | Momentum score, trend, current streak |
| `/api/v1/forecast/league/momentum` | GET | All 30 teams ranked by momentum |

### New Frontend Pages Added

| Page | Route | Hooks Used |
|------|-------|------------|
| `Ratings.tsx` | `/ratings` | `useTeamRatings`, `useHomeCourtEffect` |
| `Forecast.tsx` | `/forecast` | `useTeamForecast`, `useLeagueMomentum` |

---

## What To Build Next (Phase 6 — Second Wave)

### Priority 1: NLP Engine (SCR-322)
**Why**: Sentiment analysis and NER directly complement the RAG + fine-tuning stack. Player sentiment from news feeds feeds into the momentum engine.

**What to build**:
- `backend/src/intelligence/nlp_engine.py`
  - Sentiment classifier (positive/negative/neutral) on sports news text
  - Named Entity Recognition for player names, team names, event types
  - Text classification: injury report vs trade news vs game recap
- Integration with `vector_store.py` (tag ingested docs with sentiment at index time)
- New API endpoint: `GET /api/v1/nlp/sentiment?text=...`
- Learning notes: `docs/learning-notes/nlp-sentiment-ner-deep-dive.md`

**Dependencies to add**:
```
transformers>=4.38.0
spacy>=3.7.0
```

**Interview angle**: "We run a lightweight distilBERT sentiment classifier at RAG index time — every document gets a sentiment tag. When a user asks about team morale, we can filter the vector store to retrieve only negative-sentiment news from the last 7 days. This is metadata-filtered RAG."

---

### Priority 2: Knowledge Graphs (SCR-315)
**Why**: Graph relationships (player → team → coach → arena) enable multi-hop reasoning that vector search can't do. "Which teams share a coaching philosophy with the Celtics?" requires graph traversal.

**What to build**:
- Neo4j graph database (Docker local / GCP Aura for production)
- `backend/src/intelligence/graph_store.py`
  - Nodes: Team, Player, Coach, Arena, Season
  - Edges: plays_for, coached_by, plays_at, won_against
- Graph-augmented RAG: combine pgvector similarity + graph path distance
- New API endpoint: `GET /api/v1/graph/related?entity=LeBron+James&hops=2`
- Learning notes: `docs/learning-notes/knowledge-graphs-neo4j-deep-dive.md`

**Dependencies to add**:
```
neo4j>=5.0.0
```

---

## Key Files To Read Before Starting

| File | Why |
|------|-----|
| `docs/architecture/phase-6-advanced-skills-plan.md` | Full Phase 6 implementation plan |
| `docs/decisions/decision-log.md` | All architectural decisions (entries 98–110 cover Phase 6) |
| `docs/decisions/claude-agent-rules.md` | Operating rules for this project |
| `CLAUDE.md` | Session start instructions |
| `docs/learning-notes/future-learning-roadmap.md` | Roadmap with Phase 6 as Level 4 |

---

## Key Integration Points

| Existing File | Purpose | Modules That Touch It |
|---------------|---------|----------------------|
| `backend/src/models/trainer.py` | Model training orchestration | PyTorch, Time-Series |
| `backend/src/models/predictor.py` | Inference engine | PyTorch, Time-Series |
| `backend/src/intelligence/langgraph_chat_service.py` | Chatbot graph | LangChain, Multi-Agent |
| `backend/src/api/chat_routes.py` | Chat endpoints | LangChain, Multi-Agent |
| `backend/src/data/feature_store.py` | Feature engineering SQL | Statistics, Time-Series |
| `backend/src/intelligence/vector_store.py` | pgvector RAG | LangChain, NLP Engine |
| `backend/src/intelligence/chat_service.py` | Legacy chatbot engine | LangChain (wraps as tools) |
| `backend/requirements.txt` | Dependencies | ALL modules |
| `frontend/src/App.tsx` | Frontend router | Stats page, Forecast page |

---

## Phase 6 Database Migrations (All Applied)

| Migration | Module | Tables |
|-----------|--------|--------|
| `0003_add_chat_memory_table.py` | 6.1 LangChain | `chat_sessions`, `chat_messages` |
| `0004_add_experiments_table.py` | 6.4 Statistics | `ab_experiments`, `causal_results` |
| `0005_add_forecasts_table.py` | 6.5 Time-Series | `team_forecasts` |

---

## Phase 6 Learning Notes (All Created)

| Module | Note |
|--------|------|
| 6.1 LangChain/LangGraph | `docs/learning-notes/langchain-langgraph-deep-dive.md` |
| 6.2 PyTorch | `docs/learning-notes/pytorch-neural-networks-deep-dive.md` |
| 6.4 Statistics | _(to create: `docs/learning-notes/statistics-ab-bayesian-causal-deep-dive.md`)_ |
| 6.5 Time-Series | _(to create: `docs/learning-notes/timeseries-forecasting-deep-dive.md`)_ |
| 6.6 LLM Fine-tuning | `docs/learning-notes/llm-finetuning-lora-deep-dive.md` |

---

## Rules For This Project

- **Teach before code**: Explain WHAT and WHY before writing code
- **Decision log**: Update `docs/decisions/decision-log.md` for every architectural decision
- **Learning notes**: Create `docs/learning-notes/{module}-deep-dive.md` after each module
- **Linear sync**: Update ticket status and add completion comments
- **Tests required**: Every module needs unit + integration tests
- **No standalone scripts**: Everything integrates into the existing platform

---

## Success Criteria (Phase 6 Active Wave — All Met)

| Module | Metric | Target | Status |
|--------|--------|--------|--------|
| LangChain | Tool execution success rate | >95% | ✅ |
| PyTorch | MLP integrated into ensemble | Any result valid | ✅ |
| Multi-Agent | Supervisor + 3 specialist agents wired | Demonstrated | ✅ |
| Statistics | SPRT + Bradley-Terry + DiD implemented | Demonstrated | ✅ |
| Time-Series | 14-day Prophet + ARIMA ensemble | Implemented | ✅ |
| Fine-tuning | LoRA dataset + trainer + router | Implemented | ✅ |
