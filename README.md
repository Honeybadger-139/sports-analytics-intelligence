# 🏀 Sports Analytics Intelligence Platform

A production-grade ML platform for NBA match outcome prediction, SHAP-powered explainability, risk-optimized bet sizing via Kelly Criterion, and real-time pipeline observability.

---

## Architecture

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | FastAPI (Python 3.11) | ML predictions served as REST API |
| **Frontend** | HTML + CSS + JS | NBA operations dashboard (raw, quality, intelligence, analysis) |
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
│   │   ├── intelligence/   # RAG + rule engine (Phase 4)
│   │   └── config.py       # Centralized configuration
│   ├── tests/              # Pytest test suite
│   ├── config/             # settings.yaml
│   ├── models/             # Saved model artifacts (.pkl)
│   ├── Dockerfile
│   ├── Makefile            # Pipeline automation
│   └── main.py             # FastAPI entry point
├── frontend/
│   ├── index.html          # Multi-tab NBA operations dashboard
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
| 0. Data Foundation | ✅ Complete | NBA ingestion, schema design, incremental sync, feature store groundwork |
| 0.5 Resilience/Observability | ✅ Complete | Jittered rate limiting, dual logging, audit trail, health dashboard |
| 1. Prediction Engine | ✅ Complete | XGBoost/LightGBM ensemble, SHAP explainability, Kelly Criterion |
| 2. Prediction Operations | ✅ Complete (Backend) | Today feed, prediction persistence, performance analytics, bets ledger APIs |
| 3. Frontend Integration | ✅ Complete | Tab-based NBA console: Home, Raw Data Explorer, Data Quality, Analysis |
| 4. Intelligence Layer | ✅ Baseline + 4B Hardening Batch 1 | RAG context APIs + citation guardrails + source-quality scoring + intelligence UX filters |
| 5. Dashboard Enhancements & MLOps | ✅ Foundation + 5A Hardening Batch 1 | Monitoring API + trend endpoint + snapshot persistence + retrain-policy dry-run API |

## Phase 0 Definition Of Done

Phase 0 is considered production-ready only when all checks below pass:

1. Ingestion completes successfully (`make ingest`) with no runtime errors.
2. Data integrity audit passes (`team_stats_violations=0`, `player_stats_missing_games=0`, `null_score_matches=0`).
3. Test suite includes and passes Phase 0 reliability + integrity tests (`pytest backend/tests` or targeted subset).
4. `/api/v1/system/status` exposes latest pipeline health and audit-violation summary.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/teams` | GET | All NBA teams |
| `/api/v1/matches` | GET | Recent matches with filters |
| `/api/v1/standings` | GET | Team standings by season |
| `/api/v1/predictions/game/{id}` | GET | ML prediction + SHAP explanation |
| `/api/v1/predictions/today` | GET | Predictions for today with optional persistence |
| `/api/v1/predictions/performance` | GET | Historical model performance metrics |
| `/api/v1/predictions/bet-sizing` | GET | Kelly Criterion stake sizing |
| `/api/v1/raw/tables` | GET | Raw-table catalog for explorer tab |
| `/api/v1/raw/{table_name}` | GET | Paginated raw table rows |
| `/api/v1/quality/overview` | GET | Data quality + timing + team metrics snapshot |
| `/api/v1/intelligence/game/{game_id}` | GET | Citation-grounded game context brief |
| `/api/v1/intelligence/brief` | GET | Daily intelligence digest |
| `/api/v1/mlops/monitoring` | GET | Model/data freshness monitoring + action-ready escalations |
| `/api/v1/mlops/monitoring/trend` | GET | Monitoring snapshot trend points for charting |
| `/api/v1/mlops/retrain/policy` | GET | Deterministic retrain-policy evaluation (dry-run supported) |
| `/api/v1/mlops/retrain/jobs` | GET | Retrain queue audit view (recent jobs by season) |
| `/api/v1/bets` | POST | Create bet ledger entry |
| `/api/v1/bets` | GET | List bet ledger entries |
| `/api/v1/bets/{id}/settle` | POST | Settle bet and compute PnL |
| `/api/v1/bets/summary` | GET | Bankroll KPI summary |
| `/api/v1/features/{game_id}` | GET | Computed features for a game |
| `/api/v1/system/status` | GET | Pipeline health + audit history |

## Documentation

- [System Architecture](docs/architecture/system-design.md)
- [Database Schema](docs/architecture/database-schema.md)
- [Phase Execution Runbook](docs/architecture/phase-execution-runbook.md) — Step-by-step phase delivery plan with validation gates
- [Decision Log](docs/decisions/decision-log.md) — documented architectural decisions with interview framing
- [Learning Notes](docs/learning-notes/) — Interview-ready concept deep dives

## License

MIT
