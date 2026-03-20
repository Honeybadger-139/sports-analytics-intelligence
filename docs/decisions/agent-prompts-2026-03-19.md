# Parallel Agent Prompts — Sports Analytics Intelligence Platform
**Date:** 2026-03-19
**How to use:** Fire all agents within the same phase simultaneously. Wait for all agents in a phase to complete before starting the next phase. Agents within the same phase have NO dependencies on each other.

---

## PHASE 0 — GCP Bootstrap (SEQUENTIAL, human-in-the-loop)
> This phase requires manual GCP console actions. Complete this before firing any agents.

```
Manual steps (you do these in GCP console):
1. Create project: sports-analytics-intelligence
2. Enable APIs: run, sql, storage, pubsub, secretmanager, aiplatform, artifactregistry, cloudbuild, monitoring
3. Create Cloud SQL instance: postgres-16, db-f1-micro, us-central1, DB=sports_analytics, user=analyst
4. Create GCS buckets: gamethread-raw, gamethread-models, gamethread-chroma
5. Create Pub/Sub topic: pipeline-events, subscription: prefect-feature-trigger
6. Create Prefect Cloud account at app.prefect.io, workspace: sports-analytics
7. Store all secrets in Secret Manager: DATABASE_URL, GEMINI_API_KEY, LANGFUSE_SECRET_KEY, PREFECT_API_KEY
8. Create Artifact Registry repo: {region}-docker.pkg.dev/sports-analytics-intelligence/gamethread
```

---

## PHASE 1 — Core ML Fixes (fire all 3 agents simultaneously)

---

### PHASE 1 — Agent A: Data Imputation + Validation Gate

```
You are a senior ML engineer working on the Sports Analytics Intelligence Platform.

CONTEXT: Read these files first before doing anything:
- docs/decisions/decision-log.md (understand project history)
- docs/decisions/mlops-audit-2026-03-19.md (see audit findings)
- backend/src/data/feature_store.py (understand current feature engineering)
- backend/src/models/trainer.py (understand load_training_dataset function)

YOUR TASKS (implement all of these):

TASK 1 — Fix fillna(0) imputation in backend/src/models/trainer.py:
In the load_training_dataset() function, the current code does `df.fillna(0)` which is domain-incorrect.
Replace it with domain-aware imputation:
- For H2H features (h2h_win_pct, h2h_avg_margin): impute with 0.5 and -0.5 respectively (league average)
- For offensive/defensive ratings (avg_off_rating_last_5, avg_def_rating_last_5, opp_*): impute with the column's season median, not 0
- For all other features: keep 0 as default (appropriate for binary flags, counts)
- Add a new binary feature column `h2h_data_available` (1 if h2h_win_pct was not null, 0 if imputed)
- Add `h2h_data_available` to the FEATURE_COLUMNS list in trainer.py
- Also update the corresponding feature computation in feature_store.py to set h2h_data_available correctly

TASK 2 — Add a data validation gate in backend/src/data/feature_store.py:
Before the feature computation begins (at the start of run_feature_engineering()), add a validation function called `validate_raw_data(engine, seasons)` that:
- Queries the matches, team_game_stats tables to get row counts for the current season
- Asserts: total matches >= 10 (not enough data guard)
- Asserts: no critical column has more than 15% null values (check: game_date, home_team_id, away_team_id, points)
- Asserts: max(game_date) is within the past 7 days (stale data guard — ingestion may have failed silently)
- If any assertion fails: log a structured error dict {"validation": "failed", "reason": "...", "value": ...} and write to pipeline_audit with status="validation_failed", then raise a ValueError to stop the pipeline
- If all pass: log {"validation": "passed", "matches": N, "max_date": "..."} and continue

TASK 3 — Update docs/decisions/decision-log.md:
Add two new entries at the top of the file:
Decision 1: Domain-aware feature imputation (what, alternatives, why this choice, trade-off, interview angle)
Decision 2: Pre-feature validation gate (what, alternatives, why this choice, trade-off, interview angle)

TASK 4 — Update docs/learning-notes/ml-engine/ with a new file imputation-and-validation.md:
Cover: What is domain-aware imputation? Why does fillna(0) mislead tree models on H2H features? What is a validation gate and why does it prevent silent corruption? Interview questions on this topic.

After completing all tasks, confirm: "Phase 1-A complete. Changed files: [list]. New files: [list]."
```

---

### PHASE 1 — Agent B: ONNX Export + Artifact Version Metadata

```
You are a senior ML engineer working on the Sports Analytics Intelligence Platform.

CONTEXT: Read these files first before doing anything:
- docs/decisions/decision-log.md (understand project history)
- docs/decisions/mlops-audit-2026-03-19.md (see audit findings)
- backend/src/models/trainer.py (understand training pipeline)
- backend/src/models/artifact_store.py (understand current artifact saving)
- backend/src/models/predictor.py (understand how models are loaded for inference)

YOUR TASKS (implement all of these):

TASK 1 — Add library version metadata to training artifacts in backend/src/models/trainer.py:
In the run_training_pipeline() function, before saving artifacts, build a version_info dict:
{
  "python": sys.version,
  "sklearn": sklearn.__version__,
  "xgboost": xgb.__version__,
  "lightgbm": lgb.__version__,
  "numpy": np.__version__,
  "pandas": pd.__version__,
  "trained_at": timestamp,
  "feature_columns": FEATURE_COLUMNS
}
Save this as backend/models/version_info_{timestamp}.json alongside the model files.
Also embed it inside the training_metadata JSON under a "library_versions" key.

TASK 2 — Add version compatibility check in backend/src/models/predictor.py:
In the _load_latest_models() method, after loading a model, find and read the corresponding version_info JSON.
Check: if loaded sklearn major version != current sklearn major version → log a WARNING (not an error) with the diff.
Check: if loaded xgboost major version != current xgboost major version → log a WARNING.
Do NOT raise an error — just warn, because minor version differences are usually safe. Only raise if major versions differ by more than 1.

TASK 3 — Add ONNX export capability in backend/src/models/artifact_store.py:
Add a new function export_to_onnx(model, model_name, model_dir, timestamp) that:
- For XGBoost models: uses model.save_model(f"{model_dir}/{model_name}_{timestamp}.onnx") (XGBoost's native ONNX export)
- For LightGBM models: uses the booster's to_string or save_model method to export ONNX (use lightgbm's built-in or skl2onnx)
- For LogisticRegression (sklearn Pipeline): uses skl2onnx with convert_sklearn()
- If any ONNX export fails (library not available, unsupported model type): log a WARNING and continue — ONNX export is best-effort, not blocking
- Save alongside the joblib file with .onnx extension
Add a try/except wrapper so ONNX export failure never blocks the main training pipeline.

TASK 4 — Add model warm-up in backend/main.py:
In the lifespan context manager, after the Predictor initializes and loads models, add a warm-up call:
- Create a dummy feature row (all zeros, matching FEATURE_COLUMNS length)
- Call predictor.predict_game_internal(dummy_features) or equivalent
- Log "Model warm-up complete in Xms"
- Catch and log any exception without crashing startup
This eliminates cold-start latency on the first real prediction request.

TASK 5 — Add onnxruntime to requirements.txt and skl2onnx:
Add to requirements.txt under the ML section:
onnxruntime==1.20.1
skl2onnx==0.17.0

TASK 6 — Update docs/decisions/decision-log.md with 2 new entries:
Decision: ONNX export for inference (what, why, trade-offs, interview angle)
Decision: Library version pinning in artifacts (what, why, trade-offs)

Update docs/learning-notes/ml-engine/ with onnx-and-versioning.md covering:
What is ONNX? Why does it matter for production ML? What is model versioning and why do library mismatches cause failures? Interview questions.

After completing all tasks, confirm: "Phase 1-B complete. Changed files: [list]. New files: [list]."
```

