"""
Prefect orchestration for feature engineering.

This module wraps the existing SQL-based feature engineering functions with
Prefect tasks so the pipeline can run with task-level retries and cleaner
operational visibility while reusing the exact same feature computation logic.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List

import httpx
from prefect import flow, task
from prefect.tasks import exponential_backoff
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flows.data_contracts import FeatureContract, IngestionContract
from src import config
from src.data import feature_store

logger = logging.getLogger(__name__)
INGESTION_CONTRACT = IngestionContract()
FEATURE_CONTRACT = FeatureContract()


def _resolve_database_url() -> str:
    database_url = config.DATABASE_URL or os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    return database_url


def _resolve_engine(engine_or_url: Any):
    if hasattr(engine_or_url, "connect"):
        return engine_or_url
    database_url = str(engine_or_url or "").strip()
    if not database_url:
        database_url = _resolve_database_url()
    return create_engine(database_url, pool_pre_ping=True)


def _season_list(seasons: List[str] | None) -> List[str]:
    if seasons:
        return seasons
    return [config.CURRENT_SEASON]


def _publish_failure_event(
    run_id: str,
    gcs_prefix: str,
    seasons: list[str],
    error: str,
    error_traceback: str,
) -> None:
    project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    topic_name = os.getenv("PUBSUB_PIPELINE_TOPIC", "pipeline-events")
    if not project_id:
        logger.warning("Skipping feature-engineering failure event publish: GCP project is unset")
        return

    try:
        from google.cloud import pubsub_v1
    except Exception as exc:
        logger.warning("Skipping failure event publish: google-cloud-pubsub unavailable (%s)", exc)
        return

    payload = {
        "run_id": run_id,
        "status": "feature_engineering_failed",
        "gcs_prefix": gcs_prefix,
        "seasons": seasons,
        "error": error,
        "traceback": error_traceback,
    }
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_name)
    publisher.publish(topic_path, data=json.dumps(payload).encode("utf-8")).result(timeout=30)


def _season_feature_count(engine, season: str) -> int:
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM match_features mf
                JOIN matches m ON m.game_id = mf.game_id
                WHERE m.season = :season
                """
            ),
            {"season": season},
        )
        return int(result.scalar() or 0)


@task(
    name="Validate Raw Ingestion Data",
    retries=2,
    retry_delay_seconds=30,
    description="Asserts row counts, null rates, and date freshness before computing features",
)
def validate_raw_data(engine, seasons: list[str], run_id: str) -> Dict[str, Any]:
    resolved_engine = _resolve_engine(engine)
    summary = INGESTION_CONTRACT.validate_raw_data(resolved_engine, _season_list(seasons))
    summary["run_id"] = run_id
    return summary


@task(
    name="Compute Rolling Features",
    retries=3,
    retry_delay_seconds=exponential_backoff(backoff_factor=60),
    description="Computes win_pct, point_diff, ratings (L5/L10 rolling windows)",
)
def compute_rolling_features(engine, seasons: list[str], validated_counts: Dict[str, Any]) -> int:
    resolved_engine = _resolve_engine(engine)
    total_rows = 0
    for season in _season_list(seasons):
        total_rows += int(feature_store.compute_features(resolved_engine, season=season) or 0)
    logger.info(
        "Computed rolling features for %s season(s); raw_matches=%s rows=%s",
        len(_season_list(seasons)),
        validated_counts.get("matches"),
        total_rows,
    )
    return total_rows


@task(
    name="Compute H2H Features",
    retries=3,
    retry_delay_seconds=exponential_backoff(backoff_factor=60),
    description="Computes head-to-head win%, margin, data_available flag",
)
def compute_h2h_features(engine, seasons: list[str]) -> int:
    resolved_engine = _resolve_engine(engine)
    total_rows = 0
    for season in _season_list(seasons):
        feature_store.compute_h2h_features(resolved_engine, season=season)
        total_rows += _season_feature_count(resolved_engine, season)
    return total_rows


