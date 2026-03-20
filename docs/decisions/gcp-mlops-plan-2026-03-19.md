# GCP + Orchestration + MLOps Updated Plan
**Date:** 2026-03-19
**Supersedes:** mlops-audit-2026-03-19.md (adds GCP migration + orchestration + Vertex AI)

---

## Root Problem: The Scheduler Anti-Pattern

`scheduler.py` runs APScheduler as a BackgroundScheduler inside the FastAPI process.
This creates three production risks:

1. **Lifecycle coupling** — if the API crashes, the data pipeline stops.
2. **Duplicate jobs** — if you scale to 2 API containers, you get 2 schedulers firing duplicate ingestion runs.
3. **No visibility** — there is no DAG UI, no retry UI, no step-level audit outside `pipeline_audit` table.

Fix: decouple the pipeline from the API using Cloud Run Jobs + Cloud Scheduler.

---

## GCP Service Mapping

| Current | Problem | GCP Replacement |
|---------|---------|----------------|
| APScheduler in FastAPI | Coupled to API, duplicate on scale | Cloud Scheduler + Cloud Run Jobs |
| Local `backend/models/` | Lost on container rebuild | Cloud Storage (GCS) |
| Home-grown artifact_store.py | No experiment UI, no lineage | Vertex AI Model Registry |
| training_metadata JSON files | Unstructured, no comparison | Vertex AI Experiments |
| Grafana + Prometheus (self-hosted) | You manage infra | Cloud Monitoring + Looker Studio |
| docker-compose Postgres | Unmanaged, no auto-backup | Cloud SQL (Postgres 16) |
| Local ChromaDB embedded | Not durable across rebuilds | Cloud Run (ChromaDB container) |
| Manual retrain via API | No DAG, no rollback | Vertex AI Pipelines |
| GitHub Actions (test only) | No deploy step | Cloud Build + Artifact Registry |

---

## Orchestration Tool Decision (A vs B vs C)

### Option A: Cloud Scheduler + Cloud Run Jobs ✅ RECOMMENDED NOW
- GCP-native, zero additional infrastructure
- Serverless: spin up → execute → terminate
- Cost: ~$1/month for 3 jobs × 10 min/day
- Migration effort: 1-2 days (extract pipeline functions into a separate Docker image)
- Interview angle: "Decoupled pipeline from API. Each job is independently deployable and retry-able."

### Option B: Cloud Composer (Managed Airflow) — NOT YET
- Full DAG UI, dependency management, backfill, SLA monitoring
- Cost: $300-500/month minimum (runs a dedicated GKE cluster)
- Right choice when: team product, multiple sports leagues, complex multi-step DAGs
- Know this for interviews but don't use it for a solo portfolio

### Option C: Prefect (Open Source) ✅ UPGRADE IN PHASE 4
- Python-native: add @flow and @task decorators to existing functions
- Free cloud tier (Prefect Cloud), or self-host on Cloud Run
- Adds: task-level retry, inter-task data passing, flow state UI
- Migration: 1-2 days (existing functions are already well-structured)

**Recommendation:** Start with Cloud Scheduler + Cloud Run Jobs. Add Prefect when the pipeline grows to multiple interdependent DAGs.

---

## GCP Project Structure

```
Project: sports-analytics-intelligence
├── Cloud SQL (Postgres 16, db-f1-micro)
│   └── Managed DB with auto-backups, point-in-time recovery
├── Cloud Storage
│   ├── gs://gamethread-models/       Model artifacts (replaces backend/models/)
│   ├── gs://gamethread-data/         Raw data exports (optional)
│   └── gs://gamethread-chroma/       ChromaDB snapshots
├── Artifact Registry
│   └── {region}-docker.pkg.dev/gamethread/api  Docker images
├── Cloud Run Services
│   ├── gamethread-api (always-on, min-instances=1)
│   └── gamethread-chroma (always-on, replaces embedded ChromaDB)
├── Cloud Run Jobs
│   ├── job-nba-ingestion             Daily raw data + features
│   └── job-rag-refresh               4× daily vector store
├── Cloud Scheduler
│   ├── trigger-ingestion (06:30 UTC)
│   └── trigger-rag-{00,06,12,18} UTC
├── Secret Manager
│   └── GEMINI_API_KEY, DB_PASSWORD, LANGFUSE_KEY, etc.
├── Vertex AI
│   ├── Experiments (training run comparison)
│   ├── Model Registry (versioned artifacts + lineage)
│   └── Pipelines (retrain DAG with step-level governance)
├── Cloud Monitoring
│   ├── Cloud Run metrics (auto: latency, error rate, instance count)
│   ├── Custom metrics (prediction confidence, data freshness)
│   └── Alerting policies → email/SMS
└── Cloud Build
    └── CI/CD: test → build image → push to Artifact Registry → deploy to Cloud Run
```

