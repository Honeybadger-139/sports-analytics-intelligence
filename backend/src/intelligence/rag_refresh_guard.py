"""
Best-effort guarded trigger for RAG refresh jobs.

This keeps empty-retrieval chat turns from repeatedly spamming the RSS/vector
refresh path while still allowing the assistant to request a fresh index in the
background when coverage is missing.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)

_DEFAULT_COOLDOWN_SECONDS = 15 * 60
_LOCK = threading.Lock()
_LAST_TRIGGER_AT = 0.0


def _load_refresh_job() -> Callable[[], None]:
    """Load the canonical scheduler refresh job lazily to avoid import cycles."""
    from scheduler import run_rag_ingestion_job

    return run_rag_ingestion_job


def reset_rag_refresh_guard() -> None:
    """Reset cooldown state. Intended for tests only."""
    global _LAST_TRIGGER_AT
    with _LOCK:
        _LAST_TRIGGER_AT = 0.0


def trigger_guarded_rag_refresh(
    *,
    reason: str,
    refresh_job: Callable[[], None] | None = None,
    cooldown_seconds: int = _DEFAULT_COOLDOWN_SECONDS,
) -> bool:
    """
    Start a daemon thread that runs the RAG refresh job if the cooldown allows it.

    Returns True when a refresh has been scheduled, False when the call is
    suppressed by cooldown protection.
    """
    now = time.monotonic()
    with _LOCK:
        global _LAST_TRIGGER_AT
        elapsed = now - _LAST_TRIGGER_AT
        if _LAST_TRIGGER_AT and elapsed < cooldown_seconds:
            logger.info(
                "Skipping guarded RAG refresh (%s); last trigger was %.1fs ago",
                reason,
                elapsed,
            )
            return False
        _LAST_TRIGGER_AT = now

    def _worker() -> None:
        try:
            job = refresh_job or _load_refresh_job()
            job()
            logger.info("Completed guarded RAG refresh request (%s)", reason)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning(
                "Guarded RAG refresh failed (%s): %s",
                reason,
                exc,
                exc_info=True,
            )

    thread = threading.Thread(
        target=_worker,
        name="rag-refresh-trigger",
        daemon=True,
    )
    thread.start()
    logger.info("Scheduled guarded RAG refresh (%s)", reason)
    return True
