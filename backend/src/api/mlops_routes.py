"""
Phase 5 MLOps API routes.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src import config
from src.data.db import get_db
from src.mlops.monitoring import get_monitoring_overview
from src.mlops.retrain_policy import evaluate_retrain_need

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mlops", tags=["mlops"])


@router.get("/monitoring")
async def mlops_monitoring(
    season: str = Query(default=config.CURRENT_SEASON),
    db: Session = Depends(get_db),
):
    try:
        return get_monitoring_overview(db, season)
    except Exception as exc:
        logger.error("Failed to fetch monitoring overview: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch monitoring overview") from exc


@router.get("/retrain/policy")
async def mlops_retrain_policy(
    season: str = Query(default=config.CURRENT_SEASON),
    dry_run: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    try:
        return evaluate_retrain_need(db, season, dry_run=dry_run)
    except Exception as exc:
        logger.error("Failed to evaluate retrain policy: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to evaluate retrain policy") from exc