---

## Phase 1 — Core ML Stability (1-2 weeks) [UNCHANGED]

| Task | Action | Why |
|------|--------|-----|
| 1.1 | Domain-aware imputation (H2H → 0.5, not 0.0) | fillna(0) is domain-wrong |
| 1.2 | Data validation gate before feature computation | Catch partial NBA API responses |
| 1.3 | ONNX export for XGBoost + LightGBM | 2-3x inference speedup |
| 1.4 | Library version metadata in training artifacts | Prevent deserialization failures |
| 1.5 | Model warm-up call at startup | Eliminate cold-start latency |

---

## Phase 2 — API + GCP Foundation (2-3 weeks)

| Task | Action | Why |
|------|--------|-----|
| 2.1 | Fix Dockerfile: remove --reload, add Gunicorn | Most impactful single change |
| 2.2 | Provision GCP project (Cloud SQL, GCS, Artifact Registry) | Infrastructure foundation |
| 2.3 | Migrate secrets to Secret Manager | Eliminate .env files from servers |
| 2.4 | Move model artifacts to GCS (gs://gamethread-models/) | Stateless API containers |
| 2.5 | Extract scheduler into Cloud Run Jobs + Cloud Scheduler | Decouple pipeline from API |
| 2.6 | Set up Cloud Build CI/CD (test → build → push → deploy) | Automated deployments |
| 2.7 | Containerize ChromaDB as separate Cloud Run service | Durable vector store |
| 2.8 | Deploy API to Cloud Run (min-instances=1, 2 Gunicorn workers) | Managed serving |

### Cloud Run Job Architecture

Each pipeline job is a separate lightweight Docker image:

```
Dockerfile.pipeline:
  FROM python:3.11-slim
  RUN pip install -r requirements-pipeline.txt  # No FastAPI, no SHAP, no frontend
  COPY backend/src ./src
  COPY backend/run_pipeline.py .
  CMD ["python", "run_pipeline.py"]
```

Cloud Scheduler sends an HTTP POST to the Cloud Run Jobs API at cron time.
Cloud Run spins up a container, runs the job, terminates it.
Cloud Logging captures all output. Failed jobs auto-retry with exponential backoff.

### requirements-pipeline.txt (separate from API)

```
sqlalchemy==2.0.36
psycopg2-binary==2.9.10
pandas==2.2.3
numpy==1.26.4
nba_api==1.5.2
apscheduler==3.11.2
google-generativeai==0.8.4
chromadb==0.5.23
langchain==0.2.16
google-cloud-storage==2.18.0  # For GCS artifact access
google-cloud-secret-manager==2.20.0
python-dotenv==1.0.1
```

Removes: fastapi, uvicorn, xgboost, lightgbm, shap, prometheus, jupyter, matplotlib, seaborn.
Result: ~400MB image vs ~1.5GB full-app image.

---

## Phase 3 — Vertex AI MLOps (3-4 weeks)

### 3.1 — Vertex AI Experiments (replace training_metadata JSON)

```python
from google.cloud import aiplatform

aiplatform.init(project="sports-analytics-intelligence", experiment="nba-predictions")

with aiplatform.start_run(run=f"run-{timestamp}"):
    aiplatform.log_params({
        "n_estimators": 200,
        "max_depth": 5,
        "season": "2025-26",
        "cv_splits": 5
    })
    aiplatform.log_metrics({
        "cv_accuracy": 0.634,
        "cv_auc": 0.681,
        "brier_score": 0.221,
        "training_games": 850
    })
```

You can now compare every training run side-by-side in the Vertex AI console.
Interview talking point: "Here are 7 runs across two seasons — I can show you exactly why we selected this model version."

### 3.2 — Vertex AI Model Registry (replace artifact_store.py)

```python
from google.cloud import aiplatform

# After training + saving to GCS
model = aiplatform.Model.upload(
    display_name=f"nba-ensemble-{timestamp}",
    artifact_uri="gs://gamethread-models/ensemble/20260319/",
    serving_container_image_uri="us-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-6:latest",
    labels={"season": "2025-26", "accuracy": "0.634"}
)

# Tag best model as production
model.add_version_aliases(["production"])
```

The API loads models by alias:
```python
model = aiplatform.Model("projects/.../models/nba-ensemble@production")
```

Rolling back becomes: reassign the `production` alias to the previous version. No redeployment needed.

### 3.3 — Vertex AI Pipelines (retrain DAG)

Replaces: retrain_policy.py → retrain_jobs table → retrain_worker.py polling loop

```
Pipeline: nba-retrain-pipeline
  │
  ├─ [Step 1: Load & Validate Data]
  │   Input: season, cutoff_date
  │   Output: validated dataset URI in GCS
  │   Retry: 2× with 5min delay
  │
  ├─ [Step 2: Train Ensemble]
  │   Input: dataset URI
  │   Output: model artifacts URI, metrics dict
  │   Compute: n1-standard-4 (4 CPU, 15GB RAM)
  │
  ├─ [Step 3: Evaluate vs Champion]
  │   If new_accuracy <= current_accuracy + 0.01: STOP (keep champion)
  │   If new_accuracy > current_accuracy + 0.01: CONTINUE
  │
  ├─ [Step 4: Register to Model Registry]
  │   Input: model artifacts URI, metrics
  │   Output: registered model version ID
  │
  ├─ [Step 5: Update production alias]
  │   Atomically move 'production' alias from old → new version
  │
  └─ [Step 6: Send notification]
      Cloud Monitoring alert → email: "New model promoted: accuracy 0.634 → 0.651"
```

Interview answer: "Promotion to production requires beating the champion by at least 1 percentage point. A human can see every step's output. I can replay any historical pipeline run. The pipeline is triggered automatically when accuracy drops below 0.55 for 3 consecutive days, or on a weekly schedule — whichever comes first."

### 3.4 — Cloud Monitoring + Alerting

Cloud Run auto-metrics (no code needed):
- Request count by endpoint
- Request latency (p50/p95/p99)
- Instance count (auto-scale events)
- Error rate (4xx/5xx)

Custom metrics (add to predictor.py):
- prediction_confidence (distribution)
- data_freshness_hours
- model_accuracy_rolling

Alert policies:
- Error rate > 5% for 5 minutes → email
- Data freshness > 48 hours → email (pipeline failed)
- Prediction confidence mean < 0.55 for 1 hour → email (drift signal)

### 3.5 — Looker Studio Dashboards (free, replaces self-hosted Grafana)

Connect Looker Studio to Cloud SQL directly.
Build 4 dashboards:
1. Prediction performance (accuracy, Brier, calibration curve)
2. Bankroll KPI (P&L, stake distribution, ROI)
3. Pipeline health (ingestion run history, feature row counts)
4. MLOps (model version history, retrain trigger log)

Dashboards are shareable public URLs — ideal for portfolio presentation.

---

## Phase 4 — Prefect Orchestration Upgrade (optional, 4-6 weeks)

### What Prefect adds over Cloud Scheduler + Cloud Run Jobs

| Feature | Cloud Scheduler + Cloud Run Jobs | Prefect |
|---------|----------------------------------|---------|
| Schedule | Cron | Cron + event triggers |
| Retry | Job-level (restart whole job) | Task-level (retry only the failed task) |
| Inter-task data | Not possible | Typed artifact passing |
| Dependency control | Not possible | "Run feature engineering only if ingestion wrote > 100 rows" |
| UI | Cloud Logging | Prefect UI with flow graph, real-time task status |
| Backfill | Manual | Built-in backfill by date range |

### Migration (low effort — existing functions are already @task-ready)

```python
from prefect import flow, task

@task(retries=3, retry_delay_seconds=exponential_backoff(backoff_factor=60),
      name="NBA Raw Ingestion")
def ingest_nba_data(seasons: list[str]) -> int:
    run_full_ingestion(seasons=seasons)
    return get_ingested_row_count()  # pass to next task

@task(name="Feature Engineering")
def compute_features(row_count: int, seasons: list[str]) -> None:
    if row_count < 50:
        raise ValueError(f"Insufficient data: {row_count} rows")
    run_feature_engineering(seasons=seasons)

@flow(name="Daily NBA Pipeline", log_prints=True)
def daily_pipeline(seasons: list[str] = ["2025-26"]) -> None:
    row_count = ingest_nba_data(seasons)
    compute_features(row_count, seasons)
```

Prefect Cloud (free tier) hosts the orchestration server.
Cloud Run remains the execution environment (Prefect worker polls Prefect Cloud for flow runs).
Cloud Scheduler still triggers at 06:30 UTC — it now calls the Prefect API instead of Cloud Run Jobs directly.

---

## Cost Estimate (GCP Monthly)

| Service | Tier | Cost |
|---------|------|------|
| Cloud SQL (Postgres 16, db-f1-micro) | Always-on | ~$10/month |
| Cloud Run API (min-instances=1) | ~100K req/day | ~$15-25/month |
| Cloud Run ChromaDB (min-instances=1) | Low traffic | ~$5/month |
| Cloud Run Jobs (pipeline) | 3 jobs × 10min/day | ~$1/month |
| Cloud Scheduler | 6 jobs | ~$0.10/month |
| Cloud Storage | 5GB | ~$0.50/month |
| Artifact Registry | 2GB images | ~$0.20/month |
| Cloud Build | CI/CD | Free (120 min/day) |
| Secret Manager | 10 secrets | ~$0.06/month |
| Cloud Monitoring | Custom metrics | Free tier |
| Vertex AI Experiments | Logging | Free tier |
| Vertex AI Model Registry | GCS cost only | ~$0/month |
| Vertex AI Pipelines | Per pipeline run | ~$0.02/run |
| **Total** | | **~$35-45/month** |

---

## Interview Talking Points (Updated)

### On orchestration:
"I replaced an embedded APScheduler (which was coupled to the API process) with Cloud Run Jobs triggered by Cloud Scheduler. Each pipeline job runs in its own isolated container with only the dependencies it needs. The API has no awareness of the pipeline — scaling the API to multiple instances doesn't spawn duplicate pipeline runs. If the pipeline fails, the API continues serving predictions from the last known good state."

### On MLOps:
"I use Vertex AI as my ML platform. Every training run is logged to Vertex AI Experiments so I can compare accuracy, Brier score, and calibration across runs. Models are versioned in the Model Registry with a 'production' alias — rolling back means reassigning the alias, not redeploying. Promotion to production is governed by a Vertex AI Pipeline that requires the challenger to beat the champion by at least 1 percentage point in accuracy."

### On data freshness (the upgrade from manual refresh):
"Data ingestion is no longer manual. Cloud Scheduler fires a Cloud Run Job at 06:30 UTC daily. The job runs `run_full_ingestion()` → validates row count → runs `run_feature_engineering()` → writes audit record to Postgres. If the job fails, Cloud Scheduler retries with exponential backoff and Cloud Monitoring sends an alert. I have complete visibility into every pipeline run without ever manually running a script."

### On cost:
"The entire GCP stack costs ~$40/month. I chose Cloud SQL over self-managed Postgres because automated backups, point-in-time recovery, and patching are worth $10/month when you have real prediction data you can't afford to lose. I chose Cloud Run over GKE because it scales to zero when idle and I'm not running a Kubernetes cluster for a portfolio project."
