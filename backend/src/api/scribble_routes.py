"""
Scribble — read-only SQL playground routes + Notebooks persistence.

Security contract for /query:
  - Only SELECT statements are accepted (enforced via regex before execution).
  - Forbidden DML/DDL keywords are rejected at the application layer.
  - Queries are executed inside a read-only transaction (SET TRANSACTION READ ONLY).
  - Row limit is enforced server-side: any query exceeding MAX_ROWS is silently capped.
  - Execution time is bounded by a PostgreSQL statement_timeout (10 s).

Notebooks:
  - Stored in PostgreSQL (scribble_notebooks table) — persistent across browsers/devices.
  - CRUD via GET/POST/PATCH/DELETE /api/v1/scribble/notebooks.
  - Table is auto-created on first request if it does not exist.
"""

import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.data.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/scribble", tags=["scribble"])

_NOTEBOOKS_TABLE_ENSURED = False


def _ensure_notebooks_table(db: Session) -> None:
    """
    Create the scribble_notebooks table if it does not already exist.
    Called lazily on the first notebooks request — no migration tool required.
    """
    global _NOTEBOOKS_TABLE_ENSURED
    if _NOTEBOOKS_TABLE_ENSURED:
        return
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS scribble_notebooks (
                id          TEXT        PRIMARY KEY,
                name        TEXT        NOT NULL,
                description TEXT        NOT NULL DEFAULT '',
                sql         TEXT        NOT NULL,
                saved_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        db.commit()
        _NOTEBOOKS_TABLE_ENSURED = True
        logger.info("scribble_notebooks table ready.")
    except Exception as exc:
        db.rollback()
        logger.error("Failed to ensure scribble_notebooks table: %s", exc)

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


# ── Notebooks CRUD ────────────────────────────────────────────────────────────

class NotebookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    sql: str = Field(..., min_length=1)


class NotebookUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)


class NotebookResponse(BaseModel):
    id: str
    name: str
    description: str
    sql: str
    savedAt: str    # camelCase to match the existing frontend SavedNotebook type
    updatedAt: str


def _row_to_notebook(row) -> NotebookResponse:
    return NotebookResponse(
        id=row[0],
        name=row[1],
        description=row[2],
        sql=row[3],
        savedAt=row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
        updatedAt=row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5]),
    )


@router.get("/notebooks", response_model=List[NotebookResponse])
async def list_notebooks(db: Session = Depends(get_db)):
    """Return all saved notebooks, newest first."""
    _ensure_notebooks_table(db)
    rows = db.execute(
        text("SELECT id, name, description, sql, saved_at, updated_at FROM scribble_notebooks ORDER BY saved_at DESC")
    ).fetchall()
    return [_row_to_notebook(r) for r in rows]


@router.post("/notebooks", response_model=NotebookResponse, status_code=201)
async def create_notebook(payload: NotebookCreate, db: Session = Depends(get_db)):
    """Save a new notebook."""
    _ensure_notebooks_table(db)
    nb_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    try:
        db.execute(
            text("""
                INSERT INTO scribble_notebooks (id, name, description, sql, saved_at, updated_at)
                VALUES (:id, :name, :desc, :sql, :now, :now)
            """),
            {"id": nb_id, "name": payload.name, "desc": payload.description, "sql": payload.sql, "now": now},
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save notebook: {exc}") from exc

    row = db.execute(
        text("SELECT id, name, description, sql, saved_at, updated_at FROM scribble_notebooks WHERE id = :id"),
        {"id": nb_id},
    ).fetchone()
    return _row_to_notebook(row)


@router.patch("/notebooks/{notebook_id}", response_model=NotebookResponse)
async def update_notebook(
    notebook_id: str, payload: NotebookUpdate, db: Session = Depends(get_db)
):
    """Update notebook name or description."""
    _ensure_notebooks_table(db)
    existing = db.execute(
        text("SELECT id FROM scribble_notebooks WHERE id = :id"), {"id": notebook_id}
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Notebook not found.")

    updates: Dict[str, Any] = {"id": notebook_id, "now": datetime.now(timezone.utc)}
    set_clauses = ["updated_at = :now"]
    if payload.name is not None:
        set_clauses.append("name = :name")
        updates["name"] = payload.name
    if payload.description is not None:
        set_clauses.append("description = :desc")
        updates["desc"] = payload.description

    try:
        db.execute(
            text(f"UPDATE scribble_notebooks SET {', '.join(set_clauses)} WHERE id = :id"),
            updates,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update notebook: {exc}") from exc

    row = db.execute(
        text("SELECT id, name, description, sql, saved_at, updated_at FROM scribble_notebooks WHERE id = :id"),
        {"id": notebook_id},
    ).fetchone()
    return _row_to_notebook(row)


@router.delete("/notebooks/{notebook_id}", status_code=204)
async def delete_notebook(notebook_id: str, db: Session = Depends(get_db)):
    """Delete a notebook by ID."""
    _ensure_notebooks_table(db)
    result = db.execute(
        text("DELETE FROM scribble_notebooks WHERE id = :id RETURNING id"), {"id": notebook_id}
    ).fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    db.commit()
