# 🏀 Sports Analytics Intelligence Platform

A production-grade ML platform for NBA match outcome prediction, SHAP-powered explainability, risk-optimized bet sizing via Kelly Criterion, and real-time pipeline observability.

---

## Architecture

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | FastAPI (Python 3.11) | ML predictions served as REST API |
| **Frontend** | HTML + CSS + JS | System health dashboard |
| **Database** | PostgreSQL 16 (Docker) | Raw data, features, predictions, audit trail |
| **ML Stack** | XGBoost, LightGBM, SHAP | Ensemble prediction with per-game explainability |
| **Risk** | Kelly Criterion | Mathematically optimal bet sizing |
| **Observability** | Pipeline Audit + Dual Logging | Every sync leaves a trace in the database |

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/2001abhigupta/sports-analytics-intelligence.git
cd sports-analytics-intelligence
cp .env.example .env

# 2. Start PostgreSQL (Docker)
docker-compose up -d postgres

# 3. Setup Python environment
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Run the data pipeline
make ingest       # Pull NBA data
make features     # Compute ML features
make train        # Train prediction models

# 5. Start the API
make run-api      # http://localhost:8000/docs
```

## Project Structure

```
sports-analytics-intelligence/
├── backend/
│   ├── src/
│   │   ├── api/            # FastAPI routes (predictions, health, teams)
│   │   ├── data/           # Ingestion, feature store, DB, init.sql
│   │   ├── models/         # Trainer, predictor, explainability, bet sizing
│   │   ├── intelligence/   # RAG agent (Phase 3)
│   │   └── config.py       # Centralized configuration
│   ├── tests/              # Pytest test suite
│   ├── config/             # settings.yaml
│   ├── models/             # Saved model artifacts (.pkl)
│   ├── Dockerfile
│   ├── Makefile            # Pipeline automation
│   └── main.py             # FastAPI entry point
├── frontend/
│   ├── index.html          # System Health Dashboard
│   ├── css/style.css
│   └── js/dashboard.js
├── docs/
│   ├── architecture/       # System design, DB schema, pipeline docs
│   ├── decisions/          # Decision log (23+ architectural decisions)
│   └── learning-notes/     # Interview-ready concept explanations
├── docker-compose.yml      # PostgreSQL + pgAdmin
└── .env.example
```

## Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 1. Data Foundation | ✅ Complete | NBA ingestion, feature engineering, PostgreSQL schema |
| 1.5 Resilience | ✅ Complete | Jittered rate limiting, dual logging, audit trail, health dashboard |
| 2. Prediction Engine | ✅ Complete | XGBoost/LightGBM ensemble, SHAP explainability, Kelly Criterion |
| 3. Intelligence Layer | ⬜ Planned | RAG agent with Gemini LLM + ChromaDB |
| 4. Dashboard & MLOps | ⬜ Planned | Full analytics frontend, model monitoring, deployment |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/teams` | GET | All NBA teams |
| `/api/v1/matches` | GET | Recent matches with filters |
| `/api/v1/standings` | GET | Team standings by season |
| `/api/v1/predictions/game/{id}` | GET | ML prediction + SHAP explanation |
| `/api/v1/predictions/bet-sizing` | GET | Kelly Criterion stake sizing |
| `/api/v1/features/{game_id}` | GET | Computed features for a game |
| `/api/v1/system/status` | GET | Pipeline health + audit history |

## Documentation

- [System Architecture](docs/architecture/system-design.md)
- [Database Schema](docs/architecture/database-schema.md)
- [Decision Log](docs/decisions/decision-log.md) — 23+ documented architectural decisions
- [Learning Notes](docs/learning-notes/) — Interview-ready concept deep dives

## License

MIT
