#!/usr/bin/env python3
"""Cloud Run Job entrypoint for raw NBA ingestion.

This job:
1. Runs the existing ingestion pipeline.
2. Snapshots today's ingested raw rows to GCS as Parquet.
3. Publishes a completion or failure event to Pub/Sub.

The script is intentionally standalone so Cloud Run Jobs can execute it without
FastAPI or the embedded APScheduler runtime.
"""

from __future__ import annotations

import io
import json
import logging
import os
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

import pandas as pd
from dotenv import load_dotenv
from google.cloud import pubsub_v1, secretmanager, storage
from sqlalchemy import create_engine, text

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("gamethread.pipeline.ingestion")


@dataclass(frozen=True)
class RuntimeConfig:
    project_id: str
    database_url: str
    raw_bucket: str
    topic_name: str
    seasons: list[str]


def log_event(event: str, level: str = "INFO", **fields: Any) -> None:
    payload = {
        "event": event,
        "level": level.upper(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    logger.log(getattr(logging, level.upper(), logging.INFO), json.dumps(payload, default=str))


def _resolve_project_id() -> str:
    project_id = (os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or "").strip()
    if not project_id:
        raise ValueError("GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT environment variable is not set")
    return project_id


def _load_secret(secret_id: str, project_id: str) -> str | None:
    client = secretmanager.SecretManagerServiceClient()
    secret_name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    try:
        response = client.access_secret_version(request={"name": secret_name})
        return response.payload.data.decode("utf-8").strip()
    except Exception as exc:
        log_event(
            "secret_lookup_failed",
            level="WARNING",
            secret_id=secret_id,
            project_id=project_id,
            error=str(exc),
        )
        return None


def _resolve_value(env_name: str, project_id: str, secret_id: str | None = None) -> str | None:
    raw = os.getenv(env_name)
    if raw and raw.strip():
        return raw.strip()
    if secret_id:
        return _load_secret(secret_id, project_id)
    return None


def load_runtime_config() -> RuntimeConfig:
    project_id = _resolve_project_id()
    database_url = _resolve_value("DATABASE_URL", project_id, "DATABASE_URL")
    raw_bucket = _resolve_value("GCS_RAW_BUCKET", project_id, "GCS_RAW_BUCKET")
    topic_name = _resolve_value("PUBSUB_PIPELINE_TOPIC", project_id, "PUBSUB_PIPELINE_TOPIC")

    if not database_url:
        raise ValueError("DATABASE_URL is required for the ingestion job")
    if not raw_bucket:
        raise ValueError("GCS_RAW_BUCKET is required for the ingestion job")
    if not topic_name:
        raise ValueError("PUBSUB_PIPELINE_TOPIC is required for the ingestion job")

    from src import config as app_config

    seasons = list(app_config.PIPELINE_SEASONS)
    app_config.DATABASE_URL = database_url

    return RuntimeConfig(
        project_id=project_id,
        database_url=database_url,
        raw_bucket=raw_bucket,
        topic_name=topic_name,
        seasons=seasons,
    )


def _build_engine(database_url: str):
    return create_engine(database_url)


def _query_snapshot(engine, table_name: str, snapshot_date: datetime.date) -> pd.DataFrame:
    """Fetch rows that belong to the ingestion date window."""
    if table_name == "matches":
        query = text(
            """
            SELECT *
            FROM matches
            WHERE game_date::date = :snapshot_date
            ORDER BY game_id
            """
        )
    elif table_name == "team_game_stats":
        query = text(
            """
            SELECT tgs.*
            FROM team_game_stats tgs
            JOIN matches m ON m.game_id = tgs.game_id
            WHERE m.game_date::date = :snapshot_date
            ORDER BY tgs.game_id, tgs.team_id
            """
        )
    elif table_name == "player_game_stats":
        query = text(
            """
            SELECT pgs.*
            FROM player_game_stats pgs
            JOIN matches m ON m.game_id = pgs.game_id
            WHERE m.game_date::date = :snapshot_date
            ORDER BY pgs.game_id, pgs.team_id, pgs.player_id
            """
        )
    else:
        raise ValueError(f"Unsupported snapshot table: {table_name}")

    with engine.connect() as conn:
        return pd.read_sql_query(query, conn, params={"snapshot_date": snapshot_date})


def _dataframe_to_parquet_bytes(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    try:
        frame.to_parquet(buffer, index=False, engine="pyarrow")
    except ImportError as exc:
        raise RuntimeError(
            "Parquet export requires pyarrow. Install backend/requirements-pipeline.txt in the job image."
        ) from exc
    buffer.seek(0)
    return buffer.getvalue()


def _upload_to_gcs(storage_client: storage.Client, bucket_name: str, object_name: str, payload: bytes) -> str:
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    blob.upload_from_string(payload, content_type="application/octet-stream")
    return f"gs://{bucket_name}/{object_name}"


def _publish_event(project_id: str, topic_name: str, payload: dict[str, Any]) -> None:
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_name)
    data = json.dumps(payload, default=str).encode("utf-8")
    publisher.publish(topic_path, data=data).result(timeout=30)


def _run() -> int:
    started_at = datetime.now(timezone.utc)
    run_id = started_at.strftime("%Y%m%d_%H%M%S")
    config = load_runtime_config()

    log_event(
        "pipeline_start",
        run_id=run_id,
        seasons=config.seasons,
        project_id=config.project_id,
        raw_bucket=config.raw_bucket,
        topic_name=config.topic_name,
    )

    from src.data import ingestion as ingestion_module

    engine = None
    try:
        engine = _build_engine(config.database_url)
        from src import config as app_config

        app_config.DATABASE_URL = config.database_url

        if not ingestion_module.check_health(engine):
            raise RuntimeError("Pre-flight health check failed")

        ingestion_module.run_full_ingestion(seasons=config.seasons)

        snapshot_date = started_at.date()
        storage_client = storage.Client(project=config.project_id)
        snapshot_prefix = f"{snapshot_date:%Y/%m/%d}"
        table_names = ["matches", "team_game_stats", "player_game_stats"]
        parquet_filenames = {
            "matches": "games.parquet",
            "team_game_stats": "team_game_stats.parquet",
            "player_game_stats": "player_game_stats.parquet",
        }
        row_counts: dict[str, int] = {}

        for table_name in table_names:
            log_event("snapshot_query_started", run_id=run_id, table=table_name, snapshot_date=snapshot_date.isoformat())
            frame = _query_snapshot(engine, table_name, snapshot_date)
            row_counts[table_name] = int(len(frame))
            parquet_bytes = _dataframe_to_parquet_bytes(frame)
            object_name = f"{snapshot_prefix}/{parquet_filenames[table_name]}"
            gcs_uri = _upload_to_gcs(storage_client, config.raw_bucket, object_name, parquet_bytes)
            log_event("snapshot_uploaded", run_id=run_id, table=table_name, rows=len(frame), gcs_uri=gcs_uri)

        completed_at = datetime.now(timezone.utc)
        success_payload = {
            "run_id": run_id,
            "status": "success",
            "seasons": config.seasons,
            "rows_ingested": row_counts,
            "gcs_prefix": f"gs://{config.raw_bucket}/{snapshot_prefix}/",
            "ingestion_completed_at": completed_at.isoformat(),
        }

        _publish_event(config.project_id, config.topic_name, success_payload)
        log_event("pipeline_success", **success_payload)
        return 0
    except Exception as exc:
        error_payload = {
            "run_id": run_id,
            "status": "failed",
            "error": str(exc),
        }
        log_event("pipeline_failed", level="ERROR", traceback=traceback.format_exc(), **error_payload)
        try:
            _publish_event(config.project_id, config.topic_name, error_payload)
        except Exception as publish_exc:
            log_event("failure_event_publish_failed", level="WARNING", error=str(publish_exc))
        return 1
    finally:
        if engine is not None:
            engine.dispose()


def main() -> None:
    raise SystemExit(_run())


if __name__ == "__main__":
    main()