---

### PHASE 1 — Agent C: Dockerfile + Requirements Split + CORS Fix

```
You are a senior DevOps / MLOps engineer working on the Sports Analytics Intelligence Platform.

CONTEXT: Read these files first before doing anything:
- docs/decisions/decision-log.md (understand project history)
- docs/decisions/mlops-audit-2026-03-19.md (see audit findings)
- backend/Dockerfile (current Dockerfile — has critical --reload bug)
- backend/requirements.txt (current requirements — needs splitting)
- backend/main.py (understand FastAPI app structure, CORS setup)
- docker-compose.yml and docker-compose.prod.yml

YOUR TASKS (implement all of these):

TASK 1 — Fix the Dockerfile (most critical fix in the entire project):
The current CMD uses --reload which is a development flag that:
(a) spawns a filesystem watchdog process (wastes resources)
(b) reloads all models from disk whenever any source file changes
(c) prevents multi-worker serving
Replace the CMD with Gunicorn + UvicornWorker:
CMD ["gunicorn", "main:app",
     "--worker-class", "uvicorn.workers.UvicornWorker",
     "--workers", "2",
     "--bind", "0.0.0.0:8000",
     "--timeout", "120",
     "--keep-alive", "5",
     "--access-logfile", "-",
     "--error-logfile", "-",
     "--log-level", "info"]
Also ensure gunicorn==22.0.0 is added to the relevant requirements file.
Remove --reload from any other location it appears (docker-compose files, Makefile, etc.)

TASK 2 — Split requirements.txt into 3 files:
Create backend/requirements-prod.txt:
  - Everything from requirements.txt EXCEPT: jupyter, matplotlib, seaborn, pytest*, pytest-asyncio, pytest-cov
  - Add: gunicorn==22.0.0
  - Fix: apscheduler>=3.10.0 → apscheduler==3.11.2 (v4 has breaking API change)
  - Fix: urllib3<2 → urllib3>=2.0,<3 (the <2 constraint is only for non-standard SSL builds)
  - Add: google-cloud-storage==2.18.2, google-cloud-secret-manager==2.22.0, google-cloud-pubsub==2.27.0 (for GCP services)

Create backend/requirements-dev.txt:
  - All items from requirements-prod.txt
  - PLUS: jupyter==1.1.1, matplotlib==3.10.0, seaborn==0.13.2, pytest==8.3.4, pytest-asyncio==0.25.2, pytest-cov==6.0.0

Create backend/requirements-pipeline.txt (for Cloud Run ingestion job image — minimal):
  - sqlalchemy==2.0.36, psycopg2-binary==2.9.10, alembic==1.14.1
  - pandas==2.2.3, numpy==1.26.4, nba_api==1.5.2
  - google-cloud-storage==2.18.2, google-cloud-pubsub==2.27.0, google-cloud-secret-manager==2.22.0
  - python-dotenv==1.0.1, pyyaml==6.0.2, requests==2.32.3, httpx==0.28.1
  - NO FastAPI, NO xgboost, NO lightgbm, NO shap, NO langchain, NO chromadb

Update the Dockerfile to use requirements-prod.txt instead of requirements.txt.

TASK 3 — Fix CORS in backend/main.py:
Find the CORSMiddleware configuration. Replace allow_origins=["*"] with:
```python
import os
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5174,http://localhost:3000")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]
```
Then use ALLOWED_ORIGINS in the allow_origins parameter.

TASK 4 — Remove hardcoded credential fallbacks:
In backend/src/models/trainer.py: the get_engine() function falls back to "postgresql://analyst:analytics2026@localhost:5432/sports_analytics". Remove the fallback string. Raise a clear ValueError("DATABASE_URL environment variable is not set") if the env var is missing.
Check backend/src/models/predictor.py and backend/src/data/db.py for the same pattern and apply the same fix.

TASK 5 — Update .env.example with new variables:
Add these to .env.example with placeholder values and comments:
ALLOWED_ORIGINS=http://localhost:5174,http://localhost:3000
WORKERS=2
LOG_LEVEL=info
GCP_PROJECT_ID=sports-analytics-intelligence
GCS_RAW_BUCKET=gamethread-raw
GCS_MODELS_BUCKET=gamethread-models
PUBSUB_PIPELINE_TOPIC=pipeline-events
PREFECT_API_KEY=<from Secret Manager>
PREFECT_API_URL=https://api.prefect.cloud/api/accounts/<account-id>/workspaces/<workspace-id>

TASK 6 — Update docs/decisions/decision-log.md with entries:
Decision: Gunicorn + UvicornWorker over bare Uvicorn (what, alternatives, why, trade-offs, interview angle)
Decision: requirements split into prod/dev/pipeline (what, why, trade-offs)

After completing all tasks, confirm: "Phase 1-C complete. Changed files: [list]. New files: [list]."
```

---

## PHASE 2 — GCP Foundation + Decoupling (fire all 4 agents simultaneously after Phase 0 + Phase 1 complete)

---

### PHASE 2 — Agent A: Cloud Run Ingestion Job + GCS + Pub/Sub

