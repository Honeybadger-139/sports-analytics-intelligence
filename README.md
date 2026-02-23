# 🏀 Sports Analytics Intelligence Platform

A production-grade ML platform for sports analytics covering match outcome prediction, risk-optimized portfolio sizing, and AI-powered intelligence.

## Architecture

**Backend**: FastAPI (Python 3.11) serving ML predictions as REST API  
**Frontend**: HTML + CSS + JavaScript premium dashboard  
**Database**: PostgreSQL 16 (Dockerized)  
**ML Stack**: XGBoost, LightGBM, SHAP, Kelly Criterion  
**Intelligence**: RAG agent with Gemini LLM + ChromaDB  

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/<your-username>/sports-analytics-intelligence.git
cd sports-analytics-intelligence
cp .env.example .env

# 2. Start PostgreSQL
docker-compose up -d postgres

# 3. Setup Python environment
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Run the API
uvicorn main:app --reload

# 5. Open the dashboard
open ../frontend/index.html
```

## Project Structure

```
├── docs/                  📂 Architecture, decisions, learning notes
├── backend/               🔧 FastAPI ML API
├── frontend/              🎨 Premium HTML+CSS+JS dashboard
├── notebooks/             📊 EDA and analysis
├── docker-compose.yml     🐳 PostgreSQL + services
└── README.md
```

## Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 1. Data Foundation | 🟡 In Progress | NBA data ingestion, feature engineering, PostgreSQL |
| 2. Prediction Engine | ⬜ Planned | XGBoost/LightGBM ensemble, SHAP, Kelly Criterion |
| 3. Intelligence Layer | ⬜ Planned | RAG agent, rule engine |
| 4. Dashboard & MLOps | ⬜ Planned | Premium frontend, monitoring, deployment |

## Documentation

- [Architecture Design](docs/architecture/)
- [Decision Log](docs/decisions/decision-log.md)
- [Learning Notes](docs/learning-notes/)

## License

MIT
