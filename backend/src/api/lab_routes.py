"""
Lab Routes — Wave 3 Extensions
================================

New endpoints surfaced in Wave 3:
    GET /api/v1/lab/failed-ingestion — list dead-letter records with pagination and filtering

Wave 3 — SCR-298
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.data.db import get_db
from src.data.dead_letter import count_failed_records, list_failed_records

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/lab", tags=["lab"])


@router.get("/failed-ingestion")
def get_failed_ingestion(
    entity_type: Optional[str] = Query(
        default=None,
        description="Filter by entity type: 'team', 'game', or 'player'",
    ),
    source_module: Optional[str] = Query(
        default=None,
        description="Filter by source module e.g. 'ingestion'",
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Max records to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
):
    """
    List records that failed validation during ingestion.

    These records were not written to the main tables and have been persisted
    in the `failed_ingestion` dead-letter table for investigation and replay.

    Use `entity_type` to filter to a specific payload type (team/game/player).
    Use `source_module` to filter by which pipeline module produced the failure.

    Returns paginated results with total_count for UI pagination.
    """
    engine = db.get_bind()

    records = list_failed_records(
        engine,
        entity_type=entity_type,
        source_module=source_module,
        limit=limit,
        offset=offset,
    )

    total = count_failed_records(engine, entity_type=entity_type, source_module=source_module)

    return {
        "total_count": total,
        "returned": len(records),
        "offset": offset,
        "limit": limit,
        "filters": {
            "entity_type": entity_type,
            "source_module": source_module,
        },
        "records": records,
    }
