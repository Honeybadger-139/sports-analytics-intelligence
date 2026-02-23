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

---

*This log is updated as new decisions are made throughout the project.*
