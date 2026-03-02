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


def create_scheduler() -> BackgroundScheduler:
    """
    Build and return a configured BackgroundScheduler.

    The scheduler is NOT started here — call .start() after FastAPI has
    finished its own startup, or call it from the lifespan context manager.
    """
    from src import config

    scheduler = BackgroundScheduler(timezone="UTC")
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
        "🗓️  [scheduler] Configured: daily pipeline at %02d:%02d UTC | seasons: %s",
        config.PIPELINE_SCHEDULE_HOUR,
        config.PIPELINE_SCHEDULE_MINUTE,
        config.PIPELINE_SEASONS,
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
