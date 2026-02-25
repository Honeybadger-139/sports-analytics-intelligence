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
| 14 | **Manual Header Patching** (v1.11.4 logic) for `nba_api` | Upgrade Python 3.9 -> 3.10+, Proxy/VPN, Switching to paid API | Version 1.11.4+ of `nba_api` requires Python 3.10+ due to dependency updates, but the system is on 3.9. Manual patching allows us to restore connectivity to `stats.nba.com` by mimicking a modern browser without the overhead of a Python version upgrade. | Manual patch must be documented clearly as it won't persist if the virtual environment is wiped and rebuilt. | "When the NBA API started blocking our requests, and the library fix required a Python upgrade we weren't ready for, I backported the solution by manually engineering the HTTP headers to mimic a modern browser session. This restored data flow immediately while minimizing infra churn." |
| 15 | **Incremental DB Sync & Watermarking** | Truncate and load daily, full season pull | Selecting the `MAX(game_date)` from the DB to filter API responses prevents redundant upserts, reducing a full season pull (~1200 games) to a tiny delta (~5-10 games) in daily runs. | Must handle the edge case where no data exists (initial load) | "Instead of a naive 'truncate and reload' or repeating heavy upserts daily, I implemented watermarking: selecting the max date from the database and fetching only games on or after that date. This optimized our API rate limits and lowered database IO." |
| 16 | **In-Database Feature Engineering (SQL)** | Python/Pandas processing | SQL Window Functions are optimized for time-series (rolling stats) and relation ops (self-joins for H2H). Pushing computation to the data layer eliminates data movement overhead (moving 100k rows to Python) and ensures consistency across training/serving. | Complex SQL is harder to unit test than Python functions | "I pushed feature engineering into the data layer using PostgreSQL window functions. This is the 'Senior Manager' approach to performance: push computation to the data to avoid the 'Big Data' tax of moving millions of rows into Python memory." |
| 17 | **Resilient API Handler (Exp. Backoff)** | Simple try/except, single delay | NBA.com is flaky; 502/504/429 errors are common. A robust decorator with jittered exponential backoff ensures the pipeline completes even if the network or API flickers. | Longer execution time for failed runs | "I designed the ingestion layer to be 'safe to fail' by implementing an exponential backoff decorator. If the NBA API throttles us, the system waits progressively longer before retrying, ensuring 99.9% pipeline reliability without manual intervention." |
| 18 | **Centralized `config.py` Implementation** | Dotenv alone, Hardcoded constants, Environment variables only | Combining `python-dotenv` with a central `config.py` allows for type-safety, default values, and a single file to update when the tracking season changes. | Slightly more boilerplate, but prevents "constant drift" across multiple modules. | Highlighting "Single Source of Truth" architectural principles. |
| 19 | **Automated Post-Ingestion Audit** | Unit tests on dataframes, Manual spot checks | SQL-based set logic is much faster for checking cross-table consistency (e.g., verifying 2 team records per match). | Adds ~1-2 seconds to the ingestion run, but saves hours of debugging "missing data" in ML training. | "Data Quality as a First-Class Citizen." |
| 20 | **Numeric Data Integrity (`DECIMAL` over `FLOAT`)** | `FLOAT`, `REAL` | Floating point errors in Python/DB aggregations can lead to precision loss (e.g., 0.1+0.2 != 0.3). `DECIMAL(5,3)` ensures exact precision for ML inputs like Shooting % or Offensive Rating. | Slightly more storage/memory | "In betting models, where 0.5% edge is everything, I used exact numeric types (`DECIMAL`) to avoid floating point math errors that could silently bias our model inputs." |
| 21 | **Jittered Rate Limiting** | Fixed delay, No delay | Fixed intervals are easily flagged by anti-scraping firewalls. Random jitter mimics organic human-like behavior. | Slightly unpredictable execution time | "Scraping detection often looks for 'robotic' periodicity. I added randomized jitter to our rate limiting to make the pipeline's footprint indistinguishable from human browsing patterns." |
| 22 | **Dual-Handler Pipeline Logging** | Console-only, CloudWatch/External | Logging to both console (for dev) and a persistent log file (for production traceability) ensures we have a post-mortem trail without needing an external service. | Local disk usage (requires management/rotation) | "I implemented dual-layer logging — real-time visibility in the console and persistent traceability in file logs. This ensures zero data loss for operational tracking." |
| 23 | **Audit-First Ingestion Workflow** | Python-based logs only, No audit | Recording every sync event (record counts, status, errors) in a structured DB table allows for the construction of health dashboards and proactive monitoring. | Extra DB table and write overhead | "I treated observability as a core feature by building a structured auditing layer. Every sync records its 'Pulse' in the database, enabling me to build a health dashboard that proves data reliability before any ML model starts training." |

---


*This log is updated as new decisions are made throughout the project.*