```
You are a senior MLOps / data engineer working on the Sports Analytics Intelligence Platform.

CONTEXT: Read these files first before doing anything:
- docs/decisions/decision-log.md
- docs/decisions/hybrid-orchestration-plan-2026-03-19.md (the new architecture)
- backend/src/data/ingestion.py (current ingestion logic — you will extract this)
- backend/scheduler.py (current scheduler — you will decouple this)
- backend/requirements-pipeline.txt (created in Phase 1-C — use this for the new Dockerfile)

YOUR GOAL: Extract the raw NBA data ingestion into a standalone Cloud Run Job that:
1. Pulls from the NBA API
2. Writes raw data to GCS as Parquet (data lake)
3. Also upserts into Cloud SQL (same as current, for API serving)
4. Publishes a Pub/Sub completion message
5. Is triggered by Cloud Scheduler (not by FastAPI's APScheduler)

YOUR TASKS:

TASK 1 — Create backend/pipeline/run_ingestion.py (the Cloud Run Job entry point):
This is a standalone Python script (no FastAPI). It should:
- Load env vars from Secret Manager (or .env for local dev): DATABASE_URL, GCS_RAW_BUCKET, PUBSUB_PIPELINE_TOPIC, GCP_PROJECT_ID
- Call run_full_ingestion(seasons=PIPELINE_SEASONS) from src/data/ingestion.py (reuse existing logic)
- After successful ingestion, write Parquet files to GCS:
  * Query matches, team_game_stats, player_game_stats from Cloud SQL for today's ingested data
  * Convert each to a Parquet file using pandas DataFrame.to_parquet()
  * Upload to gs://{GCS_RAW_BUCKET}/{YYYY}/{MM}/{DD}/games.parquet etc.
  * Use google-cloud-storage library
- Publish a Pub/Sub message to {PUBSUB_PIPELINE_TOPIC} with schema:
  {
    "run_id": "{YYYYMMDD_HHMMSS}",
    "status": "success",
    "seasons": [...],
    "rows_ingested": {"matches": N, "team_game_stats": N, "player_game_stats": N},
    "gcs_prefix": "gs://{bucket}/{date}/",
    "ingestion_completed_at": "<ISO timestamp>"
  }
- If ingestion fails, publish {"status": "failed", "error": "..."} to Pub/Sub and exit with code 1
- All logging should be structured JSON ({"event": "...", "level": "INFO", "timestamp": "..."}) for Cloud Logging

TASK 2 — Create backend/Dockerfile.ingestion:
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements-pipeline.txt .
RUN pip install --no-cache-dir -r requirements-pipeline.txt
COPY src/ ./src/
COPY pipeline/run_ingestion.py .
CMD ["python", "run_ingestion.py"]

TASK 3 — Create infra/cloud-scheduler/ingestion-trigger.yaml (documentation for GCP setup):
Document the Cloud Scheduler job configuration:
- Name: trigger-nba-ingestion
- Schedule: 30 6 * * * (06:30 UTC = 12:00 PM IST)
- Target: Cloud Run Job (job-nba-raw-ingestion)
- Retry: max 3 retries, 5 min backoff
- Auth: OIDC service account

TASK 4 — Create infra/cloud-scheduler/rag-trigger.yaml similarly for RAG refresh job.

TASK 5 — Remove APScheduler from FastAPI startup:
In backend/main.py, find the lifespan context manager where scheduler.start() is called.
Add a new env var EMBEDDED_SCHEDULER_ENABLED (default: "false" for production, "true" for local dev).
If EMBEDDED_SCHEDULER_ENABLED == "true": start APScheduler (local dev mode unchanged).
If EMBEDDED_SCHEDULER_ENABLED == "false": skip scheduler, log "Scheduler disabled — using Cloud Run Jobs in production."
Update .env.example to document this flag.
Update docker-compose.dev.yml to set EMBEDDED_SCHEDULER_ENABLED=true.

TASK 6 — Update docs/decisions/decision-log.md:
Decision: Cloud Run Jobs for ingestion (what, alternatives, why, trade-offs, interview angle)
Decision: GCS as raw data lake with Parquet (what, why Parquet, trade-offs)
Decision: Pub/Sub as pipeline handoff signal (what, why, alternatives, interview angle)

Update docs/learning-notes/infrastructure/ with a new file cloud-run-jobs-and-gcs.md covering:
What is a Cloud Run Job vs Cloud Run Service? Why Parquet over CSV? What is Pub/Sub and why use it as a pipeline handoff? When would you use Kafka instead? Interview questions.

After completing all tasks, confirm: "Phase 2-A complete. Changed files: [list]. New files: [list]."
```

---

### PHASE 2 — Agent B: FastAPI API Deployment to Cloud Run

```
You are a senior DevOps engineer working on the Sports Analytics Intelligence Platform.

CONTEXT: Read these files first before doing anything:
- docs/decisions/decision-log.md
- docs/decisions/gcp-mlops-plan-2026-03-19.md
- backend/Dockerfile (updated in Phase 1-C with Gunicorn)
- backend/main.py
- docker-compose.prod.yml

YOUR GOAL: Prepare the FastAPI application for Cloud Run deployment with Cloud SQL and Secret Manager.

YOUR TASKS:

TASK 1 — Add Cloud SQL connection support in backend/src/data/db.py:
Cloud Run connects to Cloud SQL via Cloud SQL Auth Proxy using a Unix socket.
The DATABASE_URL in production will be: postgresql+psycopg2://user:pass@/dbname?host=/cloudsql/{project}:{region}:{instance}
Add logic: if DATABASE_URL starts with "postgresql" and "cloudsql" is in DATABASE_URL → use the socket path.
Otherwise (local dev) → use the URL as-is.
Document this with a comment explaining Cloud SQL Auth Proxy.

TASK 2 — Create cloudbuild.yaml at project root:
This defines the CI/CD pipeline:
steps:
  # Step 1: Run tests
  - name: python:3.11-slim
    entrypoint: bash
    args: ["-c", "cd backend && pip install -r requirements-dev.txt -q && PYTHONPATH=. pytest tests/ -q --tb=short"]

  # Step 2: Build API image
  - name: gcr.io/cloud-builders/docker
    args: ["build", "-t", "${_REGION}-docker.pkg.dev/${PROJECT_ID}/gamethread/api:${SHORT_SHA}", "-f", "backend/Dockerfile", "backend/"]

  # Step 3: Push API image
  - name: gcr.io/cloud-builders/docker
    args: ["push", "${_REGION}-docker.pkg.dev/${PROJECT_ID}/gamethread/api:${SHORT_SHA}"]

  # Step 4: Deploy to Cloud Run (only on main branch)
  - name: gcr.io/google.com/cloudsdktool/cloud-sdk
    entrypoint: bash
    args: ["-c", "if [ '$BRANCH_NAME' = 'main' ]; then gcloud run deploy gamethread-api --image ${_REGION}-docker.pkg.dev/${PROJECT_ID}/gamethread/api:${SHORT_SHA} --region ${_REGION} --platform managed --min-instances 1 --max-instances 5 --memory 2Gi --cpu 2 --timeout 120s --set-env-vars EMBEDDED_SCHEDULER_ENABLED=false --update-secrets DATABASE_URL=DATABASE_URL:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest; fi"]

substitutions:
  _REGION: us-central1
options:
  logging: CLOUD_LOGGING_ONLY

TASK 3 — Create infra/cloud-run/api-service.yaml (documentation of Cloud Run service config):
Document the Cloud Run service configuration:
- Memory: 2Gi (needed for XGBoost + LightGBM + SHAP loaded in 2 workers)
- CPU: 2
- Min instances: 1 (avoid cold starts for prediction serving)
- Max instances: 5
- Concurrency: 80 (Gunicorn handles queueing)
- Timeout: 120s (SHAP computation can take 10-30s)
- Secrets: DATABASE_URL, GEMINI_API_KEY, LANGFUSE_SECRET_KEY from Secret Manager

TASK 4 — Add /healthz and /readyz endpoints to backend/main.py:
Add two lightweight health endpoints:
GET /healthz → returns {"status": "ok"} in < 50ms. No DB query. Used for liveness probe.
GET /readyz → queries the DB with a simple SELECT 1 and checks that the Predictor has models loaded.
Returns {"status": "ready", "db": "ok", "models_loaded": true} or 503 if not ready.
Used by Cloud Run as startup/readiness probe.

TASK 5 — Update docs/decisions/decision-log.md:
Decision: Cloud Run for API serving (what, alternatives considered: GKE, Compute Engine, Cloud Run. Why Cloud Run. Trade-offs. Interview angle)
Decision: /healthz vs /readyz split (what each is, why the split matters, interview angle)

After completing all tasks, confirm: "Phase 2-B complete. Changed files: [list]. New files: [list]."
```

---

### PHASE 2 — Agent C: RAG Refresh Cloud Run Job

