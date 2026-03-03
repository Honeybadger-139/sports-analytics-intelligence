"""
Daily pipeline scheduler — Sports Analytics Intelligence Platform
=================================================================

Runs the full NBA data ingestion pipeline on a daily cron schedule so that
raw tables never go stale.

Usage
-----
1. Embedded (automatic): the FastAPI app starts this scheduler via its
   lifespan context manager.  No manual action needed.

2. Catch-up / one-shot run (manual):
       cd backend
       python scheduler.py --run-now

   Use this to immediately backfill both the 2024-25 historical season and
   the current 2025-26 season from the last watermark date.

3. Standalone daemon (alternative deployment without FastAPI):
       cd backend
       python scheduler.py
   Runs forever, firing at PIPELINE_SCHEDULE_HOUR:PIPELINE_SCHEDULE_MINUTE UTC.

Design notes
------------
- APScheduler BackgroundScheduler runs in a daemon thread — it does not
  block the FastAPI async event loop.
- misfire_grace_time=3600 means if the server was down at the scheduled
  time, the job fires as soon as it comes back up (within 1 hour).
- All run outcomes are recorded to the existing pipeline_audit table via
  record_audit() so /api/v1/system/status reflects the last run.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


def _setup_standalone_logging() -> None:
    """Configure logging for standalone (non-FastAPI) execution."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run_pipeline_job() -> None:
    """
    Scheduled job entry point.

    Calls run_full_ingestion for every season in config.PIPELINE_SEASONS.
    Failures are caught and logged so the scheduler thread never crashes.
    """
    # Import inside the function to avoid circular imports when this module
    # is imported by main.py before the rest of the app is initialised.
    from src import config
    from src.data.ingestion import run_full_ingestion

    started_at = datetime.now(timezone.utc)
    logger.info(
        "⏰ [scheduler] Daily pipeline triggered at %s UTC for seasons: %s",
        started_at.isoformat(timespec="seconds"),
        config.PIPELINE_SEASONS,
    )
    try:
        run_full_ingestion(seasons=config.PIPELINE_SEASONS)
        logger.info("✅ [scheduler] Daily pipeline completed successfully.")
    except Exception as exc:
        logger.error(
            "❌ [scheduler] Daily pipeline failed: %s",
            exc,
            exc_info=True,
        )


def run_rag_ingestion_job() -> None:
    """
    Force-refresh the RAG vector store from live RSS feeds.

    Unlike IntelligenceService._refresh_index_if_needed() which skips
    re-fetching when ChromaDB already has documents, this job ALWAYS
    fetches fresh articles and upserts them — ensuring the vector store
    never goes stale regardless of its current size.

    Schedule: 3× daily (07:00, 15:00, 23:00 UTC) so sports news, injury
    reports, and game previews are never more than ~8 hours old.
    """
    from src import config
    from src.data.db import SessionLocal
    from src.data.intelligence_audit_store import record_intelligence_audit
    from src.intelligence.embeddings import EmbeddingClient
    from src.intelligence.news_agent import chunk_context_document, fetch_context_documents_with_health
    from src.intelligence.vector_store import VectorStore

    started_at = datetime.now(timezone.utc)
    logger.info(
        "📰 [rag-scheduler] RAG ingestion triggered at %s UTC",
        started_at.isoformat(timespec="seconds"),
    )

    sources = config.INTELLIGENCE_SOURCES + config.INJURY_SOURCES
    db = SessionLocal()
    try:
        docs, health = fetch_context_documents_with_health(
            sources=sources,
            timeout_seconds=config.RAG_REQUEST_TIMEOUT_SECONDS,
            max_items_per_feed=40,
        )
        logger.info(
            "📰 [rag-scheduler] Fetched %d raw documents from %d sources",
            len(docs), len(sources),
        )

        if not docs:
            logger.warning("📰 [rag-scheduler] No documents fetched — feeds may be unreachable.")
            record_intelligence_audit(
                db.get_bind(),
                module="rag_scheduler",
                status="degraded",
                records_processed=0,
                errors="No context documents fetched from RSS sources",
                details={"sources": sources, "feed_health": health},
            )
            return

        embedding_client = EmbeddingClient()
        vector_store = VectorStore()

        payload = []
        for doc in docs:
            for chunk in chunk_context_document(doc):
                content = f"{chunk.title}. {chunk.content}".strip()
                payload.append({
                    "doc_id": chunk.doc_id,
                    "source": chunk.source,
                    "title": chunk.title,
                    "url": chunk.url,
                    "published_at": chunk.published_at.isoformat(),
                    "team_tags": chunk.team_tags,
                    "player_tags": chunk.player_tags,
                    "content": content,
                    "embedding": embedding_client.embed_document(content),
                })

        inserted = vector_store.upsert(payload)
        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        logger.info(
            "✅ [rag-scheduler] Upserted %d chunks into ChromaDB in %.1fs | store total: %d",
            inserted, elapsed, vector_store.count(),
        )
        record_intelligence_audit(
            db.get_bind(),
            module="rag_scheduler",
            status="success",
            records_processed=inserted,
            details={
                "sources": sources,
                "store_count": vector_store.count(),
                "feed_health": health,
                "elapsed_seconds": round(elapsed, 2),
            },
        )
    except Exception as exc:
        logger.error("❌ [rag-scheduler] RAG ingestion failed: %s", exc, exc_info=True)
    finally:
        db.close()


