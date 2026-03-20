"""
GCP Cloud Monitoring helpers for MLOps custom metrics.

These helpers are intentionally best-effort:
- If a project ID is missing, they no-op for local development.
- If the Cloud Monitoring client is unavailable, they log a warning and continue.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CUSTOM_METRICS = {
    "prediction_confidence": "custom.googleapis.com/model/prediction_confidence",
    "data_freshness_hours": "custom.googleapis.com/pipeline/data_freshness_hours",
    "model_accuracy": "custom.googleapis.com/model/accuracy_rolling",
    "feature_null_rate": "custom.googleapis.com/pipeline/feature_null_rate",
    "retrain_triggered": "custom.googleapis.com/mlops/retrain_triggered",
}


def _resolve_project_id(project_id: Optional[str] = None) -> Optional[str]:
    if project_id:
        return project_id
    return os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT_ID")


def write_metric(metric_type: str, value: float, labels: Dict[str, str] | None = None, project_id: Optional[str] = None) -> None:
    """
    Write a single Cloud Monitoring data point.

    The call is best-effort: missing SDKs or configuration only emit a warning.
    """
    resolved_project_id = _resolve_project_id(project_id)
    if not resolved_project_id:
        logger.debug("Skipping metric %s because no project_id is configured", metric_type)
        return

    metric_name = CUSTOM_METRICS.get(metric_type, metric_type)
    if not metric_name.startswith("custom.googleapis.com/"):
        metric_name = f"custom.googleapis.com/{metric_name.lstrip('/')}"

    try:
        from google.cloud import monitoring_v3
    except Exception as exc:  # pragma: no cover - dependency optional in local dev
        logger.warning("Cloud Monitoring client unavailable, skipping %s: %s", metric_type, exc)
        return

    try:
        client = monitoring_v3.MetricServiceClient()
        project_name = f"projects/{resolved_project_id}"

        point = monitoring_v3.Point()
        point.value.double_value = float(value)
        point.interval.end_time.seconds = int(datetime.now(timezone.utc).timestamp())
        point.interval.end_time.nanos = 0

        series = monitoring_v3.TimeSeries()
        series.metric.type = metric_name
        if labels:
            series.metric.labels.update({key: str(val) for key, val in labels.items()})
        series.resource.type = "global"
        series.resource.labels["project_id"] = resolved_project_id
        series.points.append(point)

        client.create_time_series(name=project_name, time_series=[series])
    except Exception as exc:  # pragma: no cover - best-effort monitoring
        logger.warning("Failed to write Cloud Monitoring metric %s: %s", metric_type, exc)