```
You are a senior MLOps engineer working on the Sports Analytics Intelligence Platform.

CONTEXT: Read these files first before doing anything:
- docs/decisions/decision-log.md
- docs/decisions/hybrid-orchestration-plan-2026-03-19.md
- backend/scheduler.py (specifically the run_rag_ingestion_job function)
- backend/src/intelligence/ folder (all files — understand the RAG stack)

YOUR GOAL: Extract the RAG vector store refresh into a standalone Cloud Run Job image.

YOUR TASKS:

TASK 1 — Create backend/pipeline/run_rag_refresh.py (standalone Cloud Run Job entry point):
This is a standalone Python script (no FastAPI). It should:
- Load env vars: DATABASE_URL, GEMINI_API_KEY, RAG_CHROMA_DIR, RAG_COLLECTION, INTELLIGENCE_SOURCES, INJURY_SOURCES, GCS_CHROMA_BUCKET
- Call the existing run_rag_ingestion_job() logic from scheduler.py (extract into a reusable function)
- After refreshing ChromaDB, snapshot the ChromaDB directory to GCS:
  * Tar the ChromaDB data directory
  * Upload to gs://{GCS_CHROMA_BUCKET}/snapshots/{YYYYMMDD_HH}.tar.gz
  * Keep only the last 5 snapshots (delete older ones)
  * This gives ChromaDB backup/restore capability
- Exit with code 0 on success, 1 on failure
- Structured JSON logging throughout

TASK 2 — Create backend/Dockerfile.rag:
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*
Create a backend/requirements-rag.txt with only what the RAG job needs:
  - sqlalchemy, psycopg2-binary
  - google-generativeai, chromadb, langchain
  - google-cloud-storage, google-cloud-secret-manager
  - httpx, requests, feedparser (for RSS), python-dotenv
  - NO xgboost, NO lightgbm, NO shap, NO fastapi, NO uvicorn
COPY requirements-rag.txt .
RUN pip install --no-cache-dir -r requirements-rag.txt
COPY src/ ./src/
COPY pipeline/run_rag_refresh.py .
CMD ["python", "run_rag_refresh.py"]

TASK 3 — Create infra/cloud-scheduler/rag-triggers.yaml:
Document 4 Cloud Scheduler jobs for RAG refresh:
- trigger-rag-00: 0 0 * * * (00:00 UTC)
- trigger-rag-06: 0 6 * * * (06:00 UTC)
- trigger-rag-12: 0 12 * * * (12:00 UTC)
- trigger-rag-18: 0 18 * * * (18:00 UTC)
All targeting: Cloud Run Job job-rag-refresh

TASK 4 — Update the Cloud Build pipeline (cloudbuild.yaml from Phase 2-B):
Add build + push steps for Dockerfile.rag:
- Build: ${_REGION}-docker.pkg.dev/${PROJECT_ID}/gamethread/rag:${SHORT_SHA}
- Push: same
- Update Cloud Run Job on main branch only: gcloud run jobs update job-rag-refresh --image ...

TASK 5 — Update docs/decisions/decision-log.md:
Decision: Separate RAG refresh image (what, why isolated from API, trade-offs)
Decision: ChromaDB snapshots to GCS (what, why, alternatives, interview angle)

After completing all tasks, confirm: "Phase 2-C complete. Changed files: [list]. New files: [list]."
```

---

### PHASE 2 — Agent D: Model Artifacts to GCS + Secret Manager wiring

```
You are a senior MLOps engineer working on the Sports Analytics Intelligence Platform.

CONTEXT: Read these files first before doing anything:
- docs/decisions/decision-log.md
- docs/decisions/hybrid-orchestration-plan-2026-03-19.md
- backend/src/models/artifact_store.py (current local file-based store)
- backend/src/models/predictor.py (current model loading)
- backend/src/models/trainer.py (current training pipeline)

YOUR GOAL: Make model artifacts GCS-backed and wire Secret Manager for all credentials.

YOUR TASKS:

TASK 1 — Update backend/src/models/artifact_store.py to write to GCS:
Add a new function upload_artifact_to_gcs(local_path, model_name, timestamp, bucket_name):
- Uses google-cloud-storage client
- Uploads the local file to gs://{bucket_name}/models/{model_name}/{timestamp}/{filename}
- Returns the GCS URI (gs://...)
- If GCS_MODELS_BUCKET env var is not set → skip GCS upload, log WARNING, continue (local-only mode for dev)

Modify save_artifact() to call upload_artifact_to_gcs() after the local joblib.dump().
This means models are saved BOTH locally (for immediate loading) AND in GCS (for persistence).

Add a function download_artifact_from_gcs(model_name, bucket_name, local_dir):
- Lists objects under gs://{bucket}/models/{model_name}/
- Finds the most recent timestamp prefix
- Downloads to local_dir
- Used at startup if no local model file found

TASK 2 — Update backend/src/models/predictor.py model loading:
In _load_latest_models(), add a fallback sequence:
1. Try to load from local MODEL_DIR (fastest — already there from last run)
2. If not found locally: call download_artifact_from_gcs() → then load
3. If GCS also fails: log ERROR and raise (don't silently serve no model)
This makes the predictor resilient to container restarts (models survive in GCS even if local disk is wiped).

TASK 3 — Add Secret Manager integration in backend/src/config.py:
Add a function load_secret_from_manager(secret_id, project_id):
- Uses google-cloud-secret-manager client
- Fetches the latest version of the secret
- Returns the decoded value
- If GOOGLE_CLOUD_PROJECT is not set → return None (local dev mode, fall back to env var)

Update config.py to load sensitive values with this pattern:
def get_config_value(env_var, secret_id=None):
    value = os.getenv(env_var)
    if not value and secret_id and os.getenv("GOOGLE_CLOUD_PROJECT"):
        value = load_secret_from_manager(secret_id, os.getenv("GOOGLE_CLOUD_PROJECT"))
    return value

Apply this to: DATABASE_URL, GEMINI_API_KEY, LANGFUSE_SECRET_KEY, PREFECT_API_KEY.

TASK 4 — Create infra/secret-manager/secrets-list.md:
Document all secrets that need to be created in Secret Manager:
| Secret ID | Value | Used by |
|-----------|-------|---------|
| DATABASE_URL | postgresql+psycopg2://... | API, trainer, predictor |
| GEMINI_API_KEY | AIza... | RAG, chat |
| LANGFUSE_SECRET_KEY | sk-lf-... | Observability |
| PREFECT_API_KEY | pnu_... | Prefect agent |
| GRAFANA_ADMIN_PASSWORD | (generated) | Grafana |

TASK 5 — Update docs/decisions/decision-log.md:
Decision: GCS-backed model artifacts (what, alternatives, why GCS, trade-offs, interview angle on stateless containers)
Decision: Secret Manager over .env files in production (what, why, alternatives, trade-offs)

After completing all tasks, confirm: "Phase 2-D complete. Changed files: [list]. New files: [list]."
```

---

## PHASE 3 — Prefect Feature Engineering (fire all 3 agents simultaneously after Phase 2-A completes)

---

### PHASE 3 — Agent A: Prefect Agent Deployment + Pub/Sub Trigger

