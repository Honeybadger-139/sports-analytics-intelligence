"""
Utilities for intelligence_audit table bootstrap and logging.
"""

import json
from typing import Any, Dict, Optional

from sqlalchemy import text


def is_missing_intelligence_audit_error(exc: Exception) -> bool:
    """
    Detect missing-table errors for intelligence_audit across DB error wrappers.
    """
    message = str(exc).lower()
    return "intelligence_audit" in message and (
        "does not exist" in message or "undefinedtable" in message
    )


def ensure_intelligence_audit_table(engine) -> None:
    """
    Create intelligence_audit and supporting indexes if absent.
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS intelligence_audit (
                    id SERIAL PRIMARY KEY,
                    run_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    module VARCHAR(50) NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    records_processed INTEGER DEFAULT 0,
                    errors TEXT,
                    details JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_intelligence_audit_module
                ON intelligence_audit(module)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_intelligence_audit_status
                ON intelligence_audit(status)
                """
            )
        )


def record_intelligence_audit(
    engine,
    *,
    module: str,
    status: str,
    records_processed: int = 0,
    errors: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Persist one intelligence audit event.
    """
    details_json = json.dumps(details or {})
    attempts = 0
    while attempts < 2:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO intelligence_audit (module, status, records_processed, errors, details)
                        VALUES (:module, :status, :records_processed, :errors, CAST(:details AS JSONB))
                        """
                    ),
                    {
                        "module": module,
                        "status": status,
                        "records_processed": records_processed,
                        "errors": errors,
                        "details": details_json,
                    },
                )
            return
        except Exception as exc:
            if attempts == 0 and is_missing_intelligence_audit_error(exc):
                ensure_intelligence_audit_table(engine)
                attempts += 1
                continue
            raise
