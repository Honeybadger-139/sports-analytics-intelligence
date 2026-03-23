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
if not RAW_DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Cloud Run talks to Cloud SQL through the Cloud SQL Auth Proxy / Unix socket.
# Production DATABASE_URL values already include the socket path in the
# `host=` query parameter, so we keep the URL as-is when we detect that shape
# and only fall back to the local development URL when no Cloud SQL host is set.
def _resolve_database_url(database_url: str) -> str:
    parsed = urlparse(database_url)
    if parsed.scheme.startswith("postgresql") and "cloudsql" in database_url:
        return database_url
    return database_url


DATABASE_URL = _resolve_database_url(RAW_DATABASE_URL)

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=5,           # Max 5 persistent connections
    max_overflow=10,       # Up to 10 additional on demand
    pool_timeout=30,       # Wait 30s for a connection before error
    pool_recycle=1800,     # Recycle connections every 30 min
    pool_pre_ping=True,    # Test connection health before use (avoids stale conn errors)
    echo=False,            # Set True for SQL query logging (debug)
)

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
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
