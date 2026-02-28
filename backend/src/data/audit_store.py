"""
Utilities for pipeline audit table bootstrap and error handling.
"""

from sqlalchemy import text


def is_missing_pipeline_audit_error(exc: Exception) -> bool:
    """
    Detect missing-table errors for pipeline_audit across DB error wrappers.
    """
    message = str(exc).lower()
    return "pipeline_audit" in message and (
        "does not exist" in message or "undefinedtable" in message
    )


def ensure_pipeline_audit_table(engine) -> None:
    """
    Create pipeline_audit and supporting indexes if absent.

    This keeps legacy DB volumes compatible with current observability code.
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS pipeline_audit (
                    id SERIAL PRIMARY KEY,
                    sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    module VARCHAR(50) NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    records_processed INTEGER DEFAULT 0,
                    records_inserted INTEGER DEFAULT 0,
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
                CREATE INDEX IF NOT EXISTS idx_pipeline_audit_module
                ON pipeline_audit(module)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_pipeline_audit_status
                ON pipeline_audit(status)
                """
            )
        )
