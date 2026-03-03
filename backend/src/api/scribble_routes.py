"""
Scribble — read-only SQL playground routes + Notebooks + Views persistence.

Security contract for /query:
  - Only SELECT / WITH statements are accepted (enforced via regex before execution).
  - Forbidden DML/DDL keywords are rejected at the application layer.
  - Queries are executed inside a read-only transaction (SET TRANSACTION READ ONLY).
  - Row limit is enforced server-side: any query exceeding MAX_ROWS is silently capped.
  - Execution time is bounded by a PostgreSQL statement_timeout (10 s).

Notebooks:
  - Stored in PostgreSQL (scribble_notebooks table) — persistent across browsers/devices.
  - CRUD via GET/POST/PATCH/DELETE /api/v1/scribble/notebooks.
  - Table is auto-created on first request if it does not exist.

Views:
  - User-created PostgreSQL views scoped to the public schema.
  - Names are forced to lowercase, alphanumeric + underscores only, max 63 chars.
  - All view bodies must be valid SELECT / WITH queries (same validation as /query).
  - CREATE OR REPLACE VIEW is used so re-saving updates the definition cleanly.
  - DROP is supported via DELETE /api/v1/scribble/views/{view_name}.
  - Views created here are real PostgreSQL views — queryable from SQL Lab immediately.
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
from src.intelligence.chat_service import LLMClient, _fetch_schema_context, _extract_sql

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

# Reject anything that is not a SELECT or a CTE (WITH ... SELECT)
_SELECT_RE = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)

# Block DML / DDL / privilege keywords regardless of position.
# Note: ANALYZE, CLUSTER, REINDEX are omitted here because they cannot appear
# in a valid SELECT query and are already blocked by the leading SELECT check.
# Removing them avoids false positives on column/alias names like "analyze_result".
_FORBIDDEN_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|TRUNCATE|DROP|CREATE|ALTER|RENAME|GRANT|REVOKE"
    r"|EXECUTE|EXEC|CALL|DO|COPY|VACUUM|REFRESH)\b",
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


# ── Views CRUD ─────────────────────────────────────────────────────────────────

# View names: lowercase letters, digits, underscores only; max 63 chars (PG identifier limit)
_VIEW_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def _sanitize_view_name(name: str) -> str:
    """Lowercase, strip whitespace, validate characters."""
    clean = name.strip().lower()
    if not _VIEW_NAME_RE.match(clean):
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid view name. Use lowercase letters, digits and underscores only. "
                "Must start with a letter and be ≤ 63 characters."
            ),
        )
    return clean


def _validate_view_body(sql: str) -> str:
    """Reuse the SELECT validator — view bodies must be read-only queries."""
    return _validate(sql)


class ViewCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=63)
    description: str = Field(default="", max_length=500)
    sql: str = Field(..., min_length=10)


class ViewMeta(BaseModel):
    name: str
    description: str
    sql: str
    created_at: str


def _get_view_comment(db: Session, view_name: str) -> str:
    """Read the COMMENT ON VIEW stored in pg_description, used as description."""
    row = db.execute(
        text("""
            SELECT obj_description(c.oid, 'pg_class') AS comment
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = :name
              AND n.nspname = 'public'
              AND c.relkind = 'v'
        """),
        {"name": view_name},
    ).fetchone()
    if row and row[0]:
        return row[0]
    return ""


def _get_view_definition(db: Session, view_name: str) -> str:
    """Return the stored view definition from pg_views."""
    row = db.execute(
        text("SELECT definition FROM pg_views WHERE schemaname = 'public' AND viewname = :name"),
        {"name": view_name},
    ).fetchone()
    return row[0].strip() if row else ""


@router.get("/views", response_model=List[ViewMeta])
async def list_views(db: Session = Depends(get_db)):
    """List all user-created views in the public schema, alphabetically."""
    rows = db.execute(
        text("""
            SELECT viewname
            FROM pg_views
            WHERE schemaname = 'public'
            ORDER BY viewname
        """)
    ).fetchall()

    views = []
    for row in rows:
        name = row[0]
        views.append(ViewMeta(
            name=name,
            description=_get_view_comment(db, name),
            sql=_get_view_definition(db, name),
            created_at="",
        ))
    return views


@router.post("/views", response_model=ViewMeta, status_code=201)
async def create_view(payload: ViewCreate, db: Session = Depends(get_db)):
    """
    Create or replace a PostgreSQL view from a SELECT query.

    - View name is sanitised to lowercase alphanumeric + underscores.
    - Body must be a valid SELECT / WITH query.
    - Uses CREATE OR REPLACE VIEW so updating an existing view is safe.
    - An optional description is stored as COMMENT ON VIEW.
    """
    view_name = _sanitize_view_name(payload.name)
    # Validate body (raises 400 on forbidden keywords or non-SELECT)
    body = _validate_view_body(payload.sql)
    # Strip the auto-appended LIMIT for view definitions
    _LIMIT_TAIL_RE = re.compile(r"\nLIMIT\s+\d+\s*$", re.IGNORECASE)
    body = _LIMIT_TAIL_RE.sub("", body).strip()

    try:
        db.execute(
            text(f'CREATE OR REPLACE VIEW "{view_name}" AS {body}')
        )
        if payload.description:
            safe_desc = payload.description.replace("'", "''")
            db.execute(text(f"COMMENT ON VIEW \"{view_name}\" IS '{safe_desc}'"))
        db.commit()
        logger.info("View '%s' created/replaced.", view_name)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create view: {exc}") from exc

    return ViewMeta(
        name=view_name,
        description=payload.description,
        sql=body,
        created_at="",
    )


@router.delete("/views/{view_name}", status_code=204)
async def drop_view(view_name: str, db: Session = Depends(get_db)):
    """Drop a user-created view by name."""
    clean_name = _sanitize_view_name(view_name)

    exists = db.execute(
        text("SELECT 1 FROM pg_views WHERE schemaname = 'public' AND viewname = :name"),
        {"name": clean_name},
    ).fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail=f"View '{clean_name}' not found.")

    try:
        db.execute(text(f'DROP VIEW IF EXISTS "{clean_name}"'))
        db.commit()
        logger.info("View '%s' dropped.", clean_name)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to drop view: {exc}") from exc


# ── AI SQL Assistant ───────────────────────────────────────────────────────────

_ai_llm: Optional[LLMClient] = None


def _get_ai_llm() -> LLMClient:
    global _ai_llm
    if _ai_llm is None:
        _ai_llm = LLMClient()
    return _ai_llm


_AI_SQL_SYSTEM = """
You are an expert PostgreSQL query writer for a live NBA sports analytics database.