```
You are a senior MLOps / platform engineer working on the Sports Analytics Intelligence Platform.

CONTEXT: Read these files first before doing anything:
- docs/decisions/decision-log.md
- docs/decisions/hybrid-orchestration-plan-2026-03-19.md
- backend/scheduler.py (the feature engineering job you're replacing)
- backend/src/data/feature_store.py

YOUR GOAL: Set up the Prefect agent infrastructure that will receive Pub/Sub messages from the Cloud Run ingestion job and trigger Prefect flows.

YOUR TASKS:

TASK 1 — Create backend/pipeline/prefect_agent.py (the always-on Prefect worker):
This is a Python script that:
- Connects to Prefect Cloud using PREFECT_API_KEY and PREFECT_API_URL from env/Secret Manager
- Starts a Prefect worker pool named "cloud-run-pool" of type "process"
- Listens for flow run submissions
- This script runs as a Cloud Run Service (always-on, min-instances=1) — NOT a Cloud Run Job
The actual startup command: prefect worker start --pool cloud-run-pool

Create a backend/Dockerfile.prefect-agent:
FROM prefecthq/prefect:2-python3.11
WORKDIR /app
COPY requirements-prod.txt .
RUN pip install -r requirements-prod.txt
COPY src/ ./src/
COPY pipeline/ ./pipeline/
ENV PREFECT_API_URL=""
ENV PREFECT_API_KEY=""
CMD ["prefect", "worker", "start", "--pool", "cloud-run-pool"]

TASK 2 — Create backend/pipeline/pubsub_trigger.py (Pub/Sub → Prefect bridge):
This is a Cloud Run Service (NOT a job) that:
- Exposes a POST /trigger endpoint (FastAPI, tiny app)
- Cloud Pub/Sub push subscription sends messages to this endpoint
- The endpoint parses the Pub/Sub message (base64-decode the data field)
- If message.status == "success" and message.rows_ingested.matches > 0:
  → Creates a Prefect flow run using the Prefect Python client:
    client.create_flow_run_from_deployment(deployment_name="feature-engineering-pipeline/production")
  → Passes the run_id and gcs_prefix as parameters to the flow
- If message.status == "failed": log and skip (don't trigger features on failed ingestion)
- Returns HTTP 200 (Pub/Sub requires 200 to acknowledge, otherwise it retries)
- Returns HTTP 200 even on internal errors (to prevent Pub/Sub retry storm) — but log the error

TASK 3 — Create infra/pubsub/push-subscription.md:
Document the Pub/Sub push subscription configuration:
- Topic: pipeline-events
- Subscription: prefect-feature-trigger
- Push endpoint: https://gamethread-pubsub-trigger-{hash}.run.app/trigger
- Ack deadline: 60 seconds
- Retry policy: exponential backoff, max 5 retries

TASK 4 — Update docs/decisions/decision-log.md:
Decision: Pub/Sub push subscription as pipeline handoff (what, push vs pull, why push for low-latency triggering, trade-offs)
Decision: Dedicated Pub/Sub → Prefect bridge service (what, why not trigger Prefect directly from Cloud Run Job)

Update docs/learning-notes/infrastructure/ with pubsub-and-prefect-integration.md covering:
What is Pub/Sub push vs pull? Why is a push subscription better for triggering real-time workflows? What is a Prefect worker pool? Interview questions.

After completing all tasks, confirm: "Phase 3-A complete. Changed files: [list]. New files: [list]."
```

---

### PHASE 3 — Agent B: Convert feature_store.py to Prefect Flow

```
You are a senior data engineer working on the Sports Analytics Intelligence Platform.

CONTEXT: Read these files first before doing anything:
- docs/decisions/decision-log.md
- docs/decisions/hybrid-orchestration-plan-2026-03-19.md
- backend/src/data/feature_store.py (THE file you're converting to Prefect)
- backend/src/data/audit_store.py (understand audit writing)

YOUR GOAL: Convert feature_store.py into a Prefect flow with @task decorators, retry policies, and conditional branching. The existing feature computation logic must NOT change — only the orchestration wrapper changes.

YOUR TASKS:

TASK 1 — Create backend/flows/feature_engineering_flow.py (the Prefect flow):

The flow structure must be:

```python
from prefect import flow, task
from prefect.tasks import exponential_backoff
import pandas as pd
from typing import Dict, Optional

@task(
    name="Validate Raw Ingestion Data",
    retries=2,
    retry_delay_seconds=30,
    description="Asserts row counts, null rates, and date freshness before computing features"
)
def validate_raw_data(engine, seasons: list[str], run_id: str) -> Dict:
    # Call the validate_raw_data() function from feature_store.py (Phase 1-A)
    # Return {"matches": N, "team_stats": N, "valid": True}
    ...

@task(
    name="Compute Rolling Features",
    retries=3,
    retry_delay_seconds=exponential_backoff(backoff_factor=60),
    description="Computes win_pct, point_diff, ratings (L5/L10 rolling windows)"
)
def compute_rolling_features(engine, seasons: list[str], validated_counts: Dict) -> int:
    # Call the relevant rolling feature function from feature_store.py
    # Return number of rows written
    ...

@task(
    name="Compute H2H Features",
    retries=3,
    retry_delay_seconds=exponential_backoff(backoff_factor=60),
    description="Computes head-to-head win%, margin, data_available flag"
)
def compute_h2h_features(engine, seasons: list[str]) -> int:
    ...

@task(
    name="Compute Rest and Fatigue Features",
    retries=2,
    retry_delay_seconds=60,
    description="Computes days_rest, is_back_to_back, current_streak"
)
def compute_rest_features(engine, seasons: list[str]) -> int:
    ...

@task(
    name="Validate Feature Output",
    retries=1,
    description="Asserts feature rows match raw rows, no NaN in critical columns"
)
def validate_feature_output(engine, seasons: list[str], expected_count: int) -> bool:
    ...

@task(
    name="Write Pipeline Audit",
    description="Records pipeline run status, counts, and elapsed time to pipeline_audit table"
)
def write_pipeline_audit(engine, run_id: str, status: str, details: Dict) -> None:
    ...

@task(
    name="Trigger Prediction Refresh",
    retries=3,
    retry_delay_seconds=30,
    description="POSTs to API to refresh predictions for newly featured games"
)
def trigger_prediction_refresh(api_base_url: str, features_written: int) -> None:
    ...

@flow(
    name="feature-engineering-pipeline",
    description="Reads from Cloud SQL raw tables, computes match_features, writes audit"
)
def feature_engineering_pipeline(
    run_id: str,
    gcs_prefix: str,
    seasons: list[str] = ["2025-26"]
) -> None:
    import os
    from sqlalchemy import create_engine
    engine = create_engine(os.getenv("DATABASE_URL"))

    # Validate first — if this fails, Prefect marks downstream as skipped
    validated = validate_raw_data(engine, seasons, run_id)

    # Run feature computation tasks (these can run in parallel in future)
    rolling_count = compute_rolling_features(engine, seasons, validated)
    h2h_count = compute_h2h_features(engine, seasons)
    rest_count = compute_rest_features(engine, seasons)

    # Validate output
    is_valid = validate_feature_output(engine, seasons, validated["matches"])

    # Audit
    write_pipeline_audit(engine, run_id, "success", {
        "rolling_rows": rolling_count,
        "h2h_rows": h2h_count,
        "rest_rows": rest_count,
        "validation_passed": is_valid
    })

    # Trigger API refresh only if features were written
    if rolling_count > 0:
        trigger_prediction_refresh(os.getenv("API_BASE_URL", "http://localhost:8000"), rolling_count)

if __name__ == "__main__":
    feature_engineering_pipeline(run_id="manual", gcs_prefix="", seasons=["2025-26"])
```

TASK 2 — Create backend/flows/deploy_flow.py (Prefect deployment registration):
```python
from prefect import flow
from flows.feature_engineering_flow import feature_engineering_pipeline
from prefect.deployments import Deployment
from prefect.infrastructure import Process

deployment = Deployment.build_from_flow(
    flow=feature_engineering_pipeline,
    name="production",
    work_pool_name="cloud-run-pool",
    tags=["production", "nba", "features"],
    parameters={"seasons": ["2025-26"]},
)

if __name__ == "__main__":
    deployment.apply()
