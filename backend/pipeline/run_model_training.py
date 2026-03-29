"""
run_model_training.py — Weekly ML model training Cloud Run Job (SCR-349 MLOps pipeline)

Trains XGBoost, LightGBM, and Logistic Regression on all completed seasons,
saves artifacts to GCS (gs://gamethread-models/), and uploads version metadata.

Usage:
    python pipeline/run_model_training.py
    python pipeline/run_model_training.py --training-season 2024-25 --validation-season 2025-26

Schedule: Every Monday 03:00 IST (21:30 UTC Sunday) via Cloud Scheduler
          Runs AFTER the nightly ingestion and feature store jobs.

Why weekly (not daily)?
    XGBoost/LightGBM are batch learners — there is no incremental update.
    Weekly retraining on a growing dataset gives ~50 new labelled examples per
    run, which is a meaningful update without risk of overfitting to a very
    short recent window.
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

# Ensure the backend package root is on the path when running as a Cloud Run Job
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main() -> None:
    parser = argparse.ArgumentParser(description="Train NBA win-probability models")
    parser.add_argument(
        "--training-season",
        default="2024-25",
        help="Primary training season (default: 2024-25). All completed games from this season are used.",
    )
    parser.add_argument(
        "--validation-season",
        default=None,
        help="Season used for hold-out validation (default: current season from config).",
    )
    parser.add_argument(
        "--cutoff-date",
        default=None,
        help="ISO date (YYYY-MM-DD). Only games before this date are used for training. "
             "Useful to prevent data leakage when validating against recent games.",
    )
    args = parser.parse_args()

    # Confirm GCS bucket is configured
    bucket = os.getenv("GCS_MODELS_BUCKET")
    if not bucket:
        logger.error(
            "❌ GCS_MODELS_BUCKET env var not set. "
            "Models will be saved locally only and will not persist across Cloud Run restarts."
        )
    else:
        logger.info("📦 GCS bucket: gs://%s", bucket)

    logger.info(
        "🏀 Training season: %s | Validation season: %s | Cutoff: %s",
        args.training_season,
        args.validation_season or "current (from config)",
        args.cutoff_date or "none",
    )

    from src.models.trainer import run_training_pipeline

    try:
        run_training_pipeline(
            season=args.training_season,
            cutoff_date=args.cutoff_date,
            validation_season=args.validation_season,
        )
        logger.info("✅ Model training pipeline completed successfully.")
    except Exception as exc:
        logger.error("❌ Model training pipeline failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
