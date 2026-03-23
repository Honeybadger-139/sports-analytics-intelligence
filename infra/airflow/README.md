# Airflow Orchestration (Local API Pattern)

This folder contains a local Airflow DAG that orchestrates GameThread through FastAPI admin endpoints.

## DAG

- `dags/gamethread_local_api_pipeline.py`
  - checks `GET /healthz`
  - triggers `POST /api/v1/admin/pipeline/run-now`
  - optionally triggers `POST /api/v1/admin/rag/run-now`
  - verifies `GET /api/v1/system/status`

## Required Environment Variables

- `GAMETHREAD_API_BASE_URL` (default: `http://127.0.0.1:8000`)
- `GAMETHREAD_CHAT_API_KEY` (required; same key used by admin routes)
- `GAMETHREAD_API_TIMEOUT_SECONDS` (default: `7200`)
- `GAMETHREAD_PIPELINE_INCLUDE_RAG` (`true/false`, default: `false`)

When running Airflow inside Docker:
- if backend runs on host machine: use `http://host.docker.internal:8000`
- if backend runs in Compose: use `http://backend:8000`

## Local Compose Runtime

The dev compose file includes an `airflow` service:

```bash
docker-compose -f docker-compose.base.yml -f docker-compose.dev.yml up -d airflow
```

Airflow UI will be available at `http://localhost:8088`.

## Why this works for local -> cloud

Airflow only orchestrates API calls. The backend pipeline writes to whichever database is set in `DATABASE_URL`.
If `DATABASE_URL` points to Cloud SQL/Postgres, the same run automatically lands in your cloud database.