Your ONLY job is to write a single, correct, read-only SELECT query that answers the user's question.

RULES:
1. Output ONLY the SQL query — no prose, no explanations, no markdown text outside the code block.
2. Wrap the query in a ```sql ... ``` code block.
3. Use ONLY the tables and columns listed in the schema below. Never invent columns.
4. Always use table aliases (e.g. `m` for matches, `t` for teams, `p` for players).
5. Default to the current season ('2025-26') unless the user specifies otherwise.
6. Do NOT use LIMIT unless the user asks for a specific number; the execution layer caps at 500 rows automatically.
7. Only write SELECT / WITH queries. Never write INSERT, UPDATE, DELETE, DROP, or any DDL.
8. If the question is ambiguous, pick the most sensible interpretation and add a short SQL comment (--) explaining the assumption.

CRITICAL RULES — ALWAYS FOLLOW:

PLAYER NAME MATCHING:
- Player names in the database contain unicode accented characters (e.g. "Nikola Jokić", "Luka Dončić").
- NEVER use ILIKE '%LastName%' to match a player by name — it will fail for any name with accented characters.
- ALWAYS match players via their player_id using a subquery:
    WHERE pgs.player_id = (SELECT player_id FROM players WHERE full_name ILIKE '%Joki%' LIMIT 1)
- Use a short unambiguous fragment of the name (e.g. '%Joki%' for Jokić, '%Don%' for Dončić, '%Anteto%' for Antetokounmpo).
- NEVER reference the accented spelling directly in a string literal.

OPPONENT TEAM PATTERN:
- To find the opponent team for a player in a game, use CASE WHEN on the match's home/away columns:
    JOIN teams opp ON opp.team_id = CASE
        WHEN pgs.team_id = m.home_team_id THEN m.away_team_id
        ELSE m.home_team_id
    END
- NEVER use OR conditions with != to find opponent team — that pattern is incorrect and returns 0 rows.

SCHEMA:
{schema}
"""


class AiSqlRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: List[Dict[str, str]] = Field(default_factory=list)


class AiSqlResponse(BaseModel):
    sql: str
    explanation: str


@router.post("/ai-sql", response_model=AiSqlResponse)
async def generate_sql(
    payload: AiSqlRequest,
    db: Session = Depends(get_db),
):
    """
    Natural-language → SQL query generator.

    - Injects the live database schema into the system prompt so the LLM always
      uses real table and column names.
    - Extracts the SQL block from the LLM's response.
    - Returns both the clean SQL and a brief plain-English explanation.
    - Only SELECT / WITH queries are generated; the response is never executed here.
    """
    llm = _get_ai_llm()
    if not llm.available:
        raise HTTPException(
            status_code=503,
            detail="AI SQL assistant is unavailable — GEMINI_API_KEY is not configured.",
        )

    schema = _fetch_schema_context(db)

    # Build conversation history for multi-turn context
    history_text = ""
    for turn in (payload.history or [])[-6:]:  # last 3 user+assistant pairs
        role = turn.get("role", "")
        content = turn.get("content", "")
        if role == "user":
            history_text += f"\nUser: {content}"
        elif role == "assistant":
            history_text += f"\nAssistant: {content}"

    prompt = (
        _AI_SQL_SYSTEM.format(schema=schema)
        + (f"\n\nCONVERSATION HISTORY:{history_text}" if history_text else "")
        + f"\n\nUser request: {payload.message}"
        + "\n\nRespond with ONLY the SQL query in a ```sql ... ``` block."
    )

    raw = llm.generate(prompt, max_tokens=800, _span_name="scribble.ai_sql")
    if not raw:
        raise HTTPException(status_code=500, detail="AI did not return a response. Please try again.")

    sql = _extract_sql(raw)

    # Generate a short explanation of what the query does
    explain_prompt = (
        f"In one short sentence (max 25 words), explain what this SQL query retrieves:\n\n{sql}"
    )
    explanation = llm.generate(explain_prompt, max_tokens=60, _span_name="scribble.ai_sql_explain") or ""
    explanation = explanation.strip().strip('"')

    return AiSqlResponse(sql=sql, explanation=explanation)
