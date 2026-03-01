"""
Scribble — read-only SQL playground routes.

Security contract:
  - Only SELECT statements are accepted (enforced via regex before execution).
  - Forbidden DML/DDL keywords are rejected at the application layer.
  - Queries are executed inside a read-only transaction (SET TRANSACTION READ ONLY).
  - Row limit is enforced server-side: any query exceeding MAX_ROWS is silently capped.
  - Execution time is bounded by a PostgreSQL statement_timeout (10 s).
"""

import re
import time
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.data.db import get_db

router = APIRouter(prefix="/api/v1/scribble", tags=["scribble"])

MAX_ROWS = 500
STATEMENT_TIMEOUT_MS = 10_000  # 10 seconds

# Reject anything that is not a bare SELECT
_SELECT_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)

# Block DML / DDL / privilege keywords regardless of position
_FORBIDDEN_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|TRUNCATE|DROP|CREATE|ALTER|RENAME|GRANT|REVOKE"
    r"|EXECUTE|EXEC|CALL|DO|COPY|VACUUM|ANALYZE|CLUSTER|REINDEX|REFRESH)\b",
    re.IGNORECASE,
)

# Detect whether a LIMIT clause is already present
_LIMIT_RE = re.compile(r"\bLIMIT\s+(\d+)", re.IGNORECASE)


def _validate(sql: str) -> str:
    """Validate and normalise the SQL. Returns cleaned SQL or raises HTTPException."""
    cleaned = sql.strip()

    if not _SELECT_RE.match(cleaned):
        raise HTTPException(
            status_code=400,
            detail="Only SELECT queries are allowed. DML and DDL are not permitted.",
        )

    if _FORBIDDEN_RE.search(cleaned):
        raise HTTPException(
            status_code=400,
            detail="Query contains a forbidden keyword (INSERT, UPDATE, DELETE, DROP, etc.).",
        )

    # Strip trailing semicolons to allow safe LIMIT injection
    cleaned = cleaned.rstrip(";").rstrip()

    # Cap or inject LIMIT
    limit_match = _LIMIT_RE.search(cleaned)
    if limit_match:
        existing = int(limit_match.group(1))
        if existing > MAX_ROWS:
            cleaned = _LIMIT_RE.sub(f"LIMIT {MAX_ROWS}", cleaned)
    else:
        cleaned = f"{cleaned}\nLIMIT {MAX_ROWS}"

    return cleaned


class QueryRequest(BaseModel):
    sql: str


class QueryResponse(BaseModel):
    sql: str
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    elapsed_ms: float


@router.post("/query", response_model=QueryResponse)
async def execute_query(
    payload: QueryRequest,
    db: Session = Depends(get_db),
):
    """
    Execute a read-only SELECT query against the Postgres database.

    - Only SELECT statements are accepted.
    - Results are capped at 500 rows.
    - Queries time out after 10 seconds.
    - Runs inside a read-only transaction for full safety.
    """
    sql = _validate(payload.sql)

    start = time.perf_counter()
    try:
        db.execute(text("SET LOCAL statement_timeout = :ms"), {"ms": STATEMENT_TIMEOUT_MS})
        db.execute(text("SET TRANSACTION READ ONLY"))

        result = db.execute(text(sql))
        columns: List[str] = list(result.keys())
        raw_rows = result.fetchall()

        rows: List[Dict[str, Any]] = []
        for row in raw_rows:
            row_dict: Dict[str, Any] = {}
            for col, val in zip(columns, row):
                # Coerce non-JSON-serialisable types to strings
                if val is not None and not isinstance(val, (int, float, bool, str)):
                    row_dict[col] = str(val)
                else:
                    row_dict[col] = val
            rows.append(row_dict)

        elapsed_ms = (time.perf_counter() - start) * 1000
        return QueryResponse(
            sql=sql,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            elapsed_ms=round(elapsed_ms, 2),
        )

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
