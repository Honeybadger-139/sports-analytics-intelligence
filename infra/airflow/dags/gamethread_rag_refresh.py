"""
Airflow DAG: GameThread RAG Vector Store Refresh.

Runs every 6 hours to fetch latest NBA news and update the pgvector store
in Cloud SQL. Kept deliberately separate from the heavy data pipeline DAG
so RAG context stays fresh without waiting for the daily NBA API ingestion.

Schedule: every 6 hours (0:00, 6:00, 12:00, 18:00 UTC)
Runtime:  ~60-90 seconds per run
Depends:  Backend API reachable via GAMETHREAD_API_BASE_URL

Environment variables (or Airflow Variables):
    GAMETHREAD_API_BASE_URL      Cloud Run or ngrok tunnel URL
    GAMETHREAD_CHAT_API_KEY      X-API-Key for admin auth
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator

log = logging.getLogger(__name__)


# ── Config helpers (shared pattern with main pipeline DAG) ────────────────────

def _get_config(key: str, default: str = "") -> str:
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
        raise ValueError("GAMETHREAD_API_BASE_URL is required.")
    return url


def _get_api_key() -> str:
    key = _get_config("GAMETHREAD_CHAT_API_KEY", "")
    if not key:
        raise ValueError("GAMETHREAD_CHAT_API_KEY is required.")
    return key


def _headers() -> Dict[str, str]:
    base_url = _get_api_base_url()
    headers = {
        "X-API-Key": _get_api_key(),
        "Content-Type": "application/json",
    }
    if "ngrok" in base_url:
        headers["ngrok-skip-browser-warning"] = "true"
    return headers


def _request(method: str, path: str, timeout: int = 120) -> Dict[str, Any]:
    url = f"{_get_api_base_url()}{path}"
    log.info("→ %s %s", method, url)
    try:
        response = requests.request(method=method, url=url, headers=_headers(), timeout=timeout)
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(f"Cannot reach backend at {url}: {exc}") from exc
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Request to {url} timed out after {timeout}s.")

    if response.status_code == 401:
        raise RuntimeError("Authentication failed (401). Check GAMETHREAD_CHAT_API_KEY.")
    if response.status_code == 503:
        raise RuntimeError("Admin API disabled (503). CHAT_API_KEY not configured on backend.")

    response.raise_for_status()
    return response.json() if response.content else {}


# ── Task callables ────────────────────────────────────────────────────────────

def check_backend_health(**context) -> Dict[str, Any]:
    """Quick health check before triggering RAG refresh."""
    base_url = _get_api_base_url()
    extra = {"ngrok-skip-browser-warning": "true"} if "ngrok" in base_url else {}

    for path in ["/healthz", "/api/v1/chat/health"]:
        try:
            response = requests.get(f"{base_url}{path}", headers=extra, timeout=20)
            if response.status_code == 200:
                payload = response.json()
                if payload.get("status") in ("ok", "healthy"):
                    log.info("✅ Backend healthy: %s", json.dumps(payload))
                    return payload
        except requests.exceptions.ConnectionError:
            continue

    raise RuntimeError(f"Backend unreachable at {base_url}.")


def run_rag_refresh(**context) -> Dict[str, Any]:
    """
    Call POST /api/v1/admin/rag/run-now and wait for completion.

    This endpoint is synchronous but fast (~60-90 seconds):
      1. Fetch NBA news from RSS feeds (CBS Sports, ESPN, RotoWire)
      2. Generate 768-dim Gemini embeddings for each article
      3. Upsert into rag_documents table in Cloud SQL via pgvector
      4. Chatbot immediately has access to latest articles

    Unlike the pipeline trigger, this does NOT need async fire-and-forget
    because the total runtime fits well within ngrok's 5-min timeout.
    """
    log.info("🔄 Starting RAG vector store refresh...")

    payload = _request("POST", "/api/v1/admin/rag/run-now", timeout=300)

    status = payload.get("status")
    elapsed = payload.get("elapsed_seconds", "?")
    log.info("RAG refresh result: status=%s  elapsed=%ss", status, elapsed)

    if status != "completed":
        raise RuntimeError(f"RAG refresh did not complete successfully: {payload}")

    log.info("✅ RAG refresh complete in %ss. Vector store is up to date.", elapsed)
    return payload


def verify_rag_health(**context) -> Dict[str, Any]:
    """Check RAG health endpoint to confirm documents are in the vector store."""
    payload = _request("GET", "/api/v1/health/rag", timeout=30)

    doc_count = payload.get("document_count", 0)
    rag_status = payload.get("status", "unknown")

    log.info("RAG health: status=%s  documents=%s", rag_status, doc_count)

    if doc_count == 0:
        raise RuntimeError("RAG vector store is empty after refresh — check news fetch logs.")

    log.info("✅ Vector store healthy: %d documents available for chatbot.", doc_count)
    return payload


# ── DAG definition ────────────────────────────────────────────────────────────

default_args = {
    "owner": "gamethread",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=15),
    "execution_timeout": timedelta(minutes=10),
    "email_on_failure": False,
}

with DAG(
    dag_id="gamethread_rag_refresh",
    default_args=default_args,
    description="Refresh NBA news embeddings in pgvector every 6 hours",
    start_date=datetime(2026, 3, 25),
    schedule="0 */6 * * *",   # 00:00, 06:00, 12:00, 18:00 UTC
    catchup=False,
    max_active_runs=1,        # never run two refreshes simultaneously
    tags=["gamethread", "rag", "vector-store", "cloud-run"],
    doc_md=__doc__,
) as dag:

    health = PythonOperator(
        task_id="check_backend_health",
        python_callable=check_backend_health,
        retries=3,
        retry_delay=timedelta(minutes=2),
    )

    refresh = PythonOperator(
        task_id="refresh_rag_vector_store",
        python_callable=run_rag_refresh,
        execution_timeout=timedelta(minutes=8),
    )

    verify = PythonOperator(
        task_id="verify_rag_health",
        python_callable=verify_rag_health,
        retries=1,
        retry_delay=timedelta(minutes=1),
    )

    health >> refresh >> verify
