"""
Monitoring metrics for model quality and data freshness.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from src import config
from src.data.intelligence_audit_store import record_intelligence_audit
from src.data.mlops_store import fetch_monitoring_trend, record_monitoring_snapshot


def _days_since(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if hasattr(value, "tzinfo") and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    now = datetime.now(tz=timezone.utc)
    return max((now - value.astimezone(timezone.utc)).days, 0)


def _metric_breach_streak(points: List[Dict], field: str, predicate) -> int:
    streak = 0
    for point in points:
        value = point.get(field)
        if value is None:
            break
        if predicate(float(value)):
            streak += 1
            continue
        break
    return streak


def _alert_payload(alert_id: str, severity: str, message: str, breach_streak: int) -> Dict:
    escalation_level = "none"
    action = "monitor"
    if severity == "high" and breach_streak >= 2:
        escalation_level = "incident"
        action = "open_incident"
    elif severity == "high":
        escalation_level = "watch"
        action = "investigate_now"
    elif severity == "medium" and breach_streak >= 3:
        escalation_level = "watch"
        action = "investigate_now"

    return {
        "id": alert_id,
        "severity": severity,
        "message": message,
        "breach_streak": breach_streak,
        "escalation_level": escalation_level,
        "recommended_action": action,
    }


def _escalation_summary(alerts: List[Dict]) -> Dict:
    incident_count = sum(1 for alert in alerts if alert.get("escalation_level") == "incident")
    watch_count = sum(1 for alert in alerts if alert.get("escalation_level") == "watch")
    if incident_count:
        state = "incident"
    elif watch_count:
        state = "watch"
    elif alerts:
        state = "active"
    else:
        state = "none"
    return {
        "state": state,
        "incident_alerts": incident_count,
        "watch_alerts": watch_count,
        "total_alerts": len(alerts),
    }


def get_monitoring_overview(db: Session, season: str) -> Dict:
    perf_row = db.execute(
        text(
            """
            SELECT
                COUNT(*) AS evaluated_predictions,
                ROUND(AVG(CASE WHEN p.was_correct THEN 1.0 ELSE 0.0 END)::numeric, 4) AS accuracy,
                ROUND(AVG(POWER(
                    p.home_win_prob::numeric - (CASE WHEN m.winner_team_id = m.home_team_id THEN 1 ELSE 0 END), 2
                ))::numeric, 4) AS brier_score
            FROM predictions p
            JOIN matches m ON p.game_id = m.game_id
            WHERE m.season = :season
              AND m.is_completed = TRUE
              AND p.was_correct IS NOT NULL
            """
        ),
        {"season": season},
    ).fetchone()

    latest_game_date = db.execute(
        text("SELECT MAX(game_date) FROM matches WHERE season = :season"),
        {"season": season},
    ).scalar()

    latest_pipeline_sync = db.execute(
        text("SELECT MAX(sync_time) FROM pipeline_audit"),
    ).scalar()

    alerts: List[Dict] = []
    accuracy = float(perf_row.accuracy) if perf_row and perf_row.accuracy is not None else None
    brier = float(perf_row.brier_score) if perf_row and perf_row.brier_score is not None else None

    try:
        history_points = fetch_monitoring_trend(db, season=season, days=21, limit=8)
    except Exception:
        history_points = []

    accuracy_streak = _metric_breach_streak(
        history_points,
        "accuracy",
        lambda value: value < config.MLOPS_ACCURACY_THRESHOLD,
    )
    brier_streak = _metric_breach_streak(
        history_points,
        "brier_score",
        lambda value: value > config.MLOPS_MAX_BRIER,
    )
    game_freshness_streak = _metric_breach_streak(
        history_points,
        "game_data_freshness_days",
        lambda value: value > config.MLOPS_FRESHNESS_DAYS,
    )
    pipeline_freshness_streak = _metric_breach_streak(
        history_points,
        "pipeline_freshness_days",
        lambda value: value > config.MLOPS_FRESHNESS_DAYS,
    )

    if accuracy is not None and accuracy < config.MLOPS_ACCURACY_THRESHOLD:
        severity = "high"
        if accuracy < (config.MLOPS_ACCURACY_THRESHOLD - 0.07):
            severity = "high"
        alerts.append(
            _alert_payload(
                "accuracy_breach",
                severity,
                f"Accuracy {accuracy:.3f} below threshold {config.MLOPS_ACCURACY_THRESHOLD:.3f}",
                breach_streak=accuracy_streak + 1,
            )
        )
    if brier is not None and brier > config.MLOPS_MAX_BRIER:
        severity = "high" if brier > (config.MLOPS_MAX_BRIER + 0.08) else "medium"
        alerts.append(
            _alert_payload(
                "brier_breach",
                severity,
                f"Brier score {brier:.3f} above threshold {config.MLOPS_MAX_BRIER:.3f}",
                breach_streak=brier_streak + 1,
            )
        )

    game_freshness_days = _days_since(latest_game_date)
    pipeline_freshness_days = _days_since(latest_pipeline_sync)
    if game_freshness_days is not None and game_freshness_days > config.MLOPS_FRESHNESS_DAYS:
        severity = "high" if game_freshness_days > (config.MLOPS_FRESHNESS_DAYS + 2) else "medium"
        alerts.append(
            _alert_payload(
                "game_data_stale",
                severity,
                f"Latest game data is {game_freshness_days} days old.",
                breach_streak=game_freshness_streak + 1,
            )
        )
    if pipeline_freshness_days is not None and pipeline_freshness_days > config.MLOPS_FRESHNESS_DAYS:
        severity = "high" if pipeline_freshness_days > (config.MLOPS_FRESHNESS_DAYS + 2) else "medium"
        alerts.append(
            _alert_payload(
                "pipeline_stale",
                severity,
                f"Latest pipeline sync is {pipeline_freshness_days} days old.",
                breach_streak=pipeline_freshness_streak + 1,
            )
        )

    payload = {
        "season": season,
        "metrics": {
            "evaluated_predictions": int(perf_row.evaluated_predictions or 0) if perf_row else 0,
            "accuracy": accuracy,
            "brier_score": brier,
            "latest_game_date": latest_game_date.isoformat() if latest_game_date is not None else None,
            "latest_pipeline_sync": latest_pipeline_sync.isoformat() if latest_pipeline_sync is not None else None,
            "game_data_freshness_days": game_freshness_days,
            "pipeline_freshness_days": pipeline_freshness_days,
        },
        "thresholds": {
            "accuracy_min": config.MLOPS_ACCURACY_THRESHOLD,
            "brier_max": config.MLOPS_MAX_BRIER,
            "freshness_days_max": config.MLOPS_FRESHNESS_DAYS,
        },
        "alerts": alerts,
        "escalation": _escalation_summary(alerts),
    }

    engine = db.get_bind() if hasattr(db, "get_bind") else None
    if engine is not None:
        record_intelligence_audit(
            engine,
            module="mlops_monitoring",
            status="degraded" if alerts else "success",
            records_processed=payload["metrics"]["evaluated_predictions"],
            details={
                "season": season,
                "alerts": alerts,
                "thresholds": payload["thresholds"],
            },
        )
        record_monitoring_snapshot(engine, season=season, payload=payload)

    return payload


def get_monitoring_trend(db: Session, season: str, *, days: int = 14, limit: int = 30) -> Dict:
    points = fetch_monitoring_trend(db, season=season, days=days, limit=limit)
    return {
        "season": season,
        "window_days": days,
        "points": points,
    }
