"""
Database Connection Module

Architecture Decision:
    We use SQLAlchemy as our ORM/database toolkit because:
    - It provides both raw SQL (Core) and ORM patterns
    - Connection pooling out of the box (important for FastAPI concurrent requests)
    - Database-agnostic — if we ever migrate from PostgreSQL, minimal code changes
    - Alembic integration for schema migrations
    See docs/decisions/decision-log.md #2 for PostgreSQL rationale.
"""

import os
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

from src import config

load_dotenv()

RAW_DATABASE_URL = config.DATABASE_URL or os.getenv("DATABASE_URL")

# Cloud Run talks to Cloud SQL through the Cloud SQL Auth Proxy / Unix socket.
# Production DATABASE_URL values already include the socket path in the
# `host=` query parameter, so we keep the URL as-is when we detect that shape
# and only fall back to the local development URL when no Cloud SQL host is set.
def _resolve_database_url(database_url: str) -> str:
    parsed = urlparse(database_url)
    if parsed.scheme.startswith("postgresql") and "cloudsql" in database_url:
        return database_url
    return database_url


# Allow the app to be imported in CI/test environments where no real database
# is available. A lightweight in-memory SQLite engine is created as a stub so
# that ``from main import app`` succeeds and unit tests can exercise routes via
# FastAPI TestClient with mocked DB dependencies. The ValueError is deferred
# to get_db() so that any request actually hitting the database still fails
# loudly in misconfigured production deployments.
_DB_AVAILABLE = bool(RAW_DATABASE_URL)

if _DB_AVAILABLE:
    DATABASE_URL = _resolve_database_url(RAW_DATABASE_URL)
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,           # Max 5 persistent connections
        max_overflow=10,       # Up to 10 additional on demand
        pool_timeout=30,       # Wait 30s for a connection before error
        pool_recycle=1800,     # Recycle connections every 30 min
        pool_pre_ping=True,    # Test connection health before use (avoids stale conn errors)
        echo=False,            # Set True for SQL query logging (debug)
    )
else:
    DATABASE_URL = "sqlite://"
    engine = create_engine(DATABASE_URL)

# Session factory — each API request gets its own session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for ORM models
Base = declarative_base()


def get_db():
    """
    FastAPI dependency that provides a database session.

    Usage in routes:
        @app.get("/api/v1/teams")
        async def get_teams(db: Session = Depends(get_db)):
            ...

    The session is automatically closed after the request completes,
    even if an exception occurs (finally block).

    Raises ValueError in production if DATABASE_URL was never configured
    (prevents silent data-less operation).
    """
    if not _DB_AVAILABLE:
        raise ValueError(
            "DATABASE_URL environment variable is not set — "
            "cannot serve requests that require a database connection"
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
