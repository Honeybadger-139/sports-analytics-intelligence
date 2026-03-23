"""
Airflow DAG: orchestrate local API-triggered pipeline runs.

This DAG is intended for a local-laptop control plane:
- Airflow runs locally.
- It calls the local FastAPI admin endpoints.
- The backend pipeline writes into the configured Postgres target
  (including Cloud SQL when DATABASE_URL points there).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator


API_BASE_URL = os.getenv("GAMETHREAD_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.getenv("GAMETHREAD_CHAT_API_KEY", "")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("GAMETHREAD_API_TIMEOUT_SECONDS", "7200"))
INCLUDE_RAG_REFRESH = os.getenv("GAMETHREAD_PIPELINE_INCLUDE_RAG", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _headers() -> Dict[str, str]:
    if not API_KEY:
        raise ValueError("GAMETHREAD_CHAT_API_KEY is required for admin trigger endpoints")
    return {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json",
    }


def _request(method: str, path: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    url = f"{API_BASE_URL}{path}"
    response = requests.request(
        method=method,
        url=url,
        headers=_headers(),
        json=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    if response.content:
        return response.json()
    return {}


def check_api_health() -> Dict[str, Any]:
    response = requests.get(f"{API_BASE_URL}/healthz", timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "ok":
        raise RuntimeError(f"Local API health check failed: {payload}")
    return payload


def trigger_pipeline_run() -> Dict[str, Any]:
    payload = _request("POST", "/api/v1/admin/pipeline/run-now", payload={"run_rag_refresh": False})
    if payload.get("status") != "completed":
        raise RuntimeError(f"Pipeline trigger did not complete successfully: {payload}")
    return payload


def trigger_rag_refresh_if_enabled() -> Dict[str, Any]:
    if not INCLUDE_RAG_REFRESH:
        return {"status": "skipped", "reason": "GAMETHREAD_PIPELINE_INCLUDE_RAG is false"}
    payload = _request("POST", "/api/v1/admin/rag/run-now")
    if payload.get("status") != "completed":
        raise RuntimeError(f"RAG refresh trigger did not complete successfully: {payload}")
    return payload


def capture_system_status() -> Dict[str, Any]:
    payload = _request("GET", "/api/v1/system/status")
    pipeline = payload.get("pipeline") or {}
    last_status = (pipeline.get("last_status") or "").lower()
    allowed_pipeline_statuses = {"success", "completed", "skipped_no_new_data"}
    if payload.get("status") in {"error", "degraded"}:
        raise RuntimeError(f"System status indicates unhealthy pipeline: {payload}")
    if last_status and last_status not in allowed_pipeline_statuses:
        raise RuntimeError(f"Latest pipeline status is not healthy: {payload}")
    return {
        "status": payload.get("status"),
        "database": payload.get("database"),
        "pipeline_last_sync": pipeline.get("last_sync"),
        "pipeline_last_status": last_status or None,
    }


default_args = {
    "owner": "gamethread",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


with DAG(
    dag_id="gamethread_local_api_pipeline",
    default_args=default_args,
    start_date=datetime(2026, 3, 23),
    schedule="30 6 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["gamethread", "local", "api-trigger", "pipeline"],
) as dag:
    check_local_api_health = PythonOperator(
        task_id="check_local_api_health",
        python_callable=check_api_health,
    )

    trigger_pipeline = PythonOperator(
        task_id="trigger_pipeline_ingestion_features",
        python_callable=trigger_pipeline_run,
        execution_timeout=timedelta(hours=2),
    )

    trigger_rag_refresh = PythonOperator(
        task_id="trigger_rag_refresh_optional",
        python_callable=trigger_rag_refresh_if_enabled,
        execution_timeout=timedelta(hours=1),
    )

    verify_system_status = PythonOperator(
        task_id="verify_system_status",
        python_callable=capture_system_status,
    )

    check_local_api_health >> trigger_pipeline >> trigger_rag_refresh >> verify_system_status
