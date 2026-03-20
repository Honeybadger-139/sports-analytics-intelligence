# ML Solutions Architect Audit — GameThread
**Date:** 2026-03-19
**Auditor:** Claude (ML Solutions Architect / MLOps Engineer role)
**Project State at Audit:** Phases 0–8 complete, Phase 9 (React redesign) in progress.

---

## Task 1 — Deep-Dive Component Audit

### Layer 1: Data & Pipeline

**Strengths:**
- Incremental watermark-based sync (avoids full-season reloads on every run)
- Idempotent upserts via `INSERT ... ON CONFLICT DO UPDATE`
- `pipeline_audit` table captures status, elapsed time, row count, errors as JSONB
- APScheduler at 06:30 UTC + safety-net feature rebuild at 07:30 UTC
- 24 well-chosen features: rolling win%, point differential, offensive/defensive rating, pace, eFG%, H2H win%, streak, back-to-back flag

**Issues Found:**
1. `fillna(0)` in `load_training_dataset()` is domain-incorrect for H2H features — a true zero means "never beaten them", a missing value means "no history". Impute H2H to 0.5 (league average), add `h2h_data_available` binary indicator.
2. No data validation gate between ingestion and feature computation. Partial NBA API responses (during live games) can silently produce corrupted features.
3. ChromaDB runs as embedded local file (`RAG_CHROMA_DIR=backend/data/chroma`) — not persistent across container rebuilds unless volume is intact. The Docker Compose ChromaDB service is commented out.

---

### Layer 2: Model Registry / Weights

**Strengths:**
- Versioned artifacts: `{model_name}_{YYYYMMDD_HHMMSS}.pkl` via joblib
- Keep-N retention (default 3) purges old versions
- Active model path stored in `app_config` DB table — rollback without restart
- Calibrators (Platt/isotonic) saved alongside models
- `TimeSeriesSplit(n_splits=5)` for cross-validation — correct for temporal data
- AUC-proportional ensemble weights

**Issues Found:**
1. File-system based artifact store breaks in multi-instance deployments (two pods = two divergent model states). Production fix: S3/GCS with a thin `boto3` wrapper, or shared NFS volume.
2. No version compatibility check on `joblib.load()` — different sklearn/XGBoost versions can cause deserialization failures. Must save `{"sklearn": "...", "xgboost": "...", "python": "..."}` in training metadata and assert on load.
3. No ONNX export path. XGBoost/LightGBM support ONNX natively — export gives 2-3x inference speedup and decouples serving from training libraries.

---

### Layer 3: Backend / Inference API

**Strengths:**
- FastAPI with lifespan context (correct pattern for startup/shutdown)
- Alembic migrations run on startup
- Prometheus metrics via `prometheus-fastapi-instrumentator`
- Trace IDs injected in middleware, propagated in response headers
- Rate limiting via slowapi with jittered backoff
- `Predictor` singleton pattern: models loaded once at startup
- SHAP explanations computed per-request alongside predictions

**Critical Issues Found:**
1. **`--reload` in production Dockerfile CMD** — most impactful bug. This flag: spawns a filesystem watchdog, reloads models on any file change, and disables multi-worker serving. Must be replaced with Gunicorn + UvicornWorker.
2. `allow_origins=["*"]` CORS setting — allows any website to make cross-origin requests. Must be locked to `ALLOWED_ORIGINS` env var before deployment.
3. Single-worker Uvicorn — SHAP computations (CPU-intensive) block concurrent requests under the GIL. Fix: Gunicorn with 2–4 workers.
4. `routes.py` is 62KB — DB query logic is embedded directly in route handlers. Must be refactored to a repository/store layer for testability.

---

### Layer 4: Frontend / UI

**Strengths:**
- React 19 + TypeScript 5.9, TanStack Query for server state
- Sport-context gate prevents premature routing to unimplemented sports
- CSS Modules + Tailwind for scoped, consistent styling
- Framer Motion for smooth UX
- Served as static build from `frontend/dist/` via FastAPI StaticFiles

**Issues Found:**
1. No frontend tests. 9,673 LOC across 54 TypeScript files with zero test coverage.
2. No Nginx in front of static assets — no caching headers, no gzip compression, no response buffering.
3. API base URL should be moved to `VITE_API_BASE_URL` env var for environment portability.

---

## Task 2 — Production-Grade ML Readiness

### Fix Priority Order