def create_scheduler() -> BackgroundScheduler:
    """
    Build and return a configured BackgroundScheduler.

    Jobs registered:
      1. daily_nba_pipeline   — full NBA data ingestion once per day
      2. rag_ingestion_*      — RSS feed → ChromaDB refresh 3× per day
                                (07:00, 15:00, 23:00 UTC)

    The scheduler is NOT started here — call .start() after FastAPI has
    finished its own startup, or call it from the lifespan context manager.
    """
    from src import config

    scheduler = BackgroundScheduler(timezone="UTC")

    # ── Job 1: Daily NBA data ingestion ─────────────────────────────────────
    scheduler.add_job(
        func=run_pipeline_job,
        trigger=CronTrigger(
            hour=config.PIPELINE_SCHEDULE_HOUR,
            minute=config.PIPELINE_SCHEDULE_MINUTE,
            timezone="UTC",
        ),
        id="daily_nba_pipeline",
        name=f"Daily NBA ingestion ({', '.join(config.PIPELINE_SEASONS)})",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info(
        "🗓️  [scheduler] Configured: daily NBA pipeline at %02d:%02d UTC | seasons: %s",
        config.PIPELINE_SCHEDULE_HOUR,
        config.PIPELINE_SCHEDULE_MINUTE,
        config.PIPELINE_SEASONS,
    )

    # ── Job 2: RAG ingestion — 3× daily (07:00, 15:00, 23:00 UTC) ──────────
    # Runs every ~8 hours so injury reports and news are never stale.
    # Force-upserts into ChromaDB regardless of current store size (fixes the
    # one-time-only initialisation limitation in _refresh_index_if_needed).
    for hour, label in [(7, "morning"), (15, "afternoon"), (23, "evening")]:
        scheduler.add_job(
            func=run_rag_ingestion_job,
            trigger=CronTrigger(hour=hour, minute=0, timezone="UTC"),
            id=f"rag_ingestion_{label}",
            name=f"RAG feed refresh — {label} ({hour:02d}:00 UTC)",
            replace_existing=True,
            misfire_grace_time=1800,
        )
    logger.info(
        "📰 [scheduler] Configured: RAG ingestion at 07:00, 15:00, 23:00 UTC (3× daily)"
    )

    return scheduler


# ── Standalone entry point ──────────────────────────────────────────────────

if __name__ == "__main__":
    _setup_standalone_logging()

    # Ensure src package is importable when run from the backend/ directory.
    import os
    sys.path.insert(0, os.path.dirname(__file__))

    parser = argparse.ArgumentParser(
        description="SAI daily pipeline scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Immediate catch-up run for all PIPELINE_SEASONS, then exit
  python scheduler.py --run-now

  # Start daemon that fires every day at PIPELINE_SCHEDULE_HOUR UTC
  python scheduler.py
        """,
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Trigger the pipeline immediately (catch-up run) then exit.",
    )
    args = parser.parse_args()

    if args.run_now:
        logger.info("🚀 [scheduler] --run-now: triggering immediate catch-up ingestion...")
        run_pipeline_job()
        logger.info("✅ [scheduler] Catch-up run complete. Exiting.")
        sys.exit(0)

    # ── Daemon mode ──
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("✅ [scheduler] Daemon started. Press Ctrl-C to stop.")
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("🛑 [scheduler] Daemon stopped.")
