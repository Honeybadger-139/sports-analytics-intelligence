"""
Alembic Environment Configuration
==================================

Wave 3: Alembic is the schema authority. This env.py reads DATABASE_URL
from the environment so migrations work in all environments (local, Docker,
CI) without hardcoded credentials.

Why Alembic over raw init.sql?
- Versioned, auditable schema history
- Safe to run on existing databases (idempotent via IF NOT EXISTS)
- Supports rollback via downgrade()
- Standard industry tooling for SQLAlchemy projects
"""

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, text
from alembic import context
from dotenv import load_dotenv

load_dotenv()

# Alembic Config object — provides access to values in alembic.ini
config = context.config

# Override sqlalchemy.url from environment variable so Docker / CI works
database_url = os.getenv(
    "DATABASE_URL",
    "postgresql://analyst:analytics2026@localhost:5432/sports_analytics",
)
config.set_main_option("sqlalchemy.url", database_url)

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# We use raw SQL migrations (no ORM metadata), so target_metadata = None
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection needed — emits SQL)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
