"""
Admin Routes — Runtime Configuration API
==========================================

Wave 3: Expose the app_config DB table via a secured admin API so operational
thresholds and feature flags can be changed at runtime without redeployment.

Endpoints:
    GET  /api/v1/admin/config          — list all config entries
    GET  /api/v1/admin/config/{key}    — get a single config value
    PATCH /api/v1/admin/config/{key}   — upsert a config value
    DELETE /api/v1/admin/config/{key}  — remove a config key

Security:
    All endpoints require the X-API-Key header matching CHAT_API_KEY.
    In production, this should be behind a service mesh / VPN and restricted
    to internal tooling. Do not expose admin endpoints publicly.

    We reuse CHAT_API_KEY here for simplicity — a production system would
    have a separate ADMIN_API_KEY with stricter access controls.

Wave 3 — SCR-298
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.data.db import get_db
from src.data.runtime_config import delete_config, get_config, list_configs, set_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# ── Auth dependency ────────────────────────────────────────────────────────────

def _require_api_key(x_api_key: str = Header(default="")) -> None:
    """Validate X-API-Key header against CHAT_API_KEY env var."""
    expected = os.getenv("CHAT_API_KEY", "")
    if not expected:
        # No key configured → admin endpoints are disabled for safety
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API is disabled: CHAT_API_KEY is not configured.",
        )
    if x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header.",
        )


# ── Request / Response models ─────────────────────────────────────────────────

class ConfigUpsertRequest(BaseModel):
    value: str = Field(..., description="New config value (always stored as string)")
    description: Optional[str] = Field(
        default=None, description="Human-readable description of this config key"
    )


class ConfigEntry(BaseModel):
    key: str
    value: str
    description: Optional[str]
    updated_at: Optional[str]
    created_at: Optional[str]


class PipelineRunRequest(BaseModel):
    run_rag_refresh: bool = Field(
        default=False,
        description="When true, run a RAG vector refresh immediately after ingestion + features.",
    )


def _run_pipeline_job() -> None:
    """Load raw data then feature tables using the scheduler's manual pipeline path."""
    from scheduler import run_pipeline_job

    run_pipeline_job()


def _run_rag_ingestion_job() -> None:
    """Refresh vector store using the scheduler's manual RAG path."""
    from scheduler import run_rag_ingestion_job

    run_rag_ingestion_job()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/config", dependencies=[Depends(_require_api_key)])
def list_all_configs(db: Session = Depends(get_db)):
    """
    List all runtime configuration entries.

    Returns all key/value pairs stored in the app_config table.
    """
    engine = db.get_bind()
    configs = list_configs(engine)
    return {"count": len(configs), "configs": configs}


@router.get("/config/{key}", dependencies=[Depends(_require_api_key)])
def get_config_entry(key: str, db: Session = Depends(get_db)):
    """
    Get a single runtime config entry by key.

    Returns 404 if the key does not exist.
    """
    engine = db.get_bind()
    value = get_config(engine, key)
    if value is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config key '{key}' not found.",
        )
    return {"key": key, "value": value}


@router.patch("/config/{key}", dependencies=[Depends(_require_api_key)])
def upsert_config_entry(
    key: str,
    body: ConfigUpsertRequest,
    db: Session = Depends(get_db),
):
    """
    Create or update a runtime config entry.

    Body:
        value       — new config value (string)
        description — optional description of the key's purpose

    Affects:
        The change is immediately visible to any code that reads from app_config.
        No restart required.

    Examples of updatable keys:
        active_model_path    → point to a previous model artifact for rollback
        rag_min_similarity   → tighten/loosen RAG context floor
        psi_drift_threshold  → adjust drift alerting sensitivity
        mlops_accuracy_threshold → change retrain trigger threshold
    """
    engine = db.get_bind()
    success = set_config(engine, key, body.value, description=body.description)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update config key '{key}'. Check server logs.",
        )
    logger.info("✅ [admin_routes] Config updated: %s = %s", key, body.value)
    return {
        "status": "updated",
        "key": key,
        "value": body.value,
        "description": body.description,
    }


@router.delete("/config/{key}", dependencies=[Depends(_require_api_key)])
def delete_config_entry(key: str, db: Session = Depends(get_db)):
    """
    Delete a runtime config key.

    Returns 404 if the key does not exist.
    Protected keys (e.g., seeded defaults) should be reset, not deleted.
    """
    engine = db.get_bind()
    deleted = delete_config(engine, key)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config key '{key}' not found — nothing deleted.",
        )
    return {"status": "deleted", "key": key}


