"""
Daily pipeline scheduler — Sports Analytics Intelligence Platform
=================================================================

Three job classes run automatically when the FastAPI server starts:

  1. daily_nba_pipeline  — raw NBA data ingestion (06:30 UTC = 12:00 PM IST)
                           immediately followed by feature-engineering so that
                           match_features is never stale after an ingestion run.

  2. daily_feature_engineering — standalone feature rebuild (07:30 UTC) as a
                           safety net in case the pipeline job's chained run
                           was skipped (e.g. partial ingestion failure).

  3. rag_refresh_<HH>    — RAG vector-store refresh 4× daily (every 6 hours:
                           00:00, 06:00, 12:00, 18:00 UTC = 05:30, 11:30,
                           17:30, 23:30 IST).  The 06:00 UTC slot fires
                           30 minutes BEFORE the data pipeline so that news /
                           injury context is fresh when the brief is generated.

IST time mapping (IST = UTC + 5:30)
  06:30 UTC → 12:00 PM IST  raw ingestion + features
  07:30 UTC → 13:00 PM IST  feature safety-net
  00:00 UTC → 05:30 IST     RAG refresh
  06:00 UTC → 11:30 IST     RAG refresh (just before data pipeline)
  12:00 UTC → 17:30 IST     RAG refresh
  18:00 UTC → 23:30 IST     RAG refresh

Usage
-----
1. Embedded (automatic): the FastAPI app starts this scheduler via its
   lifespan context manager.  No manual action needed.

2. Immediate catch-up run:
       cd backend
       python scheduler.py --run-now

   Runs ingestion + features immediately, then exits.

3. Features-only catch-up:
       python scheduler.py --run-now-features

4. RAG-only immediate refresh:
       python scheduler.py --run-now-rag

5. Standalone daemon (without FastAPI):
       python scheduler.py

Design notes
------------
- APScheduler BackgroundScheduler runs in a daemon thread — it does not
  block the FastAPI async event loop.
- misfire_grace_time=3600 means if the server was down at the scheduled
  time, the job fires as soon as it comes back up (within 1 hour).
- All outcomes are written to pipeline_audit / intelligence_audit tables
  so /api/v1/system/status and /api/v1/mlops/monitoring reflect them.
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


# ── Job 1: Raw ingestion + chained feature engineering ──────────────────────

def run_pipeline_job() -> None:
    """
    Scheduled job: full NBA data ingestion followed immediately by feature
    engineering.

    Chaining features here (rather than scheduling them separately) ensures
    match_features is always rebuilt with the freshest raw data.  A separate
    safety-net job (daily_feature_engineering at 07:30 UTC) handles the rare
    case where ingestion succeeds but this chained call fails.

    Fires at: 06:30 UTC = 12:00 PM IST daily.
    """
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
        logger.info("✅ [scheduler] Raw ingestion completed — starting feature engineering.")
    except Exception as exc:
        logger.error(
            "❌ [scheduler] Raw ingestion failed: %s — feature engineering will be skipped for this run.",
            exc,
            exc_info=True,
        )
        return  # do not run features on stale/partial data

    # Chain feature engineering immediately so match_features is fresh.
    run_feature_engineering_job(context="chained-after-ingestion")


# ── Job 2: Feature engineering (standalone / safety-net) ────────────────────

def run_feature_engineering_job(context: str = "scheduled") -> None:
    """
    Rebuild all feature-store tables (match_features) from current raw data.

    Called in two ways:
      • Chained from run_pipeline_job() after ingestion succeeds.
      • As a standalone scheduled safety-net at 07:30 UTC (daily_feature_engineering).

    Fires standalone at: 07:30 UTC = 13:00 IST daily.
    """
    from src import config
    from src.data.feature_store import run_feature_engineering

    started_at = datetime.now(timezone.utc)
    logger.info(
        "🔧 [scheduler] Feature engineering triggered at %s UTC [%s] for seasons: %s",
        started_at.isoformat(timespec="seconds"),
        context,
        config.PIPELINE_SEASONS,
    )
    try:
        run_feature_engineering(seasons=config.PIPELINE_SEASONS)
        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        logger.info(
            "✅ [scheduler] Feature engineering completed in %.1fs [%s].",
            elapsed,
            context,
        )
    except Exception as exc:
        logger.error(
            "❌ [scheduler] Feature engineering failed [%s]: %s",
            context,
            exc,
            exc_info=True,
        )


# ── Job 3: RAG / Intelligence vector-store refresh ──────────────────────────

def run_rag_ingestion_job() -> None:
    """
    Force-refresh the RAG vector store from live RSS feeds.

    Unlike IntelligenceService._refresh_index_if_needed() which skips
    re-fetching when ChromaDB already has documents, this job ALWAYS fetches
    fresh articles and upserts them so injury reports / game previews never
    go stale.

    Fires at: 00:00, 06:00, 12:00, 18:00 UTC (every 6 hours).
    IST equivalents: 05:30, 11:30, 17:30, 23:30.
    The 06:00 UTC slot fires 30 minutes before the data pipeline ensuring
    intelligence context is fresh when the daily brief is generated.
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

        upsert_stats = vector_store.upsert_with_stats(payload)
        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        logger.info(
            "✅ [rag-scheduler] Upserted %d chunks into ChromaDB in %.1fs | new=%d updated=%d | store total: %d",
            upsert_stats["processed"], elapsed, upsert_stats["created"], upsert_stats["updated"], vector_store.count(),
        )
        record_intelligence_audit(
            db.get_bind(),
            module="rag_scheduler",
            status="success",
            records_processed=upsert_stats["processed"],
            details={
                "sources": sources,
                "store_count": vector_store.count(),
                "feed_health": health,
                "elapsed_seconds": round(elapsed, 2),
                "upsert": upsert_stats,
            },
        )
    except Exception as exc:
        logger.error("❌ [rag-scheduler] RAG ingestion failed: %s", exc, exc_info=True)
    finally:
        db.close()