```

TASK 3 — Add Prefect dependencies to requirements-prod.txt:
Add: prefect==2.20.0, prefect-gcp==0.6.0

TASK 4 — Update docs/learning-notes/infrastructure/ with prefect-flow-design.md covering:
What is Prefect @flow vs @task? What is exponential_backoff and when to use it? How does task-level retry differ from job-level retry? What is a Prefect deployment? How does Prefect compare to Airflow DAGs? Interview questions.

Update docs/decisions/decision-log.md:
Decision: Prefect for feature engineering orchestration (what, alternatives, why Prefect over raw Cloud Run Job, trade-offs, interview angle)

After completing all tasks, confirm: "Phase 3-B complete. Changed files: [list]. New files: [list]."
```

---

### PHASE 3 — Agent C: Prefect Flow Validation Tasks + Audit

```
You are a senior data quality engineer working on the Sports Analytics Intelligence Platform.

CONTEXT: Read these files first before doing anything:
- docs/decisions/decision-log.md
- backend/flows/feature_engineering_flow.py (created by Phase 3-B agent — read this carefully)
- backend/src/data/audit_store.py
- backend/src/data/validators.py (existing validators — understand what's already there)

YOUR GOAL: Strengthen the validation and audit tasks in the Prefect flow. Add data contract checking between the ingestion output and the feature input.

YOUR TASKS:

TASK 1 — Create backend/flows/data_contracts.py:
Define Python dataclasses representing data contracts:
```python
@dataclass
class IngestionContract:
    """What the ingestion job guarantees to the feature pipeline."""
    min_matches_per_day: int = 1
    max_null_rate: float = 0.15
    max_data_age_days: int = 7
    required_columns_matches: list = field(default_factory=lambda: ["game_id", "game_date", "home_team_id", "away_team_id", "winner_team_id"])

@dataclass
class FeatureContract:
    """What the feature pipeline guarantees to the prediction pipeline."""
    required_feature_columns: list = field(default_factory=lambda: [...all 25 feature columns...])
    max_null_rate_features: float = 0.05  # Tighter than raw data
    min_feature_rows_per_match: int = 2   # One per team
```
Use these contracts inside the validate_raw_data and validate_feature_output tasks.

TASK 2 — Add dead-letter handling to the Prefect flow:
In backend/flows/feature_engineering_flow.py, wrap the main flow body in a try/except:
- If ANY unrecoverable error occurs: write to the pipeline_audit table with status="failed" and full error traceback
- Publish a failure event to Pub/Sub topic: pipeline-events with {"status": "feature_engineering_failed", "run_id": ..., "error": ...}
- This allows Cloud Monitoring to alert on feature engineering failures independently of ingestion failures

TASK 3 — Create backend/flows/flow_tests.py (local Prefect flow tests):
Write unit tests for each @task using pytest:
- test_validate_raw_data_passes_with_good_data()
- test_validate_raw_data_fails_with_stale_data()
- test_validate_raw_data_fails_with_low_row_count()
- test_validate_feature_output_detects_null_columns()
Use mocked SQLAlchemy engines (use unittest.mock.MagicMock or pytest fixtures with in-memory SQLite).

TASK 4 — Update docs/learning-notes/data-layer/ with a new file data-contracts-and-validation.md covering:
What is a data contract? Why do you need one between ingestion and feature engineering? What is a dead-letter pattern? How do you test Prefect tasks locally? Interview questions.

After completing all tasks, confirm: "Phase 3-C complete. Changed files: [list]. New files: [list]."
```

---

## PHASE 4 — Vertex AI MLOps (fire all 3 agents simultaneously after Phase 2-B and Phase 3 complete)

---

### PHASE 4 — Agent A: Vertex AI Experiments Integration

```
You are a senior MLOps engineer working on the Sports Analytics Intelligence Platform.

CONTEXT: Read these files first before doing anything:
- docs/decisions/decision-log.md
- docs/decisions/hybrid-orchestration-plan-2026-03-19.md
- backend/src/models/trainer.py
- backend/src/models/artifact_store.py

YOUR GOAL: Replace the training_metadata JSON files with Vertex AI Experiments tracking.

YOUR TASKS:

TASK 1 — Update backend/src/models/trainer.py to log to Vertex AI Experiments:
Add a new function log_training_run_to_vertex(results, metadata, timestamp):
- Initializes aiplatform with project + location from env vars
- Creates/updates experiment named "nba-game-predictions"
- Starts a run named f"run-{timestamp}-{season}"
- Logs params: n_estimators, max_depth, learning_rate, season, cv_splits, feature_count
- Logs metrics: cv_accuracy, cv_auc, brier_score, log_loss, training_games, validation_games
- Logs per-model metrics: xgboost.cv_accuracy, lightgbm.cv_accuracy, logistic_regression.cv_accuracy
- Logs calibration metrics: xgboost.raw_brier, xgboost.calibrated_brier (improvement)
- If GOOGLE_CLOUD_PROJECT not set → skip silently (local dev mode)
Call this at the end of run_training_pipeline().

TASK 2 — Add google-cloud-aiplatform to requirements-prod.txt:
google-cloud-aiplatform==1.70.0

TASK 3 — Create infra/vertex-ai/experiments-setup.md:
Document how to view experiments in GCP console.
Document the experiment naming convention and what each metric means.
Include: how to compare runs, how to identify the best model, how to set up a champion/challenger evaluation.

TASK 4 — Update docs/decisions/decision-log.md:
Decision: Vertex AI Experiments over MLflow or W&B (what, alternatives: MLflow self-hosted, W&B free tier; why Vertex AI for GCP-native portfolio; trade-offs; interview angle)

Update docs/learning-notes/mlops/ with vertex-ai-experiments.md covering:
What is experiment tracking? Why is it essential for production ML? What do you track? What is the difference between params and metrics? What is a champion/challenger model? Interview questions.

After completing all tasks, confirm: "Phase 4-A complete. Changed files: [list]. New files: [list]."
```

---

### PHASE 4 — Agent B: Vertex AI Model Registry

```
You are a senior MLOps engineer working on the Sports Analytics Intelligence Platform.

CONTEXT: Read these files first before doing anything:
- docs/decisions/decision-log.md
- docs/decisions/hybrid-orchestration-plan-2026-03-19.md
- backend/src/models/artifact_store.py
- backend/src/models/predictor.py

YOUR GOAL: Register trained models in Vertex AI Model Registry (in addition to GCS artifact storage) and update the predictor to load by registry alias.

YOUR TASKS:

TASK 1 — Update backend/src/models/artifact_store.py to register in Vertex AI:
Add a function register_model_in_vertex(model_name, gcs_artifact_uri, metrics, project_id, location):
- Calls aiplatform.Model.upload() with the GCS artifact URI
- Sets display_name, description, labels (season, accuracy, brier_score)
- Returns the registered model resource name
- If GOOGLE_CLOUD_PROJECT not set → skip, return None

Add function set_model_alias(model_resource_name, alias, project_id):
- Calls the Vertex AI client to set an alias (e.g., "production", "staging", "champion")
- Use Model.add_version_aliases([alias])

TASK 2 — Update backend/src/models/predictor.py to support loading by alias:
Add logic: if VERTEX_MODEL_ALIAS and VERTEX_MODEL_NAME env vars are set:
  → Query Vertex AI Model Registry for the model version with alias=VERTEX_MODEL_ALIAS
  → Get the GCS artifact URI for that version
  → Download from GCS if not already in local MODEL_DIR
  → Load the model
Add .env.example entries:
VERTEX_MODEL_NAME=nba-ensemble
VERTEX_MODEL_ALIAS=production
VERTEX_MODEL_LOCATION=us-central1

TASK 3 — Create infra/vertex-ai/model-registry-setup.md:
Document the model naming convention, alias strategy (production, staging, previous), rollback procedure (reassign production alias to previous version), and how to view model lineage.

TASK 4 — Update docs/decisions/decision-log.md:
Decision: Vertex AI Model Registry + alias-based serving (what, why aliases beat version numbers for rollback, trade-offs, interview angle on zero-downtime rollback)

Update docs/learning-notes/mlops/ with model-registry-and-aliases.md covering:
What is a model registry? What is a model alias vs version number? How does alias-based serving enable zero-downtime rollback? Interview questions.

After completing all tasks, confirm: "Phase 4-B complete. Changed files: [list]. New files: [list]."
```