@router.post("/pipeline/run-now", dependencies=[Depends(_require_api_key)])
def run_pipeline_now(body: Optional[PipelineRunRequest] = None):
    """
    Trigger the full pipeline immediately (ingestion + feature engineering).

    This endpoint is intentionally synchronous so external orchestrators (Airflow,
    cron, etc.) can treat completion/failure as a deterministic task result.
    """
    request = body or PipelineRunRequest()
    started_at = datetime.now(timezone.utc)
    rag_status = "skipped"

    try:
        _run_pipeline_job()
        if request.run_rag_refresh:
            _run_rag_ingestion_job()
            rag_status = "success"
    except Exception as exc:
        logger.error("❌ [admin_routes] Manual pipeline trigger failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Manual pipeline trigger failed: {exc}",
        ) from exc

    finished_at = datetime.now(timezone.utc)
    elapsed_seconds = round((finished_at - started_at).total_seconds(), 2)
    logger.info(
        "✅ [admin_routes] Manual pipeline trigger completed in %.2fs (rag=%s)",
        elapsed_seconds,
        rag_status,
    )
    return {
        "status": "completed",
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "elapsed_seconds": elapsed_seconds,
        "run_rag_refresh": request.run_rag_refresh,
        "rag_status": rag_status,
    }


# ── In-process async job registry ─────────────────────────────────────────────
# Simple dict keyed by job_id. Fine for single-process local use.
_PIPELINE_JOBS: Dict[str, dict] = {}


@router.post("/pipeline/trigger", dependencies=[Depends(_require_api_key)])
def trigger_pipeline_async(body: Optional[PipelineRunRequest] = None):
    """
    Fire-and-forget pipeline trigger. Returns immediately with a job_id.

    Use GET /api/v1/admin/pipeline/status/{job_id} to poll for completion.
    This avoids long-running HTTP connections that time out through tunnels/proxies.
    """
    request = body or PipelineRunRequest()
    job_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    _PIPELINE_JOBS[job_id] = {
        "job_id": job_id,
        "status": "running",
        "started_at": started_at.isoformat(),
        "finished_at": None,
        "elapsed_seconds": None,
        "error": None,
        "run_rag_refresh": request.run_rag_refresh,
    }

    def _run():
        try:
            _run_pipeline_job()
            if request.run_rag_refresh:
                _run_rag_ingestion_job()
            finished = datetime.now(timezone.utc)
            _PIPELINE_JOBS[job_id].update({
                "status": "completed",
                "finished_at": finished.isoformat(),
                "elapsed_seconds": round((finished - started_at).total_seconds(), 2),
            })
            logger.info("✅ [admin_routes] Async pipeline job %s completed", job_id)
        except Exception as exc:
            finished = datetime.now(timezone.utc)
            _PIPELINE_JOBS[job_id].update({
                "status": "failed",
                "finished_at": finished.isoformat(),
                "elapsed_seconds": round((finished - started_at).total_seconds(), 2),
                "error": str(exc),
            })
            logger.error("❌ [admin_routes] Async pipeline job %s failed: %s", job_id, exc)

    thread = threading.Thread(target=_run, daemon=True, name=f"pipeline-{job_id[:8]}")
    thread.start()
    logger.info("🚀 [admin_routes] Async pipeline job %s started (thread=%s)", job_id, thread.name)

    return {
        "job_id": job_id,
        "status": "running",
        "started_at": started_at.isoformat(),
        "poll_url": f"/api/v1/admin/pipeline/status/{job_id}",
    }


@router.get("/pipeline/status/{job_id}", dependencies=[Depends(_require_api_key)])
def get_pipeline_status(job_id: str):
    """
    Poll the status of an async pipeline job started via POST /pipeline/trigger.
    Returns status: running | completed | failed.
    """
    job = _PIPELINE_JOBS.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found. It may have expired or never existed.",
        )
    return job


@router.post("/rag/run-now", dependencies=[Depends(_require_api_key)])
def run_rag_now():
    """
    Trigger only the RAG vector refresh path immediately.
    """
    started_at = time.perf_counter()
    started_at_utc = datetime.now(timezone.utc)
    try:
        _run_rag_ingestion_job()
    except Exception as exc:
        logger.error("❌ [admin_routes] Manual RAG trigger failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Manual RAG trigger failed: {exc}",
        ) from exc

    elapsed_seconds = round(time.perf_counter() - started_at, 2)
    logger.info("✅ [admin_routes] Manual RAG trigger completed in %.2fs", elapsed_seconds)
    return {
        "status": "completed",
        "started_at": started_at_utc.isoformat(),
        "elapsed_seconds": elapsed_seconds,
    }
