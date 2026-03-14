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
from typing import Any, Dict, Optional

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
