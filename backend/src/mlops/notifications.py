"""
Notification helpers for MLOps escalation events.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Iterable

import requests

from src import config

logger = logging.getLogger(__name__)

_RECENT_SIGNATURES: dict[str, float] = {}


def _signature(season: str, alerts: Iterable[Dict]) -> str:
    parts = [season]
    for alert in alerts:
        parts.append(
            "|".join(
                [
                    str(alert.get("id", "")),
                    str(alert.get("severity", "")),
                    str(alert.get("escalation_level", "")),
                    str(alert.get("message", "")),
                ]
            )
        )
    return "::".join(parts)


def _post_to_slack(webhook_url: str, payload: Dict) -> None:
    try:
        response = requests.post(webhook_url, json=payload, timeout=5)
        response.raise_for_status()
    except Exception as exc:
        logger.warning("Slack alert dispatch failed: %s", exc)


def notify_critical_escalation(season: str, alerts: list[Dict], escalation: Dict) -> bool:
    if not config.SLACK_WEBHOOK_URL:
        logger.info("Critical escalation detected, but SLACK_WEBHOOK_URL is not configured.")
        return False
    if escalation.get("state") != "incident":
        return False

    sig = _signature(season, alerts)
    now = time.time()
    last_sent = _RECENT_SIGNATURES.get(sig)
    if last_sent and (now - last_sent) < config.SLACK_ALERT_DEDUP_SECONDS:
        logger.info("Skipping duplicate Slack incident alert for signature %s", sig)
        return False

    _RECENT_SIGNATURES[sig] = now
    payload = {
        "text": (
            f"GameThread critical MLOps escalation for {season}: "
            f"{escalation.get('incident_alerts', 0)} incident alerts, "
            f"{escalation.get('watch_alerts', 0)} watch alerts."
        ),
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*GameThread critical MLOps escalation*\n"
                        f"*Season:* `{season}`\n"
                        f"*State:* `{escalation.get('state', 'unknown')}`"
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(
                        f"- `{alert.get('id', 'unknown')}`: {alert.get('message', '')}"
                        for alert in alerts
                        if alert.get("escalation_level") == "incident"
                    )
                    or "- No incident-level details provided.",
                },
            },
        ],
    }
    threading.Thread(
        target=_post_to_slack,
        args=(config.SLACK_WEBHOOK_URL, payload),
        daemon=True,
    ).start()
    return True
