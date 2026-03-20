# Hybrid Orchestration Architecture: Cloud Run Jobs + Prefect
**Date:** 2026-03-19
**Decision:** Use Cloud Run Jobs (GCP-native) for raw NBA data ingestion, and Prefect for feature engineering pipeline
**Supersedes:** gcp-mlops-plan-2026-03-19.md (sections on orchestration)

---

## The Problem with APScheduler (Root Cause)

`scheduler.py` embeds APScheduler as a BackgroundScheduler inside the FastAPI process.
Three fatal flaws in production:

1. **Lifecycle coupling** — API restart = pipeline stops. Container crash = missed ingestion.
2. **Duplicate execution** — 2 API replicas = 2 schedulers firing duplicate jobs simultaneously. The `ON CONFLICT DO UPDATE` upsert prevents data corruption but wastes NBA API quota and compute.
3. **No observability** — There is no DAG graph, no task-level status, no retry UI. You know a job failed only if you read `pipeline_audit` in Postgres manually.

The fix is to separate the pipeline into two distinct tools that match the complexity of their respective jobs.

---

## Why Split Into Two Tools?

The ingestion job and the feature engineering job have fundamentally different characteristics:

| Characteristic | Raw Ingestion (NBA API → Storage) | Feature Engineering (Raw → Features) |
|---|---|---|
| Control flow | Linear: fetch → validate → write | Branching: if H2H data missing → fallback; if row count < 50 → abort |
| Retry granularity | Whole job (if NBA API fails, retry everything) | Per-task (if H2H calculation fails, retry H2H only, not rolling features) |
| Inter-task data | None needed | Row count from ingestion → guards feature computation |
| Complexity | Low (HTTP → write) | High (rolling windows, H2H joins, streak computation) |
| Execution time | 5–10 minutes | 10–20 minutes |
| Observability needed | Basic (Cloud Logging) | Full (task-level graph, step outputs, conditional branching) |

**Conclusion:** Simple jobs → simple tools. Complex jobs → powerful tools.
Using Prefect for raw ingestion would be overkill. Using Cloud Run Jobs for feature engineering would be invisible and hard to debug.

---

## Full Hybrid Architecture

```
                    ┌─────────────────┐
                    │  Cloud Scheduler │
                    │   06:30 UTC      │
                    └────────┬────────┘
                             │ HTTP trigger
                             ▼
              ┌──────────────────────────────┐
              │   Cloud Run Job              │
              │   job-nba-raw-ingestion       │
              │                              │
              │  1. Pull NBA API (nba_api)   │
              │  2. Validate: row count,     │
              │     schema, date range       │
              │  3. Write to GCS (data lake) │
              │     gs://gamethread-raw/     │
              │     YYYY/MM/DD/              │
              │     ├── games.parquet        │
              │     ├── team_stats.parquet   │
              │     └── player_stats.parquet │
              │  4. Upsert to Cloud SQL      │
              │     (matches, team_game_     │
              │     stats, player_game_stats) │
              │  5. Publish to Pub/Sub       │
              │     topic: pipeline-complete  │
              └──────────────────────────────┘
                             │
                             │ Pub/Sub message
                             ▼
              ┌──────────────────────────────┐
              │   Prefect Agent              │
              │   (Cloud Run, always-on)     │
              │                             │
              │   Triggers: feature-         │
              │   engineering-pipeline       │
              └──────────┬───────────────────┘
                         │
                         ▼
     ┌───────────────────────────────────────────────────┐
     │  Prefect Flow: feature-engineering-pipeline        │
     │                                                   │
     │  @task Task 1: Validate Raw Data                  │
     │    - Assert row_count >= 50                        │
     │    - Assert no column > 15% null                  │
     │    - Assert game_dates in current season          │
     │    - If fails: STOP, write audit, send alert       │
     │         │                                         │
     │         ▼ (on success only)                       │
     │  @task Task 2: Compute Rolling Features           │
     │    - win_pct_last_5, win_pct_last_10              │
     │    - avg_point_diff, off/def rating, pace, eFG%   │
     │    - retry=3, retry_delay=60s                     │
     │         │                                         │
     │         ▼                                         │
     │  @task Task 3: Compute H2H Features               │
     │    - h2h_win_pct, h2h_avg_margin                  │
     │    - Fallback: 0.5 if no history                  │
     │    - h2h_data_available binary flag               │
     │    - retry=3                                      │
     │         │                                         │
     │         ▼                                         │
     │  @task Task 4: Compute Rest/Fatigue Features      │
     │    - days_rest, is_back_to_back, current_streak   │
     │    - retry=2                                      │
     │         │                                         │
     │         ▼                                         │
     │  @task Task 5: Write to match_features (Cloud SQL) │
     │    - INSERT ... ON CONFLICT DO UPDATE             │
     │    - retry=3                                      │
     │         │                                         │
     │         ▼                                         │
     │  @task Task 6: Validate Feature Output            │
     │    - Assert features written = raw rows matched   │
     │    - Assert no NaN in critical feature columns    │
     │         │                                         │
     │         ▼                                         │
     │  @task Task 7: Write Pipeline Audit               │
     │    - Status, row counts, elapsed time, errors     │
     │         │                                         │
     │         ▼                                         │
     │  @task Task 8: Trigger Prediction Refresh         │
     │    - POST /api/v1/admin/refresh-predictions       │
     │    - Only if features written > 0                 │
     └───────────────────────────────────────────────────┘
                         │
                         ▼
               Cloud SQL: match_features
               API serves fresh predictions
```

