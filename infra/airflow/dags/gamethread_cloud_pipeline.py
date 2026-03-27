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
from datetime import datetime, timedelta, timezone
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
    base_url = _get_api_base_url()
    headers = {
        "X-API-Key": _get_api_key(),
        "Content-Type": "application/json",
    }
    # ngrok free-tier shows a browser warning page unless this header is present.
    # Safe to include for all requests — ignored by non-ngrok servers.
    if "ngrok" in base_url:
        headers["ngrok-skip-browser-warning"] = "true"
    return headers


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


def _parse_iso_utc(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO timestamp into a timezone-aware UTC datetime."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _pipeline_completed_since(triggered_at_utc: datetime) -> Dict[str, Any]:
    """
    Fallback completion check when async in-memory job state is unavailable.

    This happens when /admin/pipeline/trigger and /admin/pipeline/status/{job_id}
    land on different backend workers that do not share process memory.
    """
    payload = _request("GET", "/api/v1/system/status", timeout=60)
    pipeline = payload.get("pipeline") or {}
    last_status = str(pipeline.get("last_status") or "").lower()
    last_sync_raw = pipeline.get("last_sync")
    last_sync_dt = _parse_iso_utc(last_sync_raw)
    healthy_statuses = {"success", "completed", "skipped_no_new_data"}
    completed = (
        bool(last_sync_dt)
        and last_sync_dt >= triggered_at_utc
        and last_status in healthy_statuses
    )
    return {
        "completed": completed,
        "system_status": payload.get("status", "unknown"),
        "pipeline_last_status": last_status or "unknown",
        "pipeline_last_sync": last_sync_raw,
    }


# ── Task callables ────────────────────────────────────────────────────────────

def check_api_health(**context) -> Dict[str, Any]:
    """Verify the Cloud Run backend is reachable and healthy."""
    base_url = _get_api_base_url()

    # Try /healthz first (works locally), fall back to /api/v1/chat/health (Cloud Run)
    extra = {"ngrok-skip-browser-warning": "true"} if "ngrok" in base_url else {}
    for path in ["/healthz", "/api/v1/chat/health"]:
        try:
            log.info("Health check: %s%s", base_url, path)
            response = requests.get(f"{base_url}{path}", headers=extra, timeout=30)
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
    """
    Trigger ingestion + feature engineering via async admin API.

    Uses fire-and-forget POST /pipeline/trigger (returns immediately with job_id)
    then polls GET /pipeline/status/{job_id} every 60s until completed or failed.

    Why async?  The synchronous /pipeline/run-now blocks for 20-30+ minutes.
    ngrok free tier drops HTTP connections after ~5 minutes of a long-running
    request, causing the Airflow task to fail even though the pipeline keeps
    running server-side. The async pattern keeps each HTTP call < 5 seconds —
    no connection timeout is possible.
    """
    import time as _time

    POLL_INTERVAL_SECONDS = 60
    max_wait = API_TIMEOUT  # honour the same overall ceiling
    triggered_at_utc = datetime.now(timezone.utc)

    log.info("Triggering async pipeline (include_rag=False)...")
    trigger_payload = _request(
        "POST",
        "/api/v1/admin/pipeline/trigger",
        payload={"run_rag_refresh": False},
        timeout=30,  # fire-and-forget — should return in < 1s
    )

    job_id = trigger_payload.get("job_id")
    poll_url = trigger_payload.get("poll_url", f"/api/v1/admin/pipeline/status/{job_id}")
    log.info("Pipeline job started: job_id=%s  poll_url=%s", job_id, poll_url)

    started = _time.monotonic()
    attempt = 0

    while True:
        elapsed_wall = _time.monotonic() - started
        if elapsed_wall > max_wait:
            raise RuntimeError(
                f"Pipeline job {job_id} did not complete within {max_wait}s "
                f"(last poll at {elapsed_wall:.0f}s)."
            )

        _time.sleep(POLL_INTERVAL_SECONDS)
        attempt += 1

        try:
            status_payload = _request(
                "GET",
                poll_url,
                timeout=30,
            )
        except Exception as exc:
            message = str(exc)
            # Fallback for local/ngrok topologies where in-memory async status
            # can be lost across workers/process restarts.
            if "404" in message and "not found" in message.lower():
                fallback = _pipeline_completed_since(triggered_at_utc)
                if fallback["completed"]:
                    synthetic = {
                        "job_id": job_id,
                        "status": "completed",
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                        "elapsed_seconds": round(elapsed_wall, 2),
                        "completion_source": "system_status_fallback",
                        "pipeline_last_status": fallback["pipeline_last_status"],
                        "pipeline_last_sync": fallback["pipeline_last_sync"],
                    }
                    log.info(
                        "✅ Pipeline completion inferred from /system/status "
                        "(job registry unavailable): %s",
                        json.dumps(synthetic, indent=2),
                    )
                    context["ti"].xcom_push(key="pipeline_result", value=synthetic)
                    return synthetic
                log.warning(
                    "Async job status endpoint returned 404 (attempt=%d, job_id=%s). "
                    "Falling back to /system/status polling: %s",
                    attempt,
                    job_id,
                    json.dumps(fallback, indent=2),
                )
                continue
            raise

        job_status = status_payload.get("status", "unknown")
        elapsed_job = status_payload.get("elapsed_seconds", "?")
        log.info(
            "Poll #%d — job_id=%s  status=%s  elapsed=%ss  wall=%.0fs",
            attempt, job_id, job_status, elapsed_job, elapsed_wall,
        )

        if job_status == "completed":
            log.info("✅ Pipeline job %s completed after %.0fs wall time.", job_id, elapsed_wall)
            context["ti"].xcom_push(key="pipeline_result", value=status_payload)
            return status_payload

        if job_status == "failed":
            error = status_payload.get("error", "unknown error")
            raise RuntimeError(
                f"Pipeline job {job_id} failed after {elapsed_job}s: {error}"
            )

        # status == "running" — keep polling
        log.info("  → Still running, next poll in %ds...", POLL_INTERVAL_SECONDS)


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
