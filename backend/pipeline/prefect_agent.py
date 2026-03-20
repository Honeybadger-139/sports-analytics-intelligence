#!/usr/bin/env python3
"""
Prefect worker bootstrap for the Sports Analytics Intelligence Platform.

This module keeps the Cloud Run worker container simple:
- validate the Prefect Cloud env contract
- exec into `prefect worker start --pool cloud-run-pool`

The process stays attached to the Prefect worker command so Cloud Run can
supervise it like any other long-running service.
"""

from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv


logger = logging.getLogger("gamethread.prefect_agent")


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def _require_prefect_env() -> None:
    missing = [name for name in ("PREFECT_API_URL", "PREFECT_API_KEY") if not os.getenv(name)]
    if missing:
        logger.warning(
            "Prefect worker is starting without %s. Cloud Run should inject these via Secret Manager.",
            ", ".join(missing),
        )


def main() -> int:
    load_dotenv()
    _configure_logging()
    _require_prefect_env()

    pool_name = os.getenv("PREFECT_WORKER_POOL", "cloud-run-pool")
    logger.info("Starting Prefect worker pool: %s", pool_name)

    os.execvp("prefect", ["prefect", "worker", "start", "--pool", pool_name])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