---

### PHASE 4 — Agent C: Vertex AI Retrain Pipeline

```
You are a senior MLOps engineer working on the Sports Analytics Intelligence Platform.

CONTEXT: Read these files first before doing anything:
- docs/decisions/decision-log.md
- docs/decisions/hybrid-orchestration-plan-2026-03-19.md
- backend/src/mlops/retrain_policy.py
- backend/src/mlops/retrain_worker.py
- backend/src/models/trainer.py

YOUR GOAL: Replace the retrain_worker.py polling loop with a Vertex AI Pipeline (Kubeflow-based) that has step-level governance.

YOUR TASKS:

TASK 1 — Create backend/pipelines/retrain_pipeline.py (Vertex AI Pipeline definition):
Use the Kubeflow Pipelines SDK (kfp) to define a 6-step pipeline:

```python
from kfp import dsl
from kfp.v2 import compiler

@dsl.component(base_image="python:3.11-slim", packages_to_install=["google-cloud-aiplatform", "sqlalchemy", "psycopg2-binary", "pandas", "numpy", "xgboost", "lightgbm", "scikit-learn", "joblib"])
def load_and_validate_data(season: str, database_url: str, min_games: int = 50) -> str:
    # Returns GCS URI of validated dataset
    ...

@dsl.component(...)
def train_ensemble(dataset_uri: str, season: str, database_url: str) -> dict:
    # Returns: {"gcs_model_uri": "...", "cv_accuracy": 0.634, "brier_score": 0.221}
    ...

@dsl.component(...)
def evaluate_vs_champion(
    new_model_metrics: dict,
    vertex_model_name: str,
    project_id: str,
    min_improvement: float = 0.01
) -> bool:
    # Returns True if new model beats champion by min_improvement
    ...

@dsl.component(...)
def register_model(
    gcs_model_uri: str,
    new_model_metrics: dict,
    project_id: str,
    should_promote: bool
) -> str:
    # Registers in Vertex AI Model Registry
    # Returns model resource name
    ...

@dsl.component(...)
def promote_to_production(model_resource_name: str, project_id: str, should_promote: bool):
    # Sets 'production' alias if should_promote is True
    # Sends Cloud Monitoring custom metric: model_promoted=1
    ...

@dsl.component(...)
def write_retrain_audit(
    run_id: str,
    new_metrics: dict,
    promoted: bool,
    database_url: str,
    trigger_reason: str
):
    # Writes to retrain_jobs table with full details
    ...

@dsl.pipeline(name="nba-retrain-pipeline", description="Champion vs challenger retrain with governance")
def retrain_pipeline(
    season: str = "2025-26",
    trigger_reason: str = "scheduled",
    database_url: str = "",
    project_id: str = "",
    min_improvement: float = 0.01,
):
    with dsl.ExitHandler(write_retrain_audit(...)):
        dataset_task = load_and_validate_data(season, database_url)
        train_task = train_ensemble(dataset_task.output, season, database_url)
        eval_task = evaluate_vs_champion(train_task.output, "nba-ensemble", project_id, min_improvement)
        register_task = register_model(train_task.outputs["gcs_model_uri"], train_task.output, project_id, eval_task.output)
        promote_task = promote_to_production(register_task.output, project_id, eval_task.output)
```

TASK 2 — Create backend/pipelines/compile_pipeline.py:
Compiles the pipeline to retrain_pipeline.json (Vertex AI format) using kfp.compiler.Compiler().compile()

TASK 3 — Add a Cloud Scheduler trigger for weekly scheduled retrain:
Create infra/cloud-scheduler/retrain-trigger.yaml:
- Schedule: 0 3 * * 0 (03:00 UTC every Sunday)
- Target: Vertex AI Pipeline API
- Body: {"pipelineSpec": ..., "parameter_values": {"trigger_reason": "scheduled_weekly"}}

TASK 4 — Update retrain_policy.py to also trigger Vertex AI Pipeline:
The existing check_retrain_eligibility() function detects when retraining is needed.
Instead of writing to retrain_jobs and polling, have it submit a Vertex AI Pipeline run:
```python
from google.cloud import aiplatform
job = aiplatform.PipelineJob(
    display_name=f"retrain-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
    template_path="gs://gamethread-models/pipelines/retrain_pipeline.json",
    parameter_values={"season": "2025-26", "trigger_reason": trigger_reason},
)
job.submit()
```

Add kfp==2.7.0 and google-cloud-pipeline-components==2.15.0 to requirements-prod.txt.

TASK 5 — Update docs/decisions/decision-log.md:
Decision: Vertex AI Pipelines for retrain governance (what, alternatives: Prefect for retrain; why Vertex AI for step-level compute; trade-offs; interview angle on champion/challenger)

Update docs/learning-notes/mlops/ with vertex-ai-pipelines.md covering:
What is a Kubeflow Pipeline component? What is an ExitHandler? What is champion vs challenger testing? What is the minimum improvement threshold concept? How do you roll back a model on Vertex AI? Interview questions.

After completing all tasks, confirm: "Phase 4-C complete. Changed files: [list]. New files: [list]."
```

---

## PHASE 5 — Monitoring + Drift Detection (fire all 3 agents after Phase 4 completes)

---

### PHASE 5 — Agent A: Cloud Monitoring Custom Metrics + Alerting

```
You are a senior SRE / MLOps engineer working on the Sports Analytics Intelligence Platform.

CONTEXT: Read these files first before doing anything:
- docs/decisions/decision-log.md
- backend/src/mlops/monitoring.py
- backend/src/api/mlops_routes.py

YOUR GOAL: Replace Prometheus + self-hosted Grafana alerting with Cloud Monitoring custom metrics and alerting policies.

YOUR TASKS:

TASK 1 — Create backend/src/mlops/gcp_metrics.py:
A module that writes custom metrics to Cloud Monitoring:

```python
from google.cloud import monitoring_v3
import time

CUSTOM_METRICS = {
    "prediction_confidence": "custom.googleapis.com/model/prediction_confidence",
    "data_freshness_hours": "custom.googleapis.com/pipeline/data_freshness_hours",
    "model_accuracy": "custom.googleapis.com/model/accuracy_rolling",
    "feature_null_rate": "custom.googleapis.com/pipeline/feature_null_rate",
    "retrain_triggered": "custom.googleapis.com/mlops/retrain_triggered",
}

def write_metric(metric_type: str, value: float, labels: dict = {}, project_id: str = None):
    # Writes a single data point to Cloud Monitoring
    # If project_id not set → no-op (local dev)
    ...
