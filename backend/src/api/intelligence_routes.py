"""
Phase 4 intelligence API routes (RAG + rule overlays).
"""

from __future__ import annotations

from datetime import date
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src import config
from src.data.db import get_db
from src.intelligence.service import IntelligenceService
from src.intelligence.types import DailyBriefResponse, GameIntelligenceResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])


def _ensure_intelligence_enabled() -> None:
    if not config.INTELLIGENCE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Intelligence endpoints disabled (INTELLIGENCE_ENABLED=false)",
        )


@router.get("/game/{game_id}", response_model=GameIntelligenceResponse)
async def get_game_intelligence(
    game_id: str,
    season: Optional[str] = Query(default=config.CURRENT_SEASON),
    top_k: int = Query(default=config.RAG_TOP_K, ge=1, le=12),
    max_age_hours: int = Query(default=config.RAG_MAX_AGE_HOURS, ge=1, le=336),
    db: Session = Depends(get_db),
):
    _ensure_intelligence_enabled()
    service = IntelligenceService(db)
    try:
        return service.get_game_intelligence(
            game_id=game_id,
            season=season,
            top_k=top_k,
            max_age_hours=max_age_hours,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to generate game intelligence for %s: %s", game_id, exc)
        raise HTTPException(status_code=500, detail="Failed to generate game intelligence") from exc


@router.get("/brief", response_model=DailyBriefResponse)
async def get_daily_intelligence_brief(
    date_value: date = Query(default_factory=date.today, alias="date"),
    season: str = Query(default=config.CURRENT_SEASON),
    limit: int = Query(default=10, ge=1, le=25),
    top_k: int = Query(default=config.RAG_TOP_K, ge=1, le=12),
    max_age_hours: int = Query(default=config.RAG_MAX_AGE_HOURS, ge=1, le=336),
    db: Session = Depends(get_db),
):
    _ensure_intelligence_enabled()
    service = IntelligenceService(db)
    try:
        return service.get_daily_brief(
            brief_date=date_value,
            season=season,
            limit=limit,
            top_k=top_k,
            max_age_hours=max_age_hours,
        )
    except Exception as exc:
        logger.error("Failed to generate daily intelligence brief: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to generate daily intelligence brief") from exc