**Priority 1 — Fix Dockerfile (remove `--reload`, add Gunicorn)**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ libpq-dev curl \
  && rm -rf /var/lib/apt/lists/*
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt && pip install --no-cache-dir gunicorn==22.0.0
COPY . .
EXPOSE 8000
CMD ["gunicorn", "main:app", "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", "--bind", "0.0.0.0:8000", "--timeout", "120", \
     "--keep-alive", "5", "--access-logfile", "-"]
```
Worker count guidance: t3.small (2GB RAM) → 2 workers; t3.medium (4GB RAM) → 4 workers. Each worker loads ~600-800MB of model state.

**Priority 2 — Fix apscheduler pin**
Change `apscheduler>=3.10.0` to `apscheduler==3.11.2`. APScheduler 4.x has a breaking API change.

**Priority 3 — Split requirements.txt**
- `requirements-prod.txt`: remove jupyter, matplotlib, seaborn (~400MB savings in Docker image)
- `requirements-dev.txt`: includes EDA tools + pytest

**Priority 4 — Fix CORS**
```python
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5174").split(",")
```

**Priority 5 — Remove hardcoded fallback credentials**
`trainer.py` and `predictor.py` fall back to `postgresql://analyst:analytics2026@localhost:5432/sports_analytics`. Remove the fallback — raise if `DATABASE_URL` is not set.

**Priority 6 — Add new env vars**
```bash
WORKERS=2
LOG_LEVEL=info
ALLOWED_ORIGINS=https://yourdomain.com,http://localhost:5174
VITE_API_BASE_URL=http://localhost:8000
```

**Priority 7 — Fix urllib3 constraint**
`urllib3<2` suppresses security patches and is only needed for non-standard SSL builds. On standard cloud VMs (OpenSSL), change to `urllib3>=2.0,<3`.

**Priority 8 — Containerize ChromaDB**
Uncomment ChromaDB service in `docker-compose.yml`. Point `RAG_CHROMA_DIR` to container volume. Local embedded Chroma is not durable across container rebuilds.

---

## Task 3 — Phased DS/ML Roadmap

### Phase 1 — Core ML Stability (1–2 weeks)

| Task | What | Why |
|------|------|-----|
| 1.1 | Domain-aware imputation | `fillna(0)` is wrong for H2H features — misleads model |
| 1.2 | Data validation gate in pipeline | Catch partial NBA API responses before they corrupt features |
| 1.3 | ONNX export for XGB/LGB | 2-3x inference speedup, library-independent serving |
| 1.4 | Version metadata in training artifacts | Prevent joblib deserialization failures after library updates |
| 1.5 | Model warm-up call at startup | Eliminate cold-start latency on first real request |

### Phase 2 — API & Portability (2–3 weeks)

| Task | What | Why |
|------|------|-----|
| 2.1 | Remove `--reload`, add Gunicorn | Enable multi-worker serving, eliminate dev flag in prod |
| 2.2 | Split requirements.txt | Remove EDA tools from prod image (~400MB savings) |
| 2.3 | Externalize CORS, secrets, worker count | Environment portability |
| 2.4 | Refactor routes.py into repositories | Testability, maintainability |
| 2.5 | Add `/healthz` (liveness) and `/readyz` (readiness) | Proper container health probes |
| 2.6 | Containerize ChromaDB | Durable vector store |

### Phase 3 — Deployment & Hosting (3–4 weeks)

| Task | What | Why |
|------|------|-----|
| 3.1 | Choose server (DigitalOcean 4GB or AWS t3.medium) | Minimum viable cloud footprint |
| 3.2 | Add Nginx reverse proxy (TLS, static files, compression) | Production-grade traffic handling |
| 3.3 | CI/CD deployment step: SSH + docker-compose pull on main merge | Zero-downtime rolling updates |
| 3.4 | Persistent volume strategy + daily pg_dump to S3/B2 | Data durability |
| 3.5 | Rotate all secrets with openssl rand -hex 32 | Security before public exposure |

### Phase 4 — Monitoring & Logging (ongoing)

| Task | What | Why |
|------|------|-----|
| 4.1 | Grafana dashboards from Prometheus: req rate, p95 latency, error rate, confidence distribution | Operational visibility |
| 4.2 | Connect mlops_monitoring_snapshot to Grafana | Visual drift detector |
| 4.3 | Structured JSON logs for retrain worker | Aggregatable, searchable audit trail |
| 4.4 | Grafana Alerting: data freshness > 48h, accuracy < 0.55 for 3 days, retrain failure | Human notification closes the MLOps loop |
| 4.5 | KL divergence monitoring between training and live prediction distributions | Senior-level covariate shift detection |

---

## Interview Angles

**On model serving:**
"I separated training from inference. Models are trained in batch, versioned with timestamps, and the active artifact path is stored in the DB so I can roll back to a previous model via API without redeployment."

**On production concerns:**
"I found the Dockerfile used `--reload` in production, which disables multi-worker serving and reloads models on every file change. I replaced it with Gunicorn + UvicornWorker, tuned to the instance's memory ceiling given that each worker loads the full ensemble."

**On MLOps:**
"I have a retrain governance system: monitoring snapshots track accuracy and Brier score, a policy engine evaluates retrain eligibility, a worker executes the retrain, and a purge policy keeps only the last 3 versions. I'm adding KL divergence monitoring to detect covariate shift before it impacts accuracy."

**Junior vs Senior answer on ensembles:**
- Junior: "I used XGBoost because it's the best model."
- Senior: "I started with Logistic Regression as a baseline to confirm features have signal. I used TimeSeriesSplit instead of random k-fold because sports data has temporal dependencies — random splits leak future information. I ensembled XGBoost and LightGBM with AUC-proportional weights because different models capture different patterns."
