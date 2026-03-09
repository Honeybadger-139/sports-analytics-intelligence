# GameThread

A production-grade NBA analytics platform with ML-powered match predictions, SHAP explainability, risk-optimized bet sizing, AI chatbot, and a SQL playground — all served from a single FastAPI backend.

---

## Architecture

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | FastAPI + Python 3.9 | REST API, ML inference, static file serving |
| **Frontend** | React 19 + Vite + TypeScript | NBA command centre dashboard |
| **Database** | PostgreSQL 16 (Docker) | Raw data, features, predictions, notebooks, audit trail |
| **ML Stack** | XGBoost, LightGBM, SHAP | Ensemble prediction with per-game explainability |
| **Risk** | Kelly Criterion | Mathematically optimal bet sizing |
| **AI Chatbot** | Google Gemini + RAG | Natural-language NBA queries over live DB |
| **Observability** | Langfuse + Pipeline Audit | LLM chain tracing + every sync leaves a DB trace |

---

## Getting Started on a New Machine

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.9+ | [python.org](https://www.python.org/downloads/) |
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
| `GEMINI_API_KEY` | Yes | Google Gemini API key (chatbot) |
| `LANGFUSE_PUBLIC_KEY` | No | Langfuse observability (optional) |
| `LANGFUSE_SECRET_KEY` | No | Langfuse observability (optional) |

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

## Branch Strategy

```
main              ← production — what gets deployed to the server
  ├── ui-redesign ← UI / design changes
  ├── chatbot     ← chatbot feature work
  └── scribble    ← SQL playground feature work
```

**Workflow:**
1. Check out the relevant feature branch
2. Code with `make dev` (hot reload on `localhost:5174`)
3. Validate with `make start` (production build on `localhost:8000`)
4. Push to your feature branch
5. Merge into `main` when ready to ship

> **Note:** The `frontend/dist/` build output is gitignored. Run `make build` (or `make start`) to regenerate it. The `Makefile` handles this automatically.

---

## Project Structure

```
sports-analytics-intelligence/
├── Makefile                    ← all common commands live here
├── backend/
│   ├── main.py                 ← FastAPI entry point + static file serving
│   ├── scheduler.py            ← daily NBA data ingestion scheduler
│   ├── requirements.txt
│   ├── .env.example            ← copy to .env and fill in your keys
│   └── src/
│       ├── api/                ← route handlers (teams, chat, scribble, …)
│       ├── data/               ← ingestion, feature store, DB helpers
│       ├── models/             ← ML trainer, predictor, SHAP, bet sizing
│       ├── intelligence/       ← RAG + chatbot + Langfuse observability
│       └── config.py           ← centralised configuration
├── frontend/
│   ├── src/                    ← React + TypeScript source
│   ├── dist/                   ← production build output (gitignored)
│   ├── package.json
│   └── vite.config.ts
├── docs/
│   ├── architecture/           ← system design, DB schema, runbooks
│   ├── decisions/              ← architectural decision log
│   └── learning-notes/         ← concept deep-dives
└── docker-compose.yml          ← PostgreSQL + pgAdmin
```

---

## Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 0. Data Foundation | Complete | NBA ingestion, schema design, incremental sync, feature store |
| 0.5 Resilience | Complete | Jittered rate limiting, dual logging, audit trail, health dashboard |
| 1. Prediction Engine | Complete | XGBoost/LightGBM ensemble, SHAP explainability, Kelly Criterion |
| 2. Prediction Operations | Complete | Today feed, prediction persistence, performance analytics, bets ledger |
| 3. Frontend Integration | Complete | Tab-based NBA console |
| 4. Intelligence Layer | Complete | RAG context APIs + citation guardrails + source-quality scoring |
| 5. MLOps | Complete | Monitoring API + trend/escalation + retrain queue + worker lifecycle |
| 6. Delivery Hardening | Complete | CI regression gate + DB-backed invariant tests |
| 7. UI Redesign + Features | Active | React + Vite redesign, chatbot, Scribble SQL playground, Langfuse |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/teams` | GET | All NBA teams |
| `/api/v1/matches` | GET | Recent matches with filters |
| `/api/v1/standings` | GET | Team standings by season |
| `/api/v1/predictions/game/{id}` | GET | ML prediction + SHAP explanation |
| `/api/v1/predictions/today` | GET | Today's predictions |
| `/api/v1/predictions/performance` | GET | Historical model performance |
| `/api/v1/predictions/bet-sizing` | GET | Kelly Criterion stake sizing |
| `/api/v1/raw/tables` | GET | Raw-table catalog |
| `/api/v1/raw/{table_name}` | GET | Paginated raw table rows |
| `/api/v1/quality/overview` | GET | Data quality snapshot |
| `/api/v1/intelligence/brief` | GET | Daily intelligence digest |
| `/api/v1/mlops/monitoring` | GET | Model/data freshness monitoring |
| `/api/v1/mlops/retrain/policy` | GET | Retrain-policy evaluation |
| `/api/v1/bets` | POST/GET | Create / list bet ledger entries |
| `/api/v1/bets/summary` | GET | Bankroll KPI summary |
| `/api/v1/system/status` | GET | Pipeline health + audit history |
| `/api/v1/chat` | POST | AI chatbot (NBA natural-language queries) |
| `/api/v1/chat/health` | GET | Chatbot readiness (LLM + DB + schema) |
| `/api/v1/scribble/execute` | POST | Execute SQL in the playground |
| `/api/v1/scribble/notebooks` | GET/POST | List / create saved notebooks |
| `/docs` | GET | Interactive Swagger API docs |

---

## Testing

```bash
cd backend
PYTHONPATH=. venv/bin/pytest tests/test_ingestion_retry.py tests/test_routes.py tests/test_config.py -q
PYTHONPATH=. venv/bin/pytest tests/test_ingestion_db_invariants.py -q
```

---

## Documentation

- [System Architecture](docs/architecture/system-design.md)
- [Database Schema](docs/architecture/database-schema.md)
- [Phase Execution Runbook](docs/architecture/phase-execution-runbook.md)
- [Decision Log](docs/decisions/decision-log.md)
- [Learning Notes](docs/learning-notes/)

---

## License

MIT