---

## Pros and Cons Analysis

### Cloud Run Jobs for Raw Ingestion

**Pros:**
- **Fully GCP-native.** Zero additional services to manage. Cloud Scheduler, Pub/Sub, and Cloud Run are all in the same console, same billing, same IAM model.
- **Serverless.** The container spins up, runs, and terminates. You pay only for execution time (~$0.01 per run). No idle cost.
- **Isolated dependency set.** The ingestion image carries only `nba_api`, `pandas`, `google-cloud-storage`, `sqlalchemy`. No FastAPI, no SHAP, no LangGraph. Image size: ~300MB instead of 1.5GB. Faster cold starts.
- **Independent deployability.** You can update the ingestion logic and rebuild/redeploy its image without touching the API container.
- **Automatic retry.** Cloud Scheduler retries failed HTTP triggers. Cloud Run Jobs itself has `--max-retries` at the job level.
- **Structured logging.** All stdout/stderr goes to Cloud Logging automatically with correlation IDs.
- **GCS as raw data lake.** Writing raw data to GCS as Parquet gives you a permanent, cheap (~$0.02/GB/month) record of every ingestion run. If you change your feature logic 3 months from now, you can replay feature engineering from GCS without re-hitting the NBA API.

**Cons:**
- **Job-level retry only.** If the ingestion job processes 20 teams and fails on team 21, the whole job restarts from team 1. The `ON CONFLICT DO UPDATE` upsert makes this safe (idempotent), but it wastes API quota. Mitigation: write a checkpoint file to GCS after each team's data, and the job resumes from the last checkpoint.
- **No task-level visibility.** You see the job as a single unit in Cloud Run. Sub-step failures are only visible in Cloud Logging, not as a visual graph. For a simple linear job, this is acceptable.
- **No inter-run data passing.** A job cannot easily pass data to the next job in the chain (e.g., "I ingested 847 rows, here's the breakdown"). This is why Pub/Sub is used — the message can carry metadata like row count, ingestion timestamp, and season.
- **Longer cold start than APScheduler.** APScheduler fires instantly inside the running process. Cloud Run Job cold starts take 5–15 seconds for a container to spin up. This is negligible for a daily batch job.

---

### Prefect for Feature Engineering

**Pros:**
- **Task-level retry.** If the H2H calculation fails due to a DB timeout, only the H2H task retries. Rolling features (already computed and passed as an artifact) are not re-executed. This is the fundamental advantage over Cloud Run Jobs.
- **Conditional branching.** `if row_count < 50: raise ValueError(...)` inside a `@task` is handled gracefully — Prefect marks that task as `Failed`, skips downstream tasks, and reports the reason in the UI. No more silent partial executions.
- **Inter-task data passing.** The validation task returns the row count as an integer, which is passed into the feature computation tasks as a typed parameter. This is impossible in Cloud Run Jobs without writing to an intermediate store.
- **Visual flow graph.** The Prefect UI shows the DAG in real-time as it runs. You can see which task is in-progress, which failed, which completed, and click into any task to see its logs and inputs/outputs. This is an interview-grade portfolio talking point.
- **Python-native.** Your existing `feature_store.py` functions are already well-structured. Migration is decorator-based (`@flow`, `@task`) — no rewrite.
- **Free Prefect Cloud tier.** 3 workspaces, unlimited flow runs. You pay nothing unless you exceed the free tier.
- **Backfill support.** If you miss a day's feature computation (e.g., Cloud Run Job wrote to GCS but Pub/Sub delivery failed), you can trigger a backfill run by date from the Prefect UI with one click.
- **Deployment versioning.** Each code change to the flow creates a new deployment version. You can roll back to a previous version of the feature engineering logic without touching the API.

