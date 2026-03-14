"""
Runtime Configuration Store
=============================

Wave 3: Provides a DB-backed key/value store for runtime configuration flags.
This replaces hardcoded environment variables for values that need to change
at runtime without a service restart.

The app_config table has columns:
    key         VARCHAR PRIMARY KEY
    value       TEXT
    description TEXT
    updated_at  TIMESTAMP

Supported operations:
    get_config(engine, key)             → str | None
    set_config(engine, key, value, ...)
    list_configs(engine)                → list[dict]
    delete_config(engine, key)          → bool

🎓 WHY DB-BACKED CONFIG?
    Environment variables require a restart to change. A DB config table
    can be updated via API (PATCH /api/v1/admin/config/{key}) and takes
    effect immediately without downtime.

    Use cases:
    - Toggle feature flags without redeploy (A/B tests)
    - Adjust thresholds without code changes (Brier threshold, RAG similarity)
    - Switch active model artifact path for instant rollback
    - Control PSI drift alert sensitivity

💡 INTERVIEW ANGLE:
    Junior: "I use env vars for everything."
    Senior: "I differentiate between static config (DB credentials, API keys —
    env vars, secrets manager) and dynamic operational config (thresholds,
    feature flags — DB config table). The DB config can be patched via a
    secured admin API and cached with a short TTL to avoid hot-path DB queries."

Wave 3 — SCR-298
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def get_config(engine: Engine, key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Read a single config value from app_config.

    Returns `default` if the key does not exist or on DB error.
    """
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT value FROM app_config WHERE key = :key"),
                {"key": key},
            ).fetchone()
        return row[0] if row else default
    except Exception as exc:
        logger.warning("[runtime_config] get_config('%s') failed: %s", key, exc)
        return default


def get_config_float(engine: Engine, key: str, default: float) -> float:
    """Convenience wrapper that parses the value as float."""
    raw = get_config(engine, key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("[runtime_config] Cannot parse '%s'='%s' as float — using default %.4f", key, raw, default)
        return default


def get_config_int(engine: Engine, key: str, default: int) -> int:
    """Convenience wrapper that parses the value as int."""
    raw = get_config(engine, key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("[runtime_config] Cannot parse '%s'='%s' as int — using default %d", key, raw, default)
        return default


def set_config(
    engine: Engine,
    key: str,
    value: str,
    description: Optional[str] = None,
) -> bool:
    """
    Upsert a config value.

    Returns True on success, False on error.
    """
    try:
        with engine.begin() as conn:
            if description is not None:
                conn.execute(
                    text("""
                        INSERT INTO app_config (key, value, description, updated_at)
                        VALUES (:key, :value, :description, NOW())
                        ON CONFLICT (key) DO UPDATE
                            SET value = EXCLUDED.value,
                                description = COALESCE(EXCLUDED.description, app_config.description),
                                updated_at = NOW()
                    """),
                    {"key": key, "value": value, "description": description},
                )
            else:
                conn.execute(
                    text("""
                        INSERT INTO app_config (key, value, updated_at)
                        VALUES (:key, :value, NOW())
                        ON CONFLICT (key) DO UPDATE
                            SET value = EXCLUDED.value, updated_at = NOW()
                    """),
                    {"key": key, "value": value},
                )
        logger.info("✅ [runtime_config] Set %s = %s", key, value)
        return True
    except Exception as exc:
        logger.error("[runtime_config] set_config('%s') failed: %s", key, exc)
        return False


def list_configs(engine: Engine) -> List[Dict[str, Any]]:
    """
    Return all config entries as a list of dicts.
    """
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT key, value, description, updated_at, created_at
                    FROM app_config
                    ORDER BY key ASC
                """)
            ).fetchall()
        return [
            {
                "key": r[0],
                "value": r[1],
                "description": r[2],
                "updated_at": r[3].isoformat() if r[3] else None,
                "created_at": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error("[runtime_config] list_configs failed: %s", exc)
        return []


def delete_config(engine: Engine, key: str) -> bool:
    """
    Delete a config key. Returns True if the row existed and was deleted.
    """
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("DELETE FROM app_config WHERE key = :key RETURNING key"),
                {"key": key},
            )
            deleted = result.fetchone() is not None
        if deleted:
            logger.info("🗑️  [runtime_config] Deleted config key: %s", key)
        else:
            logger.info("[runtime_config] Key '%s' not found — nothing deleted.", key)
        return deleted
    except Exception as exc:
        logger.error("[runtime_config] delete_config('%s') failed: %s", key, exc)
        return False
