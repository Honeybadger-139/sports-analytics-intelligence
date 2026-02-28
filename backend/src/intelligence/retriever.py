"""
Retriever for NBA context documents with freshness controls.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

from src.intelligence.embeddings import EmbeddingClient
from src.intelligence.vector_store import VectorStore


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(tz=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return datetime.now(tz=timezone.utc)


class ContextRetriever:
    def __init__(self, embedding_client: EmbeddingClient, store: VectorStore) -> None:
        self.embedding_client = embedding_client
        self.store = store

    def retrieve(
        self,
        query_text: str,
        *,
        top_k: int,
        max_age_hours: int,
        team_filter: List[str] | None = None,
    ) -> Tuple[List[Dict], Dict]:
        team_filter = team_filter or []
        considered = self.store.count()
        if considered == 0:
            return [], {
                "docs_considered": 0,
                "docs_used": 0,
                "freshness_window_hours": max_age_hours,
            }

        query_embedding = self.embedding_client.embed_query(query_text)
        candidates = self.store.query(query_embedding=query_embedding, top_k=max(top_k * 3, top_k))

        freshness_cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=max_age_hours)
        filtered: List[Dict] = []
        for row in candidates:
            published_at = _parse_dt(row.get("published_at"))
            if published_at < freshness_cutoff:
                continue
            row_tags = row.get("team_tags") or []
            if team_filter and row_tags:
                if not any(team in row_tags for team in team_filter):
                    continue
            filtered.append(row)
            if len(filtered) >= top_k:
                break

        return filtered, {
            "docs_considered": considered,
            "docs_used": len(filtered),
            "freshness_window_hours": max_age_hours,
        }