**Cons:**
- **One additional service.** Prefect Cloud is an external dependency. Free tier is reliable, but you're trusting a third-party service. Mitigation: Prefect is open-source — you can self-host Prefect Server on Cloud Run if you want full control.
- **Prefect agent must be running.** The Prefect agent (a Python process that polls Prefect Cloud for flow runs) must be deployed and healthy to execute flows. If the agent crashes, Pub/Sub messages queue up, but flows don't execute. Mitigation: deploy the agent on Cloud Run with `min-instances=1`.
- **Learning curve for the decorator pattern.** The `@flow` / `@task` mental model is simple but different from plain Python. Debugging Prefect flows locally requires `prefect server start` or a mock setup.
- **Latency.** Prefect adds ~10–30 seconds of orchestration overhead (Pub/Sub delivery + agent polling interval + flow scheduling). For a batch job that runs once daily, this is irrelevant.
- **Overkill for simple tasks.** Do not put the raw ingestion into Prefect. The complexity budget should be spent on feature engineering where it actually helps.

---

### Why Not Airflow (Cloud Composer)?

Airflow is the industry standard and you should know it for interviews. You should NOT use it here because:
- **Cost:** Cloud Composer starts at ~$300/month. This is 10× your total monthly GCP budget.
- **Operational overhead:** Composer runs a GKE cluster. You manage it, patch it, and scale it.
- **Over-engineered for 2 daily jobs:** Airflow shines when you have 20+ interdependent DAGs, complex backfill logic, and a team of data engineers. For 2 jobs (ingestion + features), it is a sledgehammer for a nail.

**What to say in interviews:** "I evaluated Airflow but chose Cloud Run Jobs + Prefect because they give me 90% of Airflow's benefits at 2% of the cost. If this platform were ingesting 5 sports leagues with 50+ interdependent DAGs and a data engineering team, I'd migrate to Cloud Composer."

---

### Why Not Pure Prefect for Everything?

You could put raw ingestion into Prefect too. The reason to separate it is **operational simplicity**. The ingestion job is a fetch-and-write — it doesn't need task graphs, conditional branches, or inter-task data passing. Putting it in Prefect adds agent dependency, orchestration latency, and Prefect-specific debugging for no meaningful benefit. Keep simple things simple.

---

## Data Flow: Raw Data Landing Zones

### GCS Raw Zone (Data Lake)
```
gs://gamethread-raw/
  2026/03/19/
    games.parquet           # All game records for the day's ingestion
    team_stats.parquet      # All team_game_stats records
    player_stats.parquet    # All player_game_stats records
    ingestion_meta.json     # {"seasons": ["2025-26"], "rows": 847, "run_id": "..."}
```

**Why Parquet?**
- Columnar format: reading only `game_id`, `team_id`, `points` from a 50-column file reads ~6% of the data instead of 100%.
- Snappy compression: 5–10× smaller than CSV for numeric data.
- Schema enforcement: unlike CSV, Parquet stores column types. You can't accidentally read `game_date` as a string.
- Replay: if feature logic changes, you reprocess from Parquet without re-hitting the NBA API.

### Cloud SQL (Serving Layer)
The Cloud Run Job also upserts into Cloud SQL immediately after writing to GCS. Cloud SQL is the source of truth for the API — the frontend never reads from GCS directly. GCS is the archive; Cloud SQL is the live serving store.

### Pub/Sub Message Schema
```json
{
  "run_id": "20260319_063142",
  "status": "success",
  "seasons": ["2025-26"],
  "rows_ingested": {
    "matches": 12,
    "team_game_stats": 24,
    "player_game_stats": 288
  },
  "gcs_prefix": "gs://gamethread-raw/2026/03/19/",
  "ingestion_completed_at": "2026-03-19T06:38:00Z"
}
```
Prefect's Pub/Sub subscriber reads this message. If `rows_ingested.matches == 0`, the flow skips feature engineering and writes an audit record with status `"skipped_no_new_data"`.

