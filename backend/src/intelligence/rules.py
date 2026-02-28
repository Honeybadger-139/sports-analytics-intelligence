"""
Deterministic rule overlays for contextual risk signals.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List


INJURY_KEYWORDS_HIGH = ("out", "ruled out", "won't play", "won’t play", "doubtful")
INJURY_KEYWORDS_MED = ("questionable", "game-time decision", "limited")


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(tz=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return datetime.now(tz=timezone.utc)


def derive_risk_signals(
    docs: List[Dict],
    *,
    home_days_rest: int | None,
    away_days_rest: int | None,
    max_age_hours: int,
) -> List[Dict]:
    signals: List[Dict] = []
    lowered_corpus = " ".join(
        f"{doc.get('title', '')} {doc.get('content', '')}".lower() for doc in docs
    )

    if any(keyword in lowered_corpus for keyword in INJURY_KEYWORDS_HIGH):
        signals.append(
            {
                "id": "injury_high",
                "label": "High Injury Risk",
                "severity": "high",
                "rationale": "Recent context includes likely absences or doubtful status indicators.",
            }
        )
    elif any(keyword in lowered_corpus for keyword in INJURY_KEYWORDS_MED):
        signals.append(
            {
                "id": "injury_watch",
                "label": "Injury Watch",
                "severity": "medium",
                "rationale": "Recent context includes questionable or limited availability signals.",
            }
        )

    if (home_days_rest is not None and home_days_rest <= 1) or (away_days_rest is not None and away_days_rest <= 1):
        signals.append(
            {
                "id": "short_rest",
                "label": "Short Rest / Back-to-Back Risk",
                "severity": "medium",
                "rationale": "One or both teams are on short rest, increasing variance.",
            }
        )

    if away_days_rest is not None and away_days_rest <= 1:
        signals.append(
            {
                "id": "travel_fatigue_proxy",
                "label": "Travel Fatigue Proxy",
                "severity": "low",
                "rationale": "Away team short-rest profile can amplify fatigue-related execution risk.",
            }
        )

    freshness_cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=max_age_hours)
    stale_docs = [doc for doc in docs if _parse_dt(doc.get("published_at")) < freshness_cutoff]
    if stale_docs and len(stale_docs) == len(docs):
        signals.append(
            {
                "id": "stale_context",
                "label": "Stale Context",
                "severity": "high",
                "rationale": "Retrieved sources are older than freshness threshold; treat context guidance cautiously.",
            }
        )

    return signals
