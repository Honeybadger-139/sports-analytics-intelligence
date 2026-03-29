"""
run_prediction_generation.py — Daily ML prediction generation Cloud Run Job

Generates win-probability predictions + SHAP explanations for:
  1. All upcoming games for today (pre-game predictions)
  2. Any completed games that are missing predictions (backfill gap-fill)

Optionally force-refreshes all predictions for a season when called with
--force-refresh (used after a model retrain to replace stale predictions).

Usage:
    python pipeline/run_prediction_generation.py
    python pipeline/run_prediction_generation.py --season 2025-26
    python pipeline/run_prediction_generation.py --season 2025-26 --force-refresh
    python pipeline/run_prediction_generation.py --all-seasons --force-refresh

Schedule: Daily 03:00 IST (21:30 UTC) via Cloud Scheduler
          Runs AFTER the nightly ingestion + feature store jobs.
          On Mondays, runs AFTER the weekly model training job.

Pipeline order:
    Raw ingestion → Feature store → [Model training (Mon only)] → Prediction generation
"""

import argparse
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ALL_SEASONS = ["2023-24", "2024-25", "2025-26"]


def _generate_for_season(season: str, force_refresh: bool, max_games: int) -> dict:
    """Generate / backfill predictions for a single season."""
    from src.data.db import get_engine
    from src.api.routes import _bootstrap_predictions_from_completed_games
    from src.data.prediction_store import sync_prediction_outcomes
    from sqlalchemy.orm import Session

    engine = get_engine()
    with Session(engine) as db:
        logger.info(
            "🔮 Generating predictions | season=%s | force_refresh=%s | max_games=%d",
            season,
            force_refresh,
            max_games,
        )
        result = _bootstrap_predictions_from_completed_games(
            db,
            season=season,
            max_games=max_games,
            force_refresh=force_refresh,
        )
        db.commit()

        logger.info(
            "   Scanned: %d | Bootstrapped: %d | Rows persisted: %d | Errors: %d",
            result.get("scanned_games", 0),
            result.get("games_bootstrapped", 0),
            result.get("persisted_rows", 0),
            result.get("errors", 0),
        )

        # Sync was_correct outcomes for evaluated games
        try:
            sync_prediction_outcomes(db, season=season)
            db.commit()
            logger.info("   ✅ Outcomes synced for season %s", season)
        except Exception as exc:
            logger.warning("   ⚠️  Outcome sync failed for season %s: %s", season, exc)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate NBA win-probability predictions and SHAP factors")
    parser.add_argument(
        "--season",
        default=None,
        help="Target season (e.g. 2025-26). Defaults to current season from config.",
    )
    parser.add_argument(
        "--all-seasons",
        action="store_true",
        help="Generate predictions for all seasons (2023-24, 2024-25, 2025-26).",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Delete and regenerate all predictions for the target season(s). "
             "Use after model retraining to replace stale predictions.",
    )
    parser.add_argument(
        "--max-games",
        type=int,
        default=1500,
        help="Maximum games to process per season (default: 1500).",
    )
    args = parser.parse_args()

    # Determine target seasons
    if args.all_seasons:
        seasons = ALL_SEASONS
    elif args.season:
        seasons = [args.season]
    else:
        from src import config
        seasons = [config.CURRENT_SEASON]

    if not os.getenv("GCS_MODELS_BUCKET"):
        logger.warning(
            "⚠️  GCS_MODELS_BUCKET not set — predictions will use locally cached models only."
        )

    total_persisted = 0
    total_errors = 0

    for season in seasons:
        try:
            result = _generate_for_season(
                season=season,
                force_refresh=args.force_refresh,
                max_games=args.max_games,
            )
            total_persisted += result.get("persisted_rows", 0)
            total_errors += result.get("errors", 0)
        except Exception as exc:
            logger.error("❌ Prediction generation failed for season %s: %s", season, exc, exc_info=True)
            total_errors += 1

    logger.info(
        "🏁 Done | Total rows persisted: %d | Total errors: %d",
        total_persisted,
        total_errors,
    )

    if total_errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