---

## Updated GCP Service Map (Final)

```
Project: sports-analytics-intelligence
│
├── Ingestion Layer
│   ├── Cloud Scheduler       → cron trigger (06:30 UTC daily)
│   ├── Cloud Run Job         → job-nba-raw-ingestion (Python, nba_api)
│   ├── Cloud Storage         → gs://gamethread-raw/ (Parquet data lake)
│   └── Pub/Sub               → topic: pipeline-events (completion signal)
│
├── Feature Engineering Layer
│   ├── Prefect Cloud         → flow registry + UI (free tier)
│   ├── Cloud Run (always-on) → Prefect agent (min-instances=1)
│   └── Cloud SQL             → match_features table (feature store)
│
├── RAG Refresh Layer
│   ├── Cloud Scheduler       → 4× daily (00:00, 06:00, 12:00, 18:00 UTC)
│   └── Cloud Run Job         → job-rag-refresh (Python, chromadb, google-generativeai)
│
├── Serving Layer
│   ├── Cloud Run Service     → gamethread-api (FastAPI + Gunicorn, min-instances=1)
│   ├── Cloud Run Service     → gamethread-chroma (ChromaDB server)
│   └── Cloud SQL             → Postgres 16 (managed, auto-backup)
│
├── MLOps Layer
│   ├── Vertex AI Experiments → Training run comparison
│   ├── Vertex AI Model Registry → Versioned model artifacts + aliases
│   ├── Vertex AI Pipelines   → Retrain DAG (champion vs challenger)
│   └── Cloud Storage         → gs://gamethread-models/ (model artifacts)
│
├── Secrets & Config
│   └── Secret Manager        → All API keys, DB password, Langfuse key
│
├── Observability
│   ├── Cloud Monitoring      → Infra + custom metrics + alerting
│   ├── Cloud Logging         → Structured logs from all services
│   └── Looker Studio         → Business dashboards (free)
│
└── CI/CD
    ├── Cloud Build           → test → build → push → deploy
    └── Artifact Registry     → Docker images
```

---

## Phase-Wise Implementation Plan

### PHASE 0: Pre-conditions (Do Before Any Phase Starts)
These are blocking steps. All phases depend on them.

- [ ] Create GCP project: `sports-analytics-intelligence`
- [ ] Enable APIs: Cloud Run, Cloud Scheduler, Cloud SQL, Cloud Storage, Pub/Sub, Secret Manager, Vertex AI, Artifact Registry, Cloud Build
- [ ] Create service accounts with least-privilege IAM roles
- [ ] Provision Cloud SQL (Postgres 16, db-f1-micro, us-central1)
- [ ] Create GCS buckets: `gamethread-raw`, `gamethread-models`, `gamethread-chroma`
- [ ] Create Pub/Sub topic: `pipeline-events`
- [ ] Create Prefect Cloud account (free tier), create workspace `sports-analytics`
- [ ] Generate Prefect API key → store in Secret Manager

---

### PHASE 1: Core ML Fixes (parallel, no GCP dependency)

**Sub-agent A (data):** Fix `fillna(0)` imputation + add data validation gate
**Sub-agent B (models):** Add ONNX export + library version metadata in artifacts
**Sub-agent C (api):** Fix Dockerfile (`--reload` → Gunicorn), split requirements.txt, fix CORS

These 3 sub-agents run fully in parallel. No dependencies between them.

---

### PHASE 2: GCP Foundation + Ingestion Decoupling (parallel after Phase 0)

**Sub-agent A (ingestion):** Extract `run_full_ingestion()` into `Dockerfile.ingestion` + Cloud Run Job + write to GCS as Parquet + publish to Pub/Sub
**Sub-agent B (api-deploy):** Deploy FastAPI to Cloud Run + wire Cloud SQL + Secret Manager
**Sub-agent C (rag-job):** Extract `run_rag_ingestion_job()` into `Dockerfile.rag` + Cloud Run Job + Cloud Scheduler triggers
**Sub-agent D (ci-cd):** Create `cloudbuild.yaml` (test → build → push → deploy for all 3 images)

Sub-agents A, B, C, D run in parallel after Phase 0 completes.

---

### PHASE 3: Prefect Feature Engineering (depends on Phase 2-A completing)