```

Instrument these call sites:
- predictor.py: after each prediction, write prediction_confidence metric
- monitoring.py: after each snapshot, write data_freshness_hours and model_accuracy
- feature_store.py: after feature validation, write feature_null_rate

TASK 2 — Create infra/cloud-monitoring/alert-policies.md:
Document the 5 alerting policies to create in GCP console:
1. Data freshness > 48 hours for 30 minutes → email: "Pipeline may have failed"
2. Prediction error rate > 5% for 10 minutes → email + SMS: "API serving errors"
3. Model accuracy < 0.55 for 3 consecutive days → email: "Consider manual retrain"
4. API p95 latency > 5 seconds for 5 minutes → email: "API performance degraded"
5. Prediction confidence mean < 0.55 for 1 hour → email: "Possible distribution shift"

TASK 3 — Add google-cloud-monitoring to requirements-prod.txt:
google-cloud-monitoring==2.22.0

TASK 4 — Update docs/learning-notes/mlops/ with cloud-monitoring-and-alerting.md.

After completing, confirm: "Phase 5-A complete."
```

---

### PHASE 5 — Agent B: Looker Studio Dashboards (Documentation)

```
You are a senior data analyst working on the Sports Analytics Intelligence Platform.

CONTEXT: Read docs/decisions/decision-log.md and docs/architecture/system-design.md.

YOUR GOAL: Document the 4 Looker Studio dashboards to build (Looker Studio is a web UI tool, not code — so your job is to document the dashboard specs so you can build them manually).

YOUR TASKS:

TASK 1 — Create docs/architecture/looker-studio-dashboards.md:
Document the spec for each of 4 dashboards:

Dashboard 1: Prediction Performance
- Data source: Cloud SQL → predictions table + matches table
- Charts: accuracy time series (rolling 30 days), Brier score time series, calibration curve (predicted prob vs actual win rate), prediction volume by confidence bucket
- Filters: season selector, date range
- KPIs: overall accuracy, last 7 days accuracy, Brier score, total predictions

Dashboard 2: Bankroll & Betting
- Data source: Cloud SQL → bets table
- Charts: cumulative P&L line chart, stake distribution histogram, ROI by confidence tier, win rate by stake size
- KPIs: total P&L, total bets, ROI %, current bankroll

Dashboard 3: Pipeline Health
- Data source: Cloud SQL → pipeline_audit, intelligence_audit tables
- Charts: ingestion run status timeline (success/fail/warning), rows ingested per day, feature computation elapsed time trend, RAG refresh freshness
- Filters: module selector (ingestion, features, rag)
- KPIs: last ingestion status, last feature run, data freshness hours

Dashboard 4: MLOps
- Data source: Cloud SQL → mlops_monitoring_snapshot + retrain_jobs tables; Vertex AI Experiments API (BigQuery export)
- Charts: model accuracy over time, Brier score over time, retrain history (trigger reason + accuracy delta), model version timeline
- KPIs: current model accuracy, last retrain date, total retrain count, accuracy improvement per retrain

TASK 2 — Create infra/looker-studio/setup-guide.md:
Document how to connect Looker Studio to Cloud SQL (via the PostgreSQL connector), how to set up scheduled data refresh, and how to share dashboards.

After completing, confirm: "Phase 5-B complete."
```

---

### PHASE 5 — Agent C: KL Divergence Drift Detection

```
You are a senior ML scientist working on the Sports Analytics Intelligence Platform.

CONTEXT: Read these files first before doing anything:
- docs/decisions/decision-log.md
- backend/src/mlops/monitoring.py
- backend/src/data/prediction_store.py

YOUR GOAL: Add prediction distribution drift detection using KL divergence to the existing MLOps monitoring stack.

YOUR TASKS:

TASK 1 — Add KL divergence computation to backend/src/mlops/monitoring.py:
Add a function compute_prediction_drift(engine, baseline_days=30, live_days=7):
- Baseline: distribution of prediction probabilities from 30 days ago (training-time distribution proxy)
- Live: distribution of prediction probabilities from the last 7 days
- Both distributions: histogram with 10 bins [0.0, 0.1, 0.2, ..., 1.0]
- Compute symmetric KL divergence: (KL(P||Q) + KL(Q||P)) / 2
- Return: {"kl_divergence": float, "baseline_mean": float, "live_mean": float, "drift_detected": bool}
- drift_detected = True if kl_divergence > 0.1 (threshold — document why)
- Write the result to mlops_monitoring_snapshot as a new column: feature_drift_score

Add a database migration (Alembic) to add the feature_drift_score column to mlops_monitoring_snapshot.

TASK 2 — Add drift to the MLOps API endpoint:
In backend/src/api/mlops_routes.py, update the GET /api/v1/mlops/monitoring response to include:
- feature_drift_score: the latest KL divergence value
- drift_detected: boolean
- drift_baseline_period: "30 days"
- drift_live_period: "7 days"

TASK 3 — Write a learning note in docs/learning-notes/mlops/ with drift-detection.md covering:
What is covariate shift vs concept drift? What is KL divergence (intuition, not math)? Why is 0.1 a reasonable threshold? What do you do when drift is detected? How does this differ from accuracy monitoring? Interview questions.

Update docs/decisions/decision-log.md:
Decision: KL divergence for distribution drift (what, alternatives: PSI Population Stability Index, MMD Maximum Mean Discrepancy; why KL for simplicity; trade-offs; interview angle)

After completing all tasks, confirm: "Phase 5-C complete."
```

---

## How to Fire Agents in Parallel

### Phase 1 (fire simultaneously):
```
spawn agent: Phase 1 - Agent A (Imputation + Validation)
spawn agent: Phase 1 - Agent B (ONNX + Version Metadata)
spawn agent: Phase 1 - Agent C (Dockerfile + Requirements)
wait for all 3 to complete
```

### Phase 2 (fire simultaneously after Phase 1 done):
```
spawn agent: Phase 2 - Agent A (Cloud Run Ingestion Job + GCS + Pub/Sub)
spawn agent: Phase 2 - Agent B (API Cloud Run Deployment)
spawn agent: Phase 2 - Agent C (RAG Refresh Cloud Run Job)
spawn agent: Phase 2 - Agent D (Model Artifacts to GCS + Secret Manager)
wait for all 4 to complete
```

### Phase 3 (fire simultaneously after Phase 2-A completes):
```
spawn agent: Phase 3 - Agent A (Prefect Agent + Pub/Sub Trigger)
spawn agent: Phase 3 - Agent B (feature_store.py → Prefect Flow)
spawn agent: Phase 3 - Agent C (Validation Tasks + Data Contracts)
wait for all 3 to complete
```

### Phase 4 (fire simultaneously after Phase 2-B and Phase 3 complete):
```
spawn agent: Phase 4 - Agent A (Vertex AI Experiments)
spawn agent: Phase 4 - Agent B (Vertex AI Model Registry)
spawn agent: Phase 4 - Agent C (Vertex AI Retrain Pipeline)
wait for all 3 to complete
```

### Phase 5 (fire simultaneously after Phase 4 complete):
```
spawn agent: Phase 5 - Agent A (Cloud Monitoring Metrics + Alerting)
spawn agent: Phase 5 - Agent B (Looker Studio Dashboard Specs)
spawn agent: Phase 5 - Agent C (KL Divergence Drift Detection)
wait for all 3 to complete
```

---

## Total Agent Count: 14 agents across 5 phases
## Estimated Wall-Clock Time (with parallel execution):
- Phase 1: ~45 minutes (3 agents × 15 min each, parallel)
- Phase 2: ~60 minutes (4 agents × 15-20 min each, parallel)
- Phase 3: ~45 minutes (3 agents × 15 min each, parallel)
- Phase 4: ~60 minutes (3 agents × 20 min each, parallel)
- Phase 5: ~30 minutes (3 agents × 10 min each, parallel)
- **Total: ~4 hours wall-clock vs ~14 hours sequential**
