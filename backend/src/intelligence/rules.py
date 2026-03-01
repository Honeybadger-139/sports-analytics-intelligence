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
    usable_docs = [doc for doc in docs if not doc.get("is_noisy")]
    lowered_docs = [
        f"{doc.get('title', '')} {doc.get('content', '')}".lower()
        for doc in usable_docs
    ]
    lowered_corpus = " ".join(lowered_docs)
    high_hits = sum(
        1 for text in lowered_docs if any(keyword in text for keyword in INJURY_KEYWORDS_HIGH)
    )
    med_hits = sum(
        1 for text in lowered_docs if any(keyword in text for keyword in INJURY_KEYWORDS_MED)
    )

    if high_hits >= 1:
        signals.append(
            {
                "id": "injury_high",
                "label": "High Injury Risk",
                "severity": "high",
                "rationale": f"Recent non-noisy context includes {high_hits} likely absence/doubtful signal(s).",
            }
        )
    elif med_hits >= 1:
        signals.append(
            {
                "id": "injury_watch",
                "label": "Injury Watch",
                "severity": "medium",
                "rationale": f"Recent non-noisy context includes {med_hits} questionable/limited signal(s).",
            }
        )

    if high_hits >= 1 and med_hits >= 1:
        signals.append(
            {
                "id": "injury_signal_conflict",
                "label": "Injury Signal Conflict",
                "severity": "medium",
                "rationale": "Context contains mixed injury certainty signals; verify official availability closer to tipoff.",
            }
        )

    if home_days_rest is not None and away_days_rest is not None and home_days_rest <= 1 and away_days_rest <= 1:
        signals.append(
            {
                "id": "both_short_rest",
                "label": "Both Teams on Short Rest",
                "severity": "high",
                "rationale": "Both teams are on short rest/back-to-back profile, increasing variance and rotation uncertainty.",
            }
        )
    elif (home_days_rest is not None and home_days_rest <= 1) or (
        away_days_rest is not None and away_days_rest <= 1
    ):
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
    elif not usable_docs and docs:
        signals.append(
            {
                "id": "low_signal_context",
                "label": "Low-Signal Context",
                "severity": "medium",
                "rationale": "Retrieved context appears mostly low-signal/noisy; rely more on model and structured metrics.",
            }
        )

    return signals
