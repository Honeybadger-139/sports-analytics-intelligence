# Cloud Composer 2 — GameThread Pipeline Orchestration

## Architecture

```
Cloud Composer 2 (Airflow)
    │
    ├── check_backend_health     →  GET  /healthz
    ├── trigger_pipeline         →  POST /api/v1/admin/pipeline/run-now
    ├── trigger_rag_refresh      →  POST /api/v1/admin/rag/run-now
    └── verify_system_status     →  GET  /api/v1/system/status
                                        │
                                Cloud Run (gamethread-api)
                                        │
                                Cloud SQL (PostgreSQL)
```

## Quick Start

### Option A: Full Composer Setup (~$250/mo)

```bash
# From repo root:
./infra/composer/setup-composer.sh
```

### Option B: Local Airflow (Free, Docker)

```bash
docker compose -f docker-compose.dev.yml up airflow -d
# DAG auto-loaded from infra/airflow/dags/
```

### Option C: Direct trigger (Free, no Airflow)

```bash
# Trigger pipeline manually via Cloud Run:
curl -X POST https://gamethread-api-864291380911.us-central1.run.app/api/v1/admin/pipeline/run-now \
  -H "X-API-Key: $CHAT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"run_rag_refresh": false}'
```

## Required Secrets

| Secret Name | Where | Purpose |
|---|---|---|
| `CHAT_API_KEY` | Secret Manager + Airflow Variable | Admin API authentication |
| `GAMETHREAD_API_BASE_URL` | Airflow Variable | Cloud Run HTTPS URL |
| `GAMETHREAD_CHAT_API_KEY` | Airflow Variable (from Secret Manager) | Same as CHAT_API_KEY |

## Environment Variables (DAG)

| Variable | Default | Description |
|---|---|---|
| `GAMETHREAD_API_BASE_URL` | *(required)* | Cloud Run service URL |
| `GAMETHREAD_CHAT_API_KEY` | *(required)* | X-API-Key header value |
| `GAMETHREAD_API_TIMEOUT_SECONDS` | `7200` | Max wait for pipeline (2h) |
| `GAMETHREAD_PIPELINE_INCLUDE_RAG` | `false` | Include RAG refresh step |
| `GAMETHREAD_ENV` | `cloud` | Controls DAG ID suffix |

## Operations

### Manual Trigger (Composer)

```bash
gcloud composer environments run gamethread-composer \
  --location=us-central1 \
  dags trigger -- gamethread_cloud_pipeline
```

### Manual Trigger (Local Docker)

```bash
docker exec -it airflow airflow dags trigger gamethread_cloud_pipeline
```

### Update DAG (Composer)

```bash
# Get GCS bucket:
DAG_BUCKET=$(gcloud composer environments describe gamethread-composer \
  --location=us-central1 \
  --format="value(config.dagGcsPrefix)")

# Upload:
gsutil cp infra/airflow/dags/gamethread_cloud_pipeline.py "$DAG_BUCKET/"
```

### View Logs

```bash
# Composer task logs:
gcloud composer environments run gamethread-composer \
  --location=us-central1 \
  tasks logs-list -- gamethread_cloud_pipeline trigger_pipeline_ingestion_features $(date +%Y-%m-%d)

# Cloud Run logs (backend side):
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gamethread-api AND textPayload:pipeline" \
  --limit=20 --freshness=1h --format="value(textPayload)"
```

### Rollback

```bash
# 1. Pause the DAG:
gcloud composer environments run gamethread-composer \
  --location=us-central1 \
  dags pause -- gamethread_cloud_pipeline

# 2. Restore previous DAG version:
gsutil cp gs://backup-bucket/gamethread_cloud_pipeline.py.bak "$DAG_BUCKET/"

# 3. Unpause:
gcloud composer environments run gamethread-composer \
  --location=us-central1 \
  dags unpause -- gamethread_cloud_pipeline
```

## Cost Optimization

Composer 2 smallest config: ~$250/month. Alternatives for solo projects:

| Approach | Monthly Cost | Reliability |
|---|---|---|
| Cloud Composer 2 | ~$250 | Production-grade |
| Cloud Scheduler + Cloud Run Jobs | $0 idle | Good, no dependency graph |
| Local Docker Airflow | $0 | Depends on laptop uptime |
| GitHub Actions cron | $0 (free tier) | Good for simple schedules |

**Recommendation:** Use Cloud Scheduler (already configured in `infra/cloud-scheduler/`) until the project requires multi-step dependency orchestration. The Composer DAG is ready to deploy when needed.

## Files

| File | Purpose |
|---|---|
| `infra/airflow/dags/gamethread_cloud_pipeline.py` | Composer-ready DAG |
| `infra/airflow/dags/gamethread_local_api_pipeline.py` | Local-only DAG (original) |
| `infra/composer/setup-composer.sh` | Automated Composer setup |
| `infra/composer/README.md` | This file |
