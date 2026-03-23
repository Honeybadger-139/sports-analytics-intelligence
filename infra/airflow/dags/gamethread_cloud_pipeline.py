"""
Airflow DAG: GameThread Cloud Pipeline Orchestration.

Runs in any Airflow environment (Cloud Composer 2, local Docker, CI runner).
Calls the deployed Cloud Run backend admin endpoints over HTTPS.

Environment variables (or Airflow Variables / Secret Manager):
    GAMETHREAD_API_BASE_URL     Cloud Run service URL (https://...)
    GAMETHREAD_CHAT_API_KEY     X-API-Key for admin auth
    GAMETHREAD_API_TIMEOUT_SECONDS  Max wait for pipeline (default: 7200)
    GAMETHREAD_PIPELINE_INCLUDE_RAG Include RAG refresh step (default: false)
    GAMETHREAD_ENV              "cloud" or "local" (controls DAG ID & tags)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator

log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
# Tries Airflow Variables first (Composer-friendly), falls back to env vars.

def _get_config(key: str, default: str = "") -> str:
    """Read config from Airflow Variable → env var → default."""
    try:
        from airflow.models import Variable
        value = Variable.get(key, default_var=None)
        if value:
            return value
    except Exception:
        pass
    return os.getenv(key, default)


def _get_api_base_url() -> str:
    url = _get_config("GAMETHREAD_API_BASE_URL", "").rstrip("/")
    if not url:
        raise ValueError(
            "GAMETHREAD_API_BASE_URL is required. "
            "Set it as an Airflow Variable or environment variable. "
            "Expected: Cloud Run service URL (e.g., https://gamethread-api-xxxxx.run.app)"
        )
    return url


def _get_api_key() -> str:
    key = _get_config("GAMETHREAD_CHAT_API_KEY", "")
    if not key:
        raise ValueError(
            "GAMETHREAD_CHAT_API_KEY is required. "
            "Set it via Airflow Variable, Secret Manager, or env var."
        )
    return key


API_TIMEOUT = int(_get_config("GAMETHREAD_API_TIMEOUT_SECONDS", "7200"))
INCLUDE_RAG = _get_config("GAMETHREAD_PIPELINE_INCLUDE_RAG", "false").strip().lower() in {
    "1", "true", "yes", "on",
}
ENV_LABEL = _get_config("GAMETHREAD_ENV", "cloud")


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _headers() -> Dict[str, str]:
    return {
        "X-API-Key": _get_api_key(),
        "Content-Type": "application/json",
    }


def _request(
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = API_TIMEOUT,
) -> Dict[str, Any]:
    """Make authenticated HTTP request to the backend API."""
    url = f"{_get_api_base_url()}{path}"
    log.info("→ %s %s (timeout=%ds)", method, url, timeout)

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=_headers(),
            json=payload,
            timeout=timeout,
        )
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            f"Cannot reach backend at {url}. "
            f"Is GAMETHREAD_API_BASE_URL correct? Error: {exc}"
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(
            f"Request to {url} timed out after {timeout}s. "
            f"Pipeline may still be running. Check Cloud Run logs."
        ) from exc

    if response.status_code == 401:
        raise RuntimeError(
            "Authentication failed (401). "
            "GAMETHREAD_CHAT_API_KEY does not match backend CHAT_API_KEY."
        )
    if response.status_code == 503:
        raise RuntimeError(
            "Admin API is disabled (503). "
            "Backend CHAT_API_KEY may not be configured."
        )

    response.raise_for_status()
    return response.json() if response.content else {}


# ── Task callables ────────────────────────────────────────────────────────────

def check_api_health(**context) -> Dict[str, Any]:
    """Verify the Cloud Run backend is reachable and healthy."""
    base_url = _get_api_base_url()

    # Try /healthz first (works locally), fall back to /api/v1/chat/health (Cloud Run)
    for path in ["/healthz", "/api/v1/chat/health"]:
        try:
            log.info("Health check: %s%s", base_url, path)
            response = requests.get(f"{base_url}{path}", timeout=30)
            if response.status_code == 200:
                payload = response.json()
                health_status = payload.get("status")
                if health_status in ("ok", "healthy"):
                    log.info("✅ Backend healthy via %s: %s", path, json.dumps(payload, indent=2))
                    return payload
                raise RuntimeError(f"Backend health check returned status={health_status}: {payload}")
        except requests.exceptions.ConnectionError:
            continue

    raise RuntimeError(
        f"Backend unreachable at {base_url}. "
        "Tried /healthz and /api/v1/chat/health — both failed."
    )


def trigger_pipeline_run(**context) -> Dict[str, Any]:
    """Trigger ingestion + feature engineering via admin API."""
    log.info("Triggering pipeline (include_rag=False)...")
    payload = _request(
        "POST",
        "/api/v1/admin/pipeline/run-now",
        payload={"run_rag_refresh": False},
    )

    status = payload.get("status")
    elapsed = payload.get("elapsed_seconds", "?")
    log.info("Pipeline result: status=%s elapsed=%ss", status, elapsed)

    if status != "completed":
        raise RuntimeError(f"Pipeline did not complete: {payload}")

    # Push result for downstream tasks
    context["ti"].xcom_push(key="pipeline_result", value=payload)
    return payload


def trigger_rag_refresh(**context) -> Dict[str, Any]:
    """Trigger RAG vector refresh (optional, controlled by env var)."""
    if not INCLUDE_RAG:
        log.info("RAG refresh skipped (GAMETHREAD_PIPELINE_INCLUDE_RAG=false)")
        return {"status": "skipped", "reason": "disabled_by_config"}

    log.info("Triggering RAG refresh...")
    payload = _request("POST", "/api/v1/admin/rag/run-now")

    status = payload.get("status")
    elapsed = payload.get("elapsed_seconds", "?")
    log.info("RAG result: status=%s elapsed=%ss", status, elapsed)

    if status != "completed":
        raise RuntimeError(f"RAG refresh did not complete: {payload}")

    return payload


def verify_system_status(**context) -> Dict[str, Any]:
    """Post-run system health check — catches silent failures."""
    log.info("Verifying system status...")
    payload = _request("GET", "/api/v1/system/status", timeout=60)

    system_status = payload.get("status", "unknown")
    pipeline_info = payload.get("pipeline") or {}
    last_status = (pipeline_info.get("last_status") or "").lower()
    last_sync = pipeline_info.get("last_sync", "never")

    healthy_statuses = {"success", "completed", "skipped_no_new_data"}

    if system_status in {"error", "degraded"}:
        raise RuntimeError(
            f"System unhealthy after pipeline run: status={system_status}, "
            f"pipeline_last_status={last_status}, last_sync={last_sync}"
        )

    if last_status and last_status not in healthy_statuses:
        raise RuntimeError(
            f"Pipeline last status is '{last_status}' (expected one of {healthy_statuses}). "
            f"Last sync: {last_sync}"
        )

    summary = {
        "system_status": system_status,
        "pipeline_last_status": last_status or "n/a",
        "pipeline_last_sync": last_sync,
        "database": payload.get("database", "unknown"),
    }
    log.info("✅ System verified: %s", json.dumps(summary, indent=2))
    return summary


# ── DAG definition ────────────────────────────────────────────────────────────

default_args = {
    "owner": "gamethread",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
    "execution_timeout": timedelta(hours=3),
    "email_on_failure": False,
}


with DAG(
    dag_id=f"gamethread_{ENV_LABEL}_pipeline",
    default_args=default_args,
    description="Orchestrate GameThread data pipeline via Cloud Run admin API",
    start_date=datetime(2026, 3, 23),
    schedule="30 6 * * *",  # Daily at 06:30 UTC
    catchup=False,
    max_active_runs=1,
    tags=["gamethread", ENV_LABEL, "pipeline", "cloud-run"],
    doc_md=__doc__,
) as dag:

    health_check = PythonOperator(
        task_id="check_backend_health",
        python_callable=check_api_health,
        retries=3,
        retry_delay=timedelta(minutes=2),
    )

    pipeline = PythonOperator(
        task_id="trigger_pipeline_ingestion_features",
        python_callable=trigger_pipeline_run,
        execution_timeout=timedelta(hours=2),
    )

    rag_refresh = PythonOperator(
        task_id="trigger_rag_refresh",
        python_callable=trigger_rag_refresh,
        execution_timeout=timedelta(hours=1),
    )

    verify = PythonOperator(
        task_id="verify_system_status",
        python_callable=verify_system_status,
        retries=1,
        retry_delay=timedelta(minutes=1),
    )

    health_check >> pipeline >> rag_refresh >> verify
