"""
Dead-Letter Store for Failed Ingestion Records
=================================================

Wave 3: When payload validation fails, the record is NOT silently dropped —
it is persisted here with the full raw payload and structured error messages.

Why a dead-letter table?
    - Ops visibility: you can query `failed_ingestion` to see *why* records fail
    - Replay: once the bug is fixed, you can reprocess the failed records
    - Alerting: aggregate counts can trigger a Slack alert if data quality degrades
    - Audit: full traceability of data lineage (what came in, what was rejected)

This follows the Dead Letter Queue pattern from distributed systems
(RabbitMQ DLQ, Kafka dead-letter topics) applied at the DB layer.

Wave 3 — SCR-298
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def persist_failed_record(
    engine: Engine,
    *,
    entity_type: str,
    raw_payload: Dict[str, Any],
    validation_errors: List[str],
    source_module: str = "ingestion",
) -> Optional[int]:
    """
    Persist a single failed validation record to the dead-letter table.

    Parameters
    ----------
    engine           : SQLAlchemy engine
    entity_type      : "team" | "game" | "player"
    raw_payload      : original dict from the API / ingestion pipeline
    validation_errors: list of human-readable error strings from the validator
    source_module    : which module produced the record (for filtering)

    Returns
    -------
    The inserted row id, or None on failure.
    """
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO failed_ingestion
                        (entity_type, raw_payload, validation_errors, source_module, attempted_at)
                    VALUES
                        (:entity_type, :raw_payload::jsonb, :validation_errors::jsonb,
                         :source_module, NOW())
                    RETURNING id
                """),
                {
                    "entity_type": entity_type,
                    "raw_payload": json.dumps(raw_payload, default=str),
                    "validation_errors": json.dumps(validation_errors),
                    "source_module": source_module,
                },
            )
            row_id = result.scalar()
            logger.warning(
                "🗃️  [dead_letter] Persisted failed %s record id=%s errors=%s",
                entity_type,
                row_id,
                validation_errors[:2],  # log first 2 errors to keep log compact
            )
            return row_id
    except Exception as exc:
        logger.error("[dead_letter] Could not persist failed record: %s", exc)
        return None


def persist_failed_batch(
    engine: Engine,
    failed_records: List[Dict[str, Any]],
    entity_type: str,
    source_module: str = "ingestion",
) -> int:
    """
    Persist a batch of failed records.

    Parameters
    ----------
    failed_records : list of {"raw": {...}, "errors": [...]} dicts
                     (output of validators.validate_batch)

    Returns
    -------
    Number of records successfully persisted.
    """
    persisted = 0
    for item in failed_records:
        row_id = persist_failed_record(
            engine,
            entity_type=entity_type,
            raw_payload=item.get("raw", {}),
            validation_errors=item.get("errors", []),
            source_module=source_module,
        )
        if row_id is not None:
            persisted += 1
    return persisted


def list_failed_records(
    engine: Engine,
    *,
    entity_type: Optional[str] = None,
    source_module: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Fetch failed ingestion records for inspection.

    Parameters
    ----------
    entity_type   : filter by entity type ("team"/"game"/"player") or None for all
    source_module : filter by source module or None for all
    limit         : max records to return
    offset        : pagination offset

    Returns
    -------
    List of dicts representing failed_ingestion rows.
    """
    filters = []
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if entity_type:
        filters.append("entity_type = :entity_type")
        params["entity_type"] = entity_type

    if source_module:
        filters.append("source_module = :source_module")
        params["source_module"] = source_module

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    query = text(f"""
        SELECT
            id,
            entity_type,
            raw_payload,
            validation_errors,
            source_module,
            attempted_at,
            created_at
        FROM failed_ingestion
        {where_clause}
        ORDER BY attempted_at DESC
        LIMIT :limit OFFSET :offset
    """)

    try:
        with engine.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "id": row[0],
                "entity_type": row[1],
                "raw_payload": row[2],
                "validation_errors": row[3],
                "source_module": row[4],
                "attempted_at": row[5].isoformat() if row[5] else None,
                "created_at": row[6].isoformat() if row[6] else None,
            }
            for row in rows
        ]
    except Exception as exc:
        logger.error("[dead_letter] list_failed_records failed: %s", exc)
        return []


def count_failed_records(
    engine: Engine,
    *,
    entity_type: Optional[str] = None,
    source_module: Optional[str] = None,
) -> int:
    """Return the total count of failed records matching the filters."""
    filters = []
    params: Dict[str, Any] = {}

    if entity_type:
        filters.append("entity_type = :entity_type")
        params["entity_type"] = entity_type

    if source_module:
        filters.append("source_module = :source_module")
        params["source_module"] = source_module

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    query = text(f"SELECT COUNT(*) FROM failed_ingestion {where_clause}")

    try:
        with engine.connect() as conn:
            result = conn.execute(query, params).scalar()
        return int(result or 0)
    except Exception as exc:
        logger.error("[dead_letter] count_failed_records failed: %s", exc)
        return 0
