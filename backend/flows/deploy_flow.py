"""Prefect deployment registration for the feature engineering flow."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from prefect.deployments import Deployment
from prefect.infrastructure import Process

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from flows.feature_engineering_flow import feature_engineering_pipeline
except ImportError:  # pragma: no cover - supports direct script execution
    from feature_engineering_flow import feature_engineering_pipeline

logger = logging.getLogger(__name__)


deployment = Deployment.build_from_flow(
    flow=feature_engineering_pipeline,
    name="production",
    work_pool_name="cloud-run-pool",
    tags=["production", "nba", "features"],
    parameters={"seasons": ["2025-26"]},
)


if __name__ == "__main__":
    logger.info("Applying Prefect deployment: %s", deployment.name)
    deployment.apply()
