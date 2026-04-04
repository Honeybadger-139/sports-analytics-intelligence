# GameThread

A production-grade NBA analytics platform with ML-powered match predictions, SHAP explainability, risk-optimized bet sizing, AI chatbot with multi-agent orchestration, time-series forecasting, Bayesian team ratings, and a SQL playground — deployed as a hybrid serverless stack on Vercel + GCP Cloud Run.

**Live:** [sports-analytics-intelligence.vercel.app](https://sports-analytics-intelligence.vercel.app)

---

## Architecture

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React 19 + Vite + TypeScript + Tailwind v3 | NBA command-centre dashboard with 10+ pages |
| **Backend** | FastAPI + Gunicorn/Uvicorn + Python 3.11 | REST API, ML inference, static file serving |
| **Database** | PostgreSQL 16 (Docker local / Cloud SQL prod) | Raw data, features, predictions, experiments, audit trail |
| **ML Stack** | XGBoost, LightGBM, PyTorch MLP, TensorFlow Wide & Deep | Ensemble prediction with calibration (Platt/Isotonic) |
| **Explainability** | SHAP | Per-game feature importance and prediction explanations |
| **Risk** | Kelly Criterion | Mathematically optimal fractional bet sizing |
| **AI Chatbot** | LangGraph + Google Gemini + RAG + Multi-Agent Supervisor | Natural-language NBA queries with SSE streaming |
| **Statistics** | SPRT A/B Testing, Bradley-Terry Ratings, DiD Causal Inference | Model comparison, team strength rankings, home-court effect |
| **Forecasting** | Prophet + ARIMA + Momentum Engine | 14-day win-rate forecasts with changepoint detection |
| **Fine-tuning** | LoRA/PEFT on Phi-3-mini | Domain-adapted LLM with platform-generated training data |
| **Observability** | Langfuse + Prometheus + Grafana + Pipeline Audit | LLM tracing, request metrics, every sync leaves a DB trace |
| **CI/CD** | Cloud Build + GitHub Actions | Regression gate on PR, multi-image deploy on merge to main |
| **Deployment** | Vercel (frontend CDN) + Cloud Run (backend) | Hybrid serverless with global edge delivery |
| **Infrastructure** | Cloud SQL, GCS, Pub/Sub, Secret Manager, Artifact Registry | Managed GCP services for data, events, secrets, and images |

---

## Getting Started on a New Machine

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | [python.org](https://www.python.org/downloads/) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org/) |
| Docker Desktop | latest | [docker.com](https://www.docker.com/products/docker-desktop/) |
| make | built-in | pre-installed on macOS/Linux |

### 1. Clone the repo

```bash
git clone git@github.com:Honeybadger-139/sports-analytics-intelligence.git
cd sports-analytics-intelligence
```

### 2. Set up environment variables

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and fill in your keys:

| Key | Required | Description |
|-----|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `GEMINI_API_KEY` | Yes | Google Gemini API key (chatbot + intelligence layer) |
| `CHAT_API_KEY` | Yes | API key for streaming chat endpoint |
| `CHAT_ENGINE` | No | `legacy` (default) or `langgraph` |
| `LANGFUSE_PUBLIC_KEY` | No | Langfuse observability (optional) |
| `LANGFUSE_SECRET_KEY` | No | Langfuse observability (optional) |
| `GCP_PROJECT_ID` | No | Required for Cloud Run / Vertex AI features |
| `GCS_MODELS_BUCKET` | No | GCS bucket for model artifact storage |

See `backend/.env.example` for the full list of 40+ configurable options.

### 3. Install all dependencies (one command)

```bash
make install
```

This installs `npm` packages for the frontend and creates a Python `venv` for the backend automatically.

### 4. Start the database

```bash
make db-start
```

This starts the PostgreSQL Docker container (`sports-analytics-db`). Make sure Docker Desktop is running first.

### 5. Run the app

**Option A — Test/validate mode (single URL: `localhost:8000`)**

```bash
make start
```

Builds the React frontend, then starts the backend. Open `http://localhost:8000` — everything runs from one port.

**Option B — Development mode (hot reload while coding)**

```bash
make dev
```

Starts the backend on `localhost:8000` and the Vite dev server on `localhost:5174`. Open `http://localhost:5174` — changes to frontend files appear in the browser instantly without a full rebuild. API calls are forwarded to `localhost:8000` automatically.

### Optional: Start Grafana (dashboard builder)

```bash
docker-compose up -d grafana
```

Open `http://localhost:3301` (default credentials: `admin` / `admin` unless overridden in `.env`).

Pre-provisioned dashboards are available under the **GameThread** folder:
- `GameThread - League Overview`
- `GameThread - Team & Player Trends`

### Optional: Start TensorFlow Serving (Wide & Deep model)

```bash
docker-compose -f docker-compose.tfserving.yml up -d
```

Serves the Wide & Deep model on `localhost:8501` (REST) and `localhost:8500` (gRPC).

### Optional: Start Airflow (local orchestration)

Use this when you want scheduled API-triggered runs from your laptop.

1. Ensure `CHAT_API_KEY` is set in `.env`.
2. Set Airflow vars in `.env`:
   - `GAMETHREAD_API_BASE_URL` (`http://host.docker.internal:8000` if backend runs on host)
   - `GAMETHREAD_CHAT_API_KEY` (same value as `CHAT_API_KEY`)
3. Start Airflow:

```bash
docker-compose -f docker-compose.base.yml -f docker-compose.dev.yml up -d airflow
```

4. Open Airflow UI at `http://localhost:8088` (default: `admin` / `admin`).
5. Trigger DAG `gamethread_local_api_pipeline` from the UI, or run:

```bash
docker-compose -f docker-compose.base.yml -f docker-compose.dev.yml exec airflow airflow dags trigger gamethread_local_api_pipeline
```

### 6. Stop everything

```bash
make stop
```

---

## Available Make Commands

| Command | What it does |
|---------|-------------|
| `make install` | Install all frontend + backend dependencies (run once after cloning) |
| `make build` | Compile the React frontend into `frontend/dist/` |
| `make start` | Build frontend + start backend on `localhost:8000` |
| `make dev` | Start backend (8000) + Vite hot-reload server (5174) for active coding |
| `make db-start` | Start the PostgreSQL Docker container |
| `make stop` | Stop all running servers |

---

## Project Structure

```
sports-analytics-intelligence/
├── Makefile                        ← all common commands live here
├── cloudbuild.yaml                 ← Cloud Build CI/CD pipeline (4 images)
├── docker-compose.base.yml         ← shared service definitions
├── docker-compose.dev.yml          ← dev overrides (pgAdmin, Grafana)
├── docker-compose.prod.yml         ← prod overrides (resource limits)
├── docker-compose.tfserving.yml    ← TensorFlow Serving for Wide & Deep
├── backend/
│   ├── main.py                     ← FastAPI entry point + static file serving
│   ├── scheduler.py                ← daily NBA data ingestion scheduler
│   ├── requirements.txt            ← production dependencies
│   ├── requirements-dev.txt        ← dev/test dependencies
│   ├── requirements-pipeline.txt   ← lean pipeline job dependencies
│   ├── .env.example                ← copy to .env and fill in your keys
│   ├── Dockerfile                  ← API serving image
│   ├── Dockerfile.ingestion        ← batch ingestion job image
│   ├── Dockerfile.rag              ← RAG refresh job image
│   ├── Dockerfile.prefect-agent    ← Prefect orchestration agent image
│   ├── alembic/                    ← versioned schema migrations (15 migrations)
│   ├── config/                     ← settings.yaml, model hyperparameters
│   └── src/
│       ├── api/                    ← route handlers (9 route files)
│       │   ├── routes.py           ← teams, matches, standings, predictions
│       │   ├── chat_routes.py      ← chatbot (stream + non-stream + multi-agent)
│       │   ├── stats_routes.py     ← team ratings, home-court effect, A/B tests
│       │   ├── forecast_routes.py  ← time-series forecasts, momentum
│       │   ├── scribble_routes.py  ← SQL playground execution + notebooks
│       │   ├── intelligence_routes.py  ← RAG briefings, context quality
│       │   ├── mlops_routes.py     ← monitoring, retrain policy, drift
│       │   ├── admin_routes.py     ← pipeline triggers, config management
│       │   └── lab_routes.py       ← experiment lab, failed ingestion DLQ
│       ├── data/                   ← ingestion, feature store, DB helpers
│       ├── models/                 ← ML models & training pipelines
│       │   ├── trainer.py          ← multi-model training orchestration
│       │   ├── predictor.py        ← inference engine (ensemble)
│       │   ├── pytorch_model.py    ← PyTorch MLP architecture
│       │   ├── pytorch_trainer.py  ← PyTorch training with early stopping
│       │   ├── tf_model.py         ← TensorFlow Wide & Deep architecture
│       │   ├── tf_trainer.py       ← TF training pipeline
│       │   ├── explainability.py   ← SHAP explanations
│       │   ├── calibrator.py       ← Platt / Isotonic probability calibration
│       │   ├── bet_sizing.py       ← Kelly Criterion stake sizing
│       │   ├── ab_testing.py       ← SPRT sequential model comparison
│       │   ├── bayesian_ratings.py ← Bradley-Terry team strength ratings
│       │   ├── causal_inference.py ← DiD home-court advantage analysis
│       │   ├── timeseries_forecaster.py ← Prophet + ARIMA ensemble
│       │   ├── artifact_store.py   ← versioned model artifact management
│       │   ├── dataset_generator.py ← fine-tuning Q&A data generation
│       │   └── lora_trainer.py     ← LoRA/PEFT fine-tuning pipeline
│       ├── intelligence/           ← AI / chatbot / RAG subsystem
│       │   ├── langgraph_chat_service.py ← LangGraph state-machine chatbot
│       │   ├── chat_service.py     ← legacy chatbot engine
│       │   ├── multi_agent_system.py ← supervisor + specialist agents
│       │   ├── langchain_tools.py  ← LangChain tool wrappers
│       │   ├── output_schemas.py   ← Pydantic structured output schemas
│       │   ├── memory.py           ← PostgreSQL-backed conversation memory
│       │   ├── vector_store.py     ← pgvector RAG retrieval
│       │   ├── langfuse_client.py  ← observability wrapper (fail-open)
│       │   ├── chat_guard.py       ← rate limiting, anomaly detection
│       │   ├── chat_eval.py        ← offline evaluation harness
│       │   └── rules.py            ← deterministic context rules
│       ├── mlops/                  ← monitoring, drift, retrain queue
│       └── config.py              ← centralised configuration
├── frontend/
│   ├── src/
│   │   ├── pages/                  ← 14 page components
│   │   │   ├── Overview.tsx        ← system health + daily predictions
│   │   │   ├── Arena.tsx           ← match cards with live predictions
│   │   │   ├── Chatbot.tsx         ← AI chatbot with SSE streaming
│   │   │   ├── Scribble.tsx        ← SQL playground + notebooks
│   │   │   ├── Ratings.tsx         ← Bradley-Terry team strength rankings
│   │   │   ├── Forecast.tsx        ← 14-day win-rate trajectory charts
│   │   │   ├── Lab.tsx             ← experiment lab + model comparison
│   │   │   ├── Pulse.tsx           ← intelligence briefings
│   │   │   ├── ModelInsight.tsx    ← SHAP explainability deep-dive
│   │   │   ├── Dashboard.tsx       ← drag-and-drop chart builder
│   │   │   └── ...
│   │   └── components/             ← reusable components (Arena/, Chatbot/, etc.)
│   ├── vercel.json                 ← Vercel rewrites → Cloud Run backend
│   ├── package.json
│   └── vite.config.ts
├── infra/                          ← GCP infrastructure configs
│   ├── cloud-run/                  ← service + job YAML definitions
│   ├── cloud-monitoring/           ← custom metrics + alert policies
│   ├── cloud-scheduler/            ← daily pipeline trigger configs
│   ├── vertex-ai/                  ← experiments, model registry, pipelines
│   ├── tf-serving/                 ← TensorFlow Serving Dockerfile + config
│   ├── pubsub/                     ← topic + subscription definitions
│   ├── secret-manager/             ← secret mapping docs
│   ├── airflow/                    ← Composer-ready DAG definitions
│   ├── metabase/                   ← Metabase dashboard configs
│   └── looker-studio/              ← Looker Studio dashboard specs
├── grafana/                        ← pre-provisioned Grafana dashboards
├── scripts/                        ← deployment + utility scripts
├── docs/
│   ├── architecture/               ← system design, DB schema, runbooks
│   ├── decisions/                  ← 100+ architectural decision log entries
│   ├── learning-notes/             ← 50+ concept deep-dives
│   └── images/                     ← architecture diagrams
├── .github/
│   └── workflows/
│       └── backend-regression.yml  ← CI gate on push/PR to main
└── notebooks/                      ← Jupyter experiment notebooks
```

---

## Deployment Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         PRODUCTION STACK                             │
│                                                                      │
│  ┌─────────────────┐          ┌──────────────────────────────────┐  │
│  │   Vercel CDN     │  HTTPS   │        GCP (us-central1)         │  │
│  │   (Frontend)     │────────▶│                                   │  │
│  │                  │          │  ┌────────────┐ ┌─────────────┐  │  │
│  │  React 19 SPA    │          │  │ Cloud Run  │ │ Cloud SQL   │  │  │
│  │  Global Edge     │          │  │ (API)      │─│ PostgreSQL  │  │  │
│  │  Auto-deploy     │          │  │ 1-5 inst.  │ │ 16          │  │  │
│  └─────────────────┘          │  └────────────┘ └─────────────┘  │  │
│                                │                                   │  │
│                                │  ┌────────────┐ ┌─────────────┐  │  │
│                                │  │ Cloud Run  │ │ GCS Buckets │  │  │
│                                │  │ Jobs       │ │ (models,    │  │  │
│                                │  │ • Ingest   │ │  raw data,  │  │  │
│                                │  │ • RAG      │ │  chroma)    │  │  │
│                                │  │ • Migrate  │ └─────────────┘  │  │
│                                │  └────────────┘                   │  │
│                                │                                   │  │
│                                │  ┌────────────┐ ┌─────────────┐  │  │
│                                │  │ Cloud Build│ │ Secret Mgr  │  │  │
│                                │  │ (CI/CD)    │ │ Pub/Sub     │  │  │
│                                │  │ 4 images   │ │ Artifact    │  │  │
│                                │  └────────────┘ │ Registry    │  │  │
│                                │                  └─────────────┘  │  │
│                                └──────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

**CI/CD Pipeline (Cloud Build):**
1. Build API image → Push to Artifact Registry
2. Run Alembic migrations (Cloud Run Job) — deploy aborts if migrations fail
3. Deploy API to Cloud Run (min 1 / max 5 instances, 2 vCPU, 2 GB RAM)
4. Build + push ingestion job image
5. Build + push RAG refresh job image

**GitHub Actions:** Regression gate on every push/PR to `main` — runs `test_ingestion_retry`, `test_routes`, `test_config` with coverage threshold.

---

## Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 0. Data Foundation | Complete | NBA ingestion, schema design, incremental sync, feature store |
| 0.5 Resilience | Complete | Jittered rate limiting, dual logging, audit trail, health dashboard |
| 1. Prediction Engine | Complete | XGBoost/LightGBM ensemble, SHAP explainability, Kelly Criterion |
| 2. Cloud Deployment | Complete | Cloud Run services + jobs, GCS artifacts, Pub/Sub events |
| 3. Pipeline Orchestration | Complete | Prefect flows, Pub/Sub bridge, feature engineering tasks |
| 4. Vertex AI Integration | Complete | Experiments tracking, Model Registry with aliases, Pipelines |
| 5. Cloud Monitoring | Complete | Custom metrics, drift detection (KL divergence), alert policies |
| 6. Advanced Skills (6 modules) | Complete | LangChain tools, PyTorch MLP, Multi-Agent, Statistics, Time-Series, Fine-tuning |
| 7. Delivery Hardening | Complete | CI regression gate + DB-backed invariant tests |
| 8. UI Redesign + Features | Complete | React + Vite + Tailwind redesign, chatbot with SSE streaming, Scribble SQL playground |
| 9. Full Stack Deployment | Complete | Vercel frontend + Cloud Run backend, hybrid serverless |
| 10. Enterprise ML Architecture | Complete | TensorFlow Wide & Deep, decoupled TF Serving, LangGraph Multi-Agent Supervisor |

### Phase 6 — Advanced Skills Modules

| Module | What it adds |
|--------|-------------|
| 6.1 LangChain/LangGraph | Tool-calling agents, Pydantic structured outputs, PostgreSQL conversation memory |
| 6.2 PyTorch Neural Network | MLP baseline for tabular data, entity embeddings, comparison with tree models |
| 6.3 Multi-Agent System | Supervisor + Stats/News/Prediction specialist agents via LangGraph |
| 6.4 Statistics | SPRT sequential A/B testing, Bradley-Terry ratings, DiD causal inference (COVID natural experiment) |
| 6.5 Time-Series Forecasting | Prophet + ARIMA ensemble, momentum scoring, 14-day win-rate forecasts |
| 6.6 LLM Fine-tuning | LoRA on Phi-3-mini with platform-generated Q&A data, LLM router |

---

## API Endpoints

### Core

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/teams` | GET | All NBA teams |
| `/api/v1/matches` | GET | Recent matches with filters |
| `/api/v1/standings` | GET | Team standings by season |
| `/api/v1/predictions/game/{id}` | GET | ML prediction + SHAP explanation |
| `/api/v1/predictions/today` | GET | Today's predictions |
| `/api/v1/predictions/performance` | GET | Historical model performance |
| `/api/v1/predictions/bet-sizing` | GET | Kelly Criterion stake sizing |
| `/api/v1/bets` | POST/GET | Create / list bet ledger entries |
| `/api/v1/bets/summary` | GET | Bankroll KPI summary |

### Intelligence & Chatbot

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat` | POST | AI chatbot (non-streaming) |
| `/api/v1/chat/stream` | POST | AI chatbot with SSE token streaming |
| `/api/v1/chat/agents` | POST | Multi-agent supervisor endpoint |
| `/api/v1/chat/health` | GET | Chatbot readiness (LLM + DB + schema) |
| `/api/v1/intelligence/brief` | GET | Daily intelligence digest |

### Statistics & Forecasting

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/stats/team-ratings` | GET | Bradley-Terry strength rankings with tier labels |
| `/api/v1/stats/home-court-effect` | GET | DiD causal estimate (COVID natural experiment) |
| `/api/v1/stats/ab-test` | POST | SPRT sequential A/B model comparison |
| `/api/v1/forecast/{team_name}` | GET | 14-day Prophet + ARIMA win-rate forecast |
| `/api/v1/forecast/{team_name}/momentum` | GET | Momentum score, trend, current streak |
| `/api/v1/forecast/league/momentum` | GET | All 30 teams ranked by momentum |

### Data Exploration & SQL Playground

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/raw/tables` | GET | Raw-table catalog |
| `/api/v1/raw/{table_name}` | GET | Paginated raw table rows |
| `/api/v1/scribble/execute` | POST | Execute SQL in the playground |
| `/api/v1/scribble/notebooks` | GET/POST | List / create saved notebooks |

### Operations & MLOps

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/system/status` | GET | Pipeline health + audit history |
| `/api/v1/quality/overview` | GET | Data quality snapshot |
| `/api/v1/mlops/monitoring` | GET | Model/data freshness monitoring |
| `/api/v1/mlops/retrain/policy` | GET | Retrain-policy evaluation |
| `/api/v1/admin/pipeline/run-now` | POST | Trigger ingestion + feature engineering |
| `/api/v1/admin/rag/run-now` | POST | Trigger RAG vector store refresh |
| `/api/v1/admin/config/{key}` | PATCH | Live runtime config update (no restart) |
| `/api/v1/lab/failed-ingestion` | GET | Dead-letter queue for failed records |
| `/docs` | GET | Interactive Swagger API docs |

---

## Tech Stack Summary

### Backend

| Category | Libraries |
|----------|-----------|
| Framework | FastAPI, Gunicorn, Uvicorn, Pydantic v2 |
| Database | SQLAlchemy 2.0, psycopg2, Alembic, pgvector |
| ML (Trees) | XGBoost, LightGBM, scikit-learn, SHAP |
| ML (Neural) | PyTorch (MLP), TensorFlow 2.15 (Wide & Deep) |
| AI/LLM | LangChain, LangGraph, Google Gemini, ChromaDB |
| Statistics | statsmodels (SPRT, OLS), scipy |
| Forecasting | Prophet, ARIMA (statsmodels), ruptures |
| Fine-tuning | PEFT/LoRA, TRL, bitsandbytes, transformers (install separately) |
| Observability | Langfuse, Prometheus, slowapi |
| Data | pandas, numpy, nba_api |

### Frontend

| Category | Libraries |
|----------|-----------|
| Framework | React 19, TypeScript 5.9 |
| Build | Vite 7, Tailwind CSS v3, PostCSS |
| State | React Query (TanStack), React Router v7 |
| UI | Framer Motion, Lucide React icons |
| Styling | CSS Modules + Tailwind utilities + CSS custom properties |

---

## Testing

```bash
cd backend

# Targeted regression suite (same as CI)
PYTHONPATH=. venv/bin/pytest tests/test_ingestion_retry.py tests/test_routes.py tests/test_config.py -q

# DB-backed invariant tests (requires running PostgreSQL)
PYTHONPATH=. venv/bin/pytest tests/test_ingestion_db_invariants.py -q
```

---

## Database Migrations

The project uses Alembic as the schema authority. Migrations run automatically in CI (Cloud Run Job) before API deployment.

```bash
cd backend

# Apply all migrations
PYTHONPATH=. venv/bin/alembic upgrade head

# Check current migration state
PYTHONPATH=. venv/bin/alembic current
```

Key migrations include: initial schema + Wave 3 tables, chat memory, experiments, forecasts, pre-game predictions, player positions, conference/division backfill, and data cleanup migrations.

---

## Docker Compose Profiles

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Backward-compatible default (dev profile) |
| `docker-compose.base.yml` | Shared services: PostgreSQL 16 + backend |
| `docker-compose.dev.yml` | Dev overrides: pgAdmin, Grafana, hot-reload |
| `docker-compose.prod.yml` | Prod overrides: resource limits, no tooling |
| `docker-compose.tfserving.yml` | TensorFlow Serving for Wide & Deep model |

```bash
# Dev environment (full tooling)
docker-compose -f docker-compose.base.yml -f docker-compose.dev.yml up

# Production-like environment
docker-compose -f docker-compose.base.yml -f docker-compose.prod.yml up
```

---

## Documentation

- [System Architecture](docs/architecture/system-design.md)
- [Database Schema](docs/architecture/database-schema.md)
- [Phase Execution Runbook](docs/architecture/phase-execution-runbook.md)
- [Phase 6 Advanced Skills Plan](docs/architecture/phase-6-advanced-skills-plan.md)
- [Chatbot LangGraph Workflow](docs/architecture/chatbot-langgraph-workflow.md)
- [SSE Streaming Architecture](docs/architecture/chatbot-streaming-sse.md)
- [Decision Log (100+ entries)](docs/decisions/decision-log.md)
- [Learning Notes (50+ deep-dives)](docs/learning-notes/)

---

## What This Project Demonstrates

| Skill Area | Implementation |
|------------|---------------|
| **ML Engineering** | Multi-model ensemble (XGBoost + LightGBM + PyTorch MLP + TF Wide & Deep), probability calibration, SHAP explainability, versioned artifacts with rollback |
| **MLOps** | Drift detection (PSI), retrain queue with policy engine, Vertex AI Experiments + Model Registry, Cloud Monitoring custom metrics |
| **Data Engineering** | Incremental sync with watermarking, feature engineering in SQL (window functions), dead-letter queue, Alembic schema migrations |
| **GenAI / LLM** | LangGraph state-machine chatbot, multi-agent supervisor architecture, RAG with quality gating, LoRA fine-tuning, SSE streaming |
| **Statistics** | SPRT sequential testing, Bradley-Terry ratings, Difference-in-Differences causal inference using COVID as a natural experiment |
| **Time-Series** | Prophet + ARIMA ensemble forecasting, momentum scoring, changepoint detection |
| **Cloud Architecture** | Hybrid Vercel + Cloud Run deployment, Cloud Build CI/CD (4 container images), Pub/Sub event-driven handoff, Secret Manager |
| **Frontend** | React 19 + TypeScript SPA, Tailwind + CSS Modules hybrid styling, React Query, drag-and-drop dashboard builder, SSE streaming UI |
| **Production Patterns** | Feature-flagged migrations, graceful degradation, DB-backed runtime config, rate limiting, API key auth, CORS, health probes |

---

## License

MIT