**Sub-agent A (prefect-setup):** Deploy Prefect agent on Cloud Run + Pub/Sub subscriber
**Sub-agent B (prefect-flow):** Convert `feature_store.py` to Prefect `@flow` + `@task` with retry policies + conditional branching
**Sub-agent C (prefect-validation):** Add validation tasks (row count gate, null check, schema assertion) + audit task

Sub-agents A, B, C run in parallel once Phase 2-A is done (ingestion writes to GCS + Pub/Sub).

---

### PHASE 4: Vertex AI MLOps (parallel, depends on Phase 2-B)

**Sub-agent A (experiments):** Add Vertex AI Experiments logging to `trainer.py`
**Sub-agent B (registry):** Wire Vertex AI Model Registry (replace `artifact_store.py` GCS path logic)
**Sub-agent C (pipelines):** Build Vertex AI retrain pipeline (replace `retrain_worker.py` polling loop)

Sub-agents A, B, C run in parallel once Cloud Run API is deployed (Phase 2-B).

---

### PHASE 5: Monitoring + Dashboards (parallel, depends on Phases 2-4)

**Sub-agent A (monitoring):** Cloud Monitoring custom metrics + alerting policies
**Sub-agent B (dashboards):** Looker Studio dashboards (prediction performance, bankroll, pipeline health)
**Sub-agent C (drift):** Add KL divergence monitoring for prediction distribution drift

---

## Cost Estimate (Final)

| Service | Purpose | Monthly Cost |
|---------|---------|-------------|
| Cloud SQL db-f1-micro | Postgres 16 (managed) | ~$10 |
| Cloud Run API (min=1) | FastAPI serving | ~$15–25 |
| Cloud Run ChromaDB (min=1) | Vector store | ~$5 |
| Cloud Run Prefect agent (min=1) | Flow executor | ~$5 |
| Cloud Run Jobs (3 jobs) | Ingestion + RAG | ~$1 |
| Cloud Scheduler (6 triggers) | Cron | ~$0.10 |
| Cloud Storage (10GB total) | Raw data + models | ~$0.20 |
| Pub/Sub | Pipeline events | ~$0.01 |
| Secret Manager | API keys | ~$0.06 |
| Artifact Registry (3 images) | Docker images | ~$0.30 |
| Cloud Build | CI/CD | Free (120 min/day) |
| Vertex AI Experiments | ML tracking | Free tier |
| Vertex AI Model Registry | Model versioning | ~$0 (GCS cost) |
| Vertex AI Pipelines | Retrain DAG | ~$0.05/run |
| Cloud Monitoring | Metrics + alerting | Free tier |
| Prefect Cloud | Orchestration UI | Free tier |
| Looker Studio | Dashboards | Free |
| **Total** | | **~$37–47/month** |

---

## Interview Talking Points (Hybrid Architecture)

### On the split decision:
"I separated raw ingestion from feature engineering because they have fundamentally different complexity profiles. Ingestion is a linear fetch-and-write — Cloud Run Jobs handle that cleanly with GCS as the raw data lake and Pub/Sub as the completion signal. Feature engineering has branching logic, task-level retry requirements, and inter-task data dependencies — that's exactly where Prefect adds value. Using Prefect for ingestion would be over-engineered; using Cloud Run Jobs for feature engineering would be invisible and hard to debug."

### On GCS as data lake:
"Raw data lands in GCS as Parquet files partitioned by date before it touches Cloud SQL. This gives me replay capability — if my feature logic has a bug today, I can fix it and reprocess 6 months of data from GCS without re-querying the NBA API. Parquet is columnar and compressed, so storage costs are negligible."

### On Pub/Sub as the handoff:
"The handoff between Cloud Run Job (ingestion) and Prefect (feature engineering) is a Pub/Sub message. This decouples the two systems completely — the ingestion job doesn't know Prefect exists, and Prefect doesn't care how the data was ingested. I could swap Cloud Run Jobs for Spark on Dataflow next year and the feature pipeline wouldn't change."

### On Prefect vs Airflow:
"I chose Prefect over Airflow because Airflow (via Cloud Composer) starts at $300/month for a managed cluster — that's prohibitive for a solo portfolio project. Prefect Cloud's free tier covers unlimited flow runs. If this were a team product with 20+ interdependent DAGs, I'd evaluate Cloud Composer."