# ── Scheduler factory ────────────────────────────────────────────────────────

def create_scheduler() -> BackgroundScheduler:
    """
    Build and return a configured BackgroundScheduler.

    Jobs registered
    ───────────────
    daily_nba_pipeline         Raw ingestion + chained features
                               06:30 UTC (12:00 PM IST)  — configurable via
                               PIPELINE_SCHEDULE_HOUR / PIPELINE_SCHEDULE_MINUTE

    daily_feature_engineering  Feature safety-net (standalone rebuild)
                               07:30 UTC (13:00 IST)

    rag_refresh_00, _06, _12, _18
                               RAG vector-store refresh every 6 hours
                               00:00, 06:00, 12:00, 18:00 UTC
                               (05:30, 11:30, 17:30, 23:30 IST)
                               Configurable via RAG_SCHEDULE_HOURS env var.

    The scheduler is NOT started here — call .start() from the lifespan
    context manager or from standalone daemon mode.
    """
    from src import config

    scheduler = BackgroundScheduler(timezone="UTC")

    # ── Job 1: Daily NBA raw ingestion + chained feature engineering ─────────
    scheduler.add_job(
        func=run_pipeline_job,
        trigger=CronTrigger(
            hour=config.PIPELINE_SCHEDULE_HOUR,
            minute=config.PIPELINE_SCHEDULE_MINUTE,
            timezone="UTC",
        ),
        id="daily_nba_pipeline",
        name=(
            f"Daily NBA ingestion + features "
            f"({config.PIPELINE_SCHEDULE_HOUR:02d}:{config.PIPELINE_SCHEDULE_MINUTE:02d} UTC"
            f" = {(config.PIPELINE_SCHEDULE_HOUR + 5) % 24:02d}:{(config.PIPELINE_SCHEDULE_MINUTE + 30) % 60:02d} IST"
            f" | {', '.join(config.PIPELINE_SEASONS)})"
        ),
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info(
        "🗓️  [scheduler] daily_nba_pipeline: %02d:%02d UTC = %02d:%02d IST | seasons: %s",
        config.PIPELINE_SCHEDULE_HOUR,
        config.PIPELINE_SCHEDULE_MINUTE,
        (config.PIPELINE_SCHEDULE_HOUR + 5) % 24,
        (config.PIPELINE_SCHEDULE_MINUTE + 30) % 60,
        config.PIPELINE_SEASONS,
    )

    # ── Job 2: Standalone feature engineering safety-net (07:30 UTC) ─────────
    # Fires 60 minutes after the default ingestion time.  If ingestion ran
    # fine the chained call already rebuilt features; this job is a no-op in
    # the happy path but ensures features are current even after a partial run.
    feature_hour   = config.PIPELINE_SCHEDULE_HOUR
    feature_minute = config.PIPELINE_SCHEDULE_MINUTE + 60  # shift by 60 min
    if feature_minute >= 60:
        feature_hour   = (feature_hour + feature_minute // 60) % 24
        feature_minute = feature_minute % 60

    scheduler.add_job(
        func=run_feature_engineering_job,
        trigger=CronTrigger(
            hour=feature_hour,
            minute=feature_minute,
            timezone="UTC",
        ),
        id="daily_feature_engineering",
        name=(
            f"Feature engineering safety-net "
            f"({feature_hour:02d}:{feature_minute:02d} UTC)"
        ),
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info(
        "🔧 [scheduler] daily_feature_engineering (safety-net): %02d:%02d UTC",
        feature_hour,
        feature_minute,
    )

    # ── Job 3: RAG vector-store refresh — every 6 hours ──────────────────────
    rag_hours = config.RAG_SCHEDULE_HOURS  # default: [0, 6, 12, 18]
    slot_labels = {0: "midnight", 6: "morning", 12: "noon", 18: "evening"}

    for hour in rag_hours:
        label = slot_labels.get(hour, f"{hour:02d}h")
        ist_hour   = (hour + 5) % 24
        ist_minute = 30  # IST = UTC + 5:30
        scheduler.add_job(
            func=run_rag_ingestion_job,
            trigger=CronTrigger(hour=hour, minute=0, timezone="UTC"),
            id=f"rag_refresh_{hour:02d}",
            name=f"RAG refresh — {label} ({hour:02d}:00 UTC = {ist_hour:02d}:{ist_minute:02d} IST)",
            replace_existing=True,
            misfire_grace_time=1800,
        )

    ist_slots = [f"{(h + 5) % 24:02d}:30 IST" for h in rag_hours]
    logger.info(
        "📰 [scheduler] rag_refresh: %s UTC  (%s)  — every 6 hours",
        ", ".join(f"{h:02d}:00" for h in rag_hours),
        ", ".join(ist_slots),
    )

    return scheduler


# ── Standalone entry point ───────────────────────────────────────────────────

if __name__ == "__main__":
    _setup_standalone_logging()

    import os
    sys.path.insert(0, os.path.dirname(__file__))

    parser = argparse.ArgumentParser(
        description="SAI pipeline scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Immediate ingestion + features catch-up run, then exit
  python scheduler.py --run-now

  # Features-only rebuild (skip ingestion)
  python scheduler.py --run-now-features

  # RAG vector-store refresh only, then exit
  python scheduler.py --run-now-rag

  # Start daemon (all jobs fire on their cron schedule)
  python scheduler.py
        """,
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Trigger ingestion + feature engineering immediately, then exit.",
    )
    parser.add_argument(
        "--run-now-features",
        action="store_true",
        help="Trigger feature engineering immediately (no ingestion), then exit.",
    )
    parser.add_argument(
        "--run-now-rag",
        action="store_true",
        help="Trigger RAG vector-store refresh immediately, then exit.",
    )
    args = parser.parse_args()

    if args.run_now:
        logger.info("🚀 [scheduler] --run-now: triggering immediate ingestion + features...")
        run_pipeline_job()
        logger.info("✅ [scheduler] Catch-up run complete. Exiting.")
        sys.exit(0)

    if args.run_now_features:
        logger.info("🔧 [scheduler] --run-now-features: rebuilding features only...")
        run_feature_engineering_job(context="manual-run-now-features")
        logger.info("✅ [scheduler] Feature rebuild complete. Exiting.")
        sys.exit(0)

    if args.run_now_rag:
        logger.info("📰 [scheduler] --run-now-rag: triggering immediate RAG refresh...")
        run_rag_ingestion_job()
        logger.info("✅ [scheduler] RAG refresh complete. Exiting.")
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
