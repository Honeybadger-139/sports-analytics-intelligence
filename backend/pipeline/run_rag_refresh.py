"""
Cloud Run job entrypoint for the RAG refresh workflow.

This wrapper reuses the existing scheduler-based refresh logic, then snapshots
the ChromaDB directory to GCS so the vector store can be restored or audited
later. Logging is emitted as structured JSON lines for Cloud Logging.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import config

logger = logging.getLogger("rag_refresh_job")


class JsonFormatter(logging.Formatter):
    """Render every log record as a single JSON object."""

    _standard_attrs = {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in self._standard_attrs and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, sort_keys=True)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def emit(level: int, event: str, **fields) -> None:
    logger.log(level, event, extra={"event": event, **fields})


def _resolve_runtime_env() -> dict[str, str]:
    """
    Resolve the runtime environment contract for the RAG refresh job.

    Required at runtime:
    - DATABASE_URL
    - GEMINI_API_KEY
    - RAG_CHROMA_DIR
    - RAG_COLLECTION
    - INTELLIGENCE_SOURCES
    - INJURY_SOURCES
    - GCS_CHROMA_BUCKET
    """
    resolved = {
        "DATABASE_URL": os.getenv("DATABASE_URL") or (config.DATABASE_URL or ""),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY") or (config.GEMINI_API_KEY or ""),
        "RAG_CHROMA_DIR": os.getenv("RAG_CHROMA_DIR") or str(config.RAG_CHROMA_DIR),
        "RAG_COLLECTION": os.getenv("RAG_COLLECTION") or config.RAG_COLLECTION,
        "INTELLIGENCE_SOURCES": os.getenv("INTELLIGENCE_SOURCES") or ",".join(config.INTELLIGENCE_SOURCES),
        "INJURY_SOURCES": os.getenv("INJURY_SOURCES") or ",".join(config.INJURY_SOURCES),
        "GCS_CHROMA_BUCKET": os.getenv("GCS_CHROMA_BUCKET") or "",
    }
    missing = [key for key, value in resolved.items() if not value]
    if missing:
        raise ValueError(f"Missing required RAG refresh environment values: {', '.join(missing)}")

    for key, value in resolved.items():
        os.environ[key] = value
    return resolved


def _capture_scheduler_run() -> tuple[bool, dict[str, object]]:
    """
    Run the existing scheduler job and infer success from the emitted logs.

    The scheduler function is reused directly, but it swallows exceptions and
    logs failures internally. This capture layer translates those signals into
    an explicit success/failure result for the Cloud Run job.
    """

    import scheduler  # imported lazily after sys.path setup

    captured: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    scheduler_logger = logging.getLogger(scheduler.__name__)
    handler = CaptureHandler(level=logging.INFO)
    scheduler_logger.addHandler(handler)
    try:
        scheduler.run_rag_ingestion_job()
    finally:
        scheduler_logger.removeHandler(handler)

    failure_messages = []
    success_processed: Optional[int] = None
    for record in captured:
        message = record.getMessage()
        if record.levelno >= logging.ERROR:
            failure_messages.append(message)
        elif "No documents fetched" in message:
            failure_messages.append(message)
        elif "Upserted" in message:
            match = re.search(r"Upserted (\d+) chunks", message)
            if match:
                success_processed = int(match.group(1))

    if failure_messages:
        return False, {
            "failure_messages": failure_messages,
            "success_processed": success_processed,
        }

    if success_processed is None or success_processed <= 0:
        return False, {
            "failure_messages": ["No successful upsert log was observed"],
            "success_processed": success_processed,
        }

    return True, {
        "success_processed": success_processed,
    }


def snapshot_chroma_dir_to_gcs(
    chroma_dir: Path,
    bucket_name: str,
    project_id: Optional[str],
) -> str:
    """Archive the Chroma directory and upload it as a tar.gz snapshot."""
    from google.cloud import storage

    if not chroma_dir.exists():
        raise FileNotFoundError(f"Chroma directory does not exist: {chroma_dir}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H")
    archive_name = f"{timestamp}.tar.gz"
    object_name = f"snapshots/{archive_name}"

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as temp_file:
        temp_path = Path(temp_file.name)

    try:
        with tarfile.open(temp_path, "w:gz") as tar:
            tar.add(chroma_dir, arcname=chroma_dir.name)

        client = storage.Client(project=project_id or None)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        blob.upload_from_filename(str(temp_path), content_type="application/gzip")
        gcs_uri = f"gs://{bucket_name}/{object_name}"

        emit(
            logging.INFO,
            "snapshot_uploaded",
            gcs_uri=gcs_uri,
            source_dir=str(chroma_dir),
        )
        prune_old_snapshots(bucket, keep_last=5)
        return gcs_uri
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            logger.debug("Temporary archive cleanup skipped", exc_info=True)


def prune_old_snapshots(bucket, keep_last: int = 5) -> None:
    blobs = list(bucket.list_blobs(prefix="snapshots/"))
    if len(blobs) <= keep_last:
        emit(logging.INFO, "snapshot_prune_skipped", snapshot_count=len(blobs))
        return

    blobs.sort(
        key=lambda blob: blob.time_created or blob.updated or datetime(1970, 1, 1, tzinfo=timezone.utc)
    )
    to_delete = blobs[:-keep_last]
    for blob in to_delete:
        blob.delete()

    emit(
        logging.INFO,
        "snapshot_pruned",
        deleted=len(to_delete),
        retained=keep_last,
    )


def main() -> int:
    load_dotenv()
    configure_logging()
    runtime_env = _resolve_runtime_env()
    bucket_name = runtime_env["GCS_CHROMA_BUCKET"]
    project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    chroma_dir = Path(runtime_env["RAG_CHROMA_DIR"])

    emit(
        logging.INFO,
        "rag_refresh_started",
        bucket_name=bucket_name,
        chroma_dir=str(chroma_dir),
        project_id=project_id,
        rag_collection=runtime_env["RAG_COLLECTION"],
        intelligence_sources_count=len(runtime_env["INTELLIGENCE_SOURCES"].split(",")),
        injury_sources_count=len(runtime_env["INJURY_SOURCES"].split(",")),
    )

    try:
        success, details = _capture_scheduler_run()
        if not success:
            emit(logging.ERROR, "rag_refresh_failed", **details)
            return 1

        gcs_uri = snapshot_chroma_dir_to_gcs(chroma_dir, bucket_name, project_id)
        emit(
            logging.INFO,
            "rag_refresh_complete",
            gcs_uri=gcs_uri,
            **details,
        )
        return 0
    except Exception as exc:
        emit(logging.ERROR, "rag_refresh_failed", error=str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
