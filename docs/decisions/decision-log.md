# Decision Log — Sports Analytics Intelligence Platform

> This is the **interview cheat sheet**. Every architectural and technical decision is documented here with alternatives considered, rationale, trade-offs, and interview angles.

---

## How to Read This Log

| Column | Purpose |
|--------|---------|
| **Decision** | What we chose |
| **Alternatives** | What else we could have used |
| **Why This Choice** | The reasoning — this is what you say in interviews |
| **Trade-off** | What we gave up — shows mature thinking |
| **Interview Angle** | How to frame this if asked |

---

## Infrastructure Decisions

| # | Decision | Alternatives | Why This Choice | Trade-off | Interview Angle |
|---|----------|-------------|-----------------|-----------|-----------------|
| 1 | **FastAPI + HTML/CSS/JS** over Streamlit | Streamlit, Gradio, Dash | Premium visual impact, decoupled API+frontend architecture (production pattern), broader skill signal on resume | More development time than Streamlit | "I designed a decoupled ML system — API serves predictions, frontend consumes them. This is the pattern used in production ML systems." |
| 2 | **PostgreSQL** over SQLite | SQLite, MongoDB, DuckDB | Window functions for rolling features, JSONB for flexible metadata, concurrent access for API + data pipeline, production-grade RDBMS | Requires Docker setup (but trivial) | "I used PostgreSQL because I needed window functions for time-series feature computation and concurrent read/write for the API and ingestion pipeline." |
| 3 | **Docker Compose** for infrastructure | Local installs, Kubernetes | Reproducible environment, single-command setup, consistent across dev/prod | Learning curve for Docker beginners | "I containerized the stack for reproducibility — any team member can run `docker-compose up` and have the full environment." |
| 4 | **ChromaDB** over Pinecone | Pinecone, Weaviate, FAISS | Free, local, Python-native, no cloud costs or API limits | Less scalable than managed solutions | "I chose a local vector store to avoid cloud dependency and keep costs zero while maintaining full functionality." |
| 5 | **Gemini LLM** for RAG | OpenAI GPT, Claude, Llama local | Free tier available, good quality, user already has API key | Vendor dependency (but designed model-agnostic) | "I designed the RAG layer model-agnostic — swapping LLMs requires changing one config value." |

## ML Decisions

| # | Decision | Alternatives | Why This Choice | Trade-off | Interview Angle |
|---|----------|-------------|-----------------|-----------|-----------------|
| 6 | **XGBoost + LightGBM** over Neural Nets | Deep Learning, Random Forest, SVM | Tabular data with <100 features — GBMs consistently outperform NNs on tabular data (Grinsztajn et al., 2022 NeurIPS benchmark) | Less flexible for unstructured/sequence data | "For structured tabular data, gradient boosted trees remain SOTA. The Grinsztajn benchmark showed NNs only win when data exceeds 10K+ features or is inherently sequential." |
| 7 | **SHAP** over LIME | LIME, Permutation Importance, Partial Dependence | Consistent Shapley values with mathematical guarantees, handles feature interactions, model-agnostic | Computationally slower than LIME | "SHAP provides theoretically grounded explanations based on cooperative game theory. Unlike LIME, SHAP values satisfy consistency, missingness, and local accuracy axioms." |
| 8 | **Kelly Criterion** over flat staking | Flat %, Proportional, Fixed amount | Mathematically optimal capital growth rate (Shannon, 1956), accounts for both edge AND odds | Can be aggressive — hence fractional Kelly | "I used the Kelly Criterion from information theory for capital allocation. It maximizes the geometric growth rate of capital. In practice, I use fractional Kelly (quarter/half) to reduce variance." |
| 9 | **Ensemble** (weighted avg) | Single best model, Stacking, Blending | Reduces variance without adding complexity, robust to individual model failures | Slightly higher latency | "Ensembling reduces variance — if one model overfits to a pattern, the ensemble smooths it out. I use validation-set performance to weight the models." |

## Data Pipeline Decisions

| # | Decision | Alternatives | Why This Choice | Trade-off | Interview Angle |
|---|----------|-------------|-----------------|-----------|-----------------| 
| 10 | **nba_api** (Python package) over web scraping | BeautifulSoup scraping, paid APIs (SportsRadar), manual CSV downloads | Official NBA.com endpoints → structured JSON, no HTML parsing fragility, free, actively maintained by community | No real-time streaming (batch only), rate-limited to ~1 req/sec | "I used the official NBA stats API wrapper because it provides structured, reliable data without the fragility of web scraping. In production, API > scraping for maintainability." |
| 11 | **SQLAlchemy Core** over raw psycopg2 | Raw psycopg2, Django ORM, Peewee | Connection pooling out of the box, database-agnostic (can swap to MySQL/SQLite), Alembic integration for migrations, supports both raw SQL and ORM patterns | Slightly more abstraction than raw driver | "I used SQLAlchemy because it provides connection pooling — critical for handling concurrent FastAPI requests — and makes the data layer database-agnostic." |
| 12 | **Config-driven** (settings.yaml) over hardcoded constants | Hardcoded, JSON config, Python config module, env-vars only | YAML is human-readable, supports comments, hierarchical structure for nested config, separates config from code | Requires a YAML parser (trivial) | "I externalized all tuning parameters to YAML — model hyperparameters, risk thresholds, data sources. This means A/B testing different configs requires zero code changes, just a config swap." |
| 13 | **Separated raw data vs. computed features** (two tables) over single denormalized table | Single `enriched_games` table, feature columns alongside raw stats | Raw data is immutable — changing feature logic doesn't require re-ingesting from NBA API, clear lineage (raw → features → predictions), can recompute features without touching source data | More JOINs required | "I separated raw observations (`team_game_stats`) from computed features (`match_features`) following the immutable raw data principle. This means I can iterate on feature engineering without re-ingesting data — crucial for rapid experimentation." |

---

*This log is updated as new decisions are made throughout the project.*
