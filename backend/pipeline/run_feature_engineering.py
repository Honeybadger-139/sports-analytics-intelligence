"""
run_feature_engineering.py — Daily feature engineering Cloud Run Job

Computes match_features (rolling averages, H2H stats, streak features) from
raw game data in player_game_stats / team_game_stats / matches.

This is step 2 of the MLOps pipeline:
    Raw ingestion → Feature engineering → [Model training (Mon)] → Prediction generation

Usage:
    python pipeline/run_feature_engineering.py
    python pipeline/run_feature_engineering.py --seasons 2023-24 2024-25 2025-26

Schedule: Daily 07:30 IST (02:00 UTC) via Cloud Scheduler, 1h after raw ingestion.
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run NBA feature engineering pipeline")
    parser.add_argument(
        "--seasons",
        nargs="+",
        default=None,
        help="Seasons to compute features for (e.g. 2023-24 2024-25 2025-26). "
             "Defaults to PIPELINE_SEASONS from config.",
    )
    args = parser.parse_args()

    from src.data.feature_store import run_feature_engineering

    seasons = args.seasons
    logger.info("🏀 Running feature engineering for seasons: %s", seasons or "config.PIPELINE_SEASONS")

    try:
        run_feature_engineering(seasons=seasons)
        logger.info("✅ Feature engineering completed successfully.")
    except Exception as exc:
        logger.error("❌ Feature engineering failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