@task(
    name="Compute Rest and Fatigue Features",
    retries=2,
    retry_delay_seconds=60,
    description="Computes days_rest, is_back_to_back, current_streak",
)
def compute_rest_features(engine, seasons: list[str]) -> int:
    resolved_engine = _resolve_engine(engine)
    total_rows = 0
    for season in _season_list(seasons):
        feature_store.compute_streak_features(resolved_engine, season=season)
        total_rows += _season_feature_count(resolved_engine, season)
    return total_rows


@task(
    name="Validate Feature Output",
    retries=1,
    description="Asserts feature rows match raw rows, no NaN in critical columns",
)
def validate_feature_output(engine, seasons: list[str], expected_count: int) -> bool:
    resolved_engine = _resolve_engine(engine)
    seasons = _season_list(seasons)
    FEATURE_CONTRACT.validate_feature_output(
        resolved_engine,
        seasons,
        expected_match_count=expected_count,
    )
    logger.info("Feature output validation passed for %s season(s).", len(seasons))
    return True


@task(
    name="Write Pipeline Audit",
    description="Records pipeline run status, counts, and elapsed time to pipeline_audit table",
)
def write_pipeline_audit(engine, run_id: str, status: str, details: Dict[str, Any]) -> None:
    resolved_engine = _resolve_engine(engine)
    feature_store.record_audit(
        resolved_engine,
        module="prefect_feature_engineering",
        status=status,
        processed=int(details.get("feature_rows", 0) or 0),
        inserted=int(details.get("feature_rows", 0) or 0),
        errors=details.get("error"),
        details={"run_id": run_id, **details},
    )


@task(
    name="Trigger Prediction Refresh",
    retries=3,
    retry_delay_seconds=30,
    description="POSTs to API to refresh predictions for newly featured games",
)
def trigger_prediction_refresh(api_base_url: str, features_written: int) -> Dict[str, Any]:
    if features_written <= 0:
        return {"triggered": False, "reason": "no_features_written"}

    endpoint = f"{api_base_url.rstrip('/')}/api/v1/predictions/today?persist=true"
    with httpx.Client(timeout=30.0) as client:
        response = client.post(endpoint)
        if response.status_code in {404, 405}:
            response = client.get(endpoint)
        response.raise_for_status()

    payload: Dict[str, Any]
    try:
        payload = response.json()
    except Exception:
        payload = {"text": response.text}

    return {
        "triggered": True,
        "endpoint": endpoint,
        "status_code": response.status_code,
        "response": payload,
    }


@flow(
    name="feature-engineering-pipeline",
    description="Reads from Cloud SQL raw tables, computes match_features, writes audit",
    log_prints=True,
)
def feature_engineering_pipeline(
    run_id: str,
    gcs_prefix: str,
    seasons: list[str] = ["2025-26"],
) -> None:
    database_url = _resolve_database_url()
    engine = create_engine(database_url, pool_pre_ping=True)
    season_list = _season_list(seasons)
    api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")

    try:
        validated = validate_raw_data(engine, season_list, run_id)
        rolling_count = compute_rolling_features(engine, season_list, validated)
        h2h_count = compute_h2h_features(engine, season_list)
        rest_count = compute_rest_features(engine, season_list)
        is_valid = validate_feature_output(engine, season_list, validated["matches"])

        write_pipeline_audit(
            engine,
            run_id,
            "success",
            {
                "gcs_prefix": gcs_prefix,
                "seasons": season_list,
                "raw_matches": validated.get("matches", 0),
                "feature_rows": rolling_count,
                "rolling_rows": rolling_count,
                "h2h_rows": h2h_count,
                "rest_rows": rest_count,
                "validation_passed": is_valid,
            },
        )

        if rolling_count > 0:
            trigger_prediction_refresh(api_base_url, rolling_count)
    except Exception as exc:
        error_tb = traceback.format_exc()
        write_pipeline_audit(
            engine,
            run_id,
            "failed",
            {
                "gcs_prefix": gcs_prefix,
                "seasons": season_list,
                "error": str(exc),
                "traceback": error_tb,
            },
        )
        try:
            _publish_failure_event(run_id, gcs_prefix, season_list, str(exc), error_tb)
        except Exception as publish_exc:
            logger.warning("Failed to publish feature-engineering failure event: %s", publish_exc)
        raise


if __name__ == "__main__":
    feature_engineering_pipeline(run_id="manual", gcs_prefix="", seasons=["2025-26"])
