"""
Orchestrator for game intelligence retrieval + summarization.
"""

from __future__ import annotations

import logging
import json
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from src import config
from src.data.intelligence_audit_store import record_intelligence_audit
from src.intelligence.embeddings import EmbeddingClient
from src.intelligence.news_agent import chunk_context_document, fetch_context_documents_with_health
from src.intelligence.retriever import ContextRetriever
from src.intelligence.rules import derive_risk_signals
from src.intelligence.summarizer import ContextSummarizer
from src.intelligence.vector_store import VectorStore

logger = logging.getLogger(__name__)


def _severity_rank(value: str) -> int:
    return {"low": 1, "medium": 2, "high": 3}.get(value, 0)


def _risk_level(signals: List[Dict]) -> str:
    if not signals:
        return "low"
    return max(signals, key=lambda item: _severity_rank(item.get("severity", "low"))).get("severity", "low")


NOISE_KEYWORDS = (
    "parlay",
    "promo code",
    "odds",
    "longshot",
    "betting",
    "mock draft",
    "kalshi",
)


def _parse_published_at(value: str | None) -> datetime:
    if not value:
        return datetime.now(tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return datetime.now(tz=timezone.utc)


def _freshness_hours(value: str | None) -> float:
    published_at = _parse_published_at(value)
    return max((datetime.now(tz=timezone.utc) - published_at).total_seconds() / 3600.0, 0.0)


def _is_noisy_context(doc: Dict) -> bool:
    text = f"{doc.get('title', '')} {doc.get('content', '')}".lower()
    return any(keyword in text for keyword in NOISE_KEYWORDS)


def _score_doc_quality(doc: Dict, max_age_hours: int) -> Dict:
    freshness = _freshness_hours(doc.get("published_at"))
    similarity = float(doc.get("score") or 0.0)
    freshness_factor = max(0.0, 1.0 - (freshness / max(max_age_hours, 1)))
    similarity_factor = max(min((similarity + 1.0) / 2.0, 1.0), 0.0)
    noisy = _is_noisy_context(doc)
    quality_score = max(
        0.0,
        min(1.0, (0.55 * similarity_factor) + (0.45 * freshness_factor) - (0.35 if noisy else 0.0)),
    )
    stale = freshness >= (max_age_hours * 0.75)
    annotated = dict(doc)
    annotated.update(
        {
            "quality_score": round(quality_score, 4),
            "freshness_hours": round(freshness, 1),
            "is_stale": stale,
            "is_noisy": noisy,
        }
    )
    return annotated


def _source_quality_summary(docs: List[Dict]) -> List[Dict]:
    grouped: Dict[str, List[Dict]] = {}
    for doc in docs:
        source = doc.get("source") or "unknown-source"
        grouped.setdefault(source, []).append(doc)

    summary = []
    for source, rows in grouped.items():
        avg_quality = sum(float(row.get("quality_score") or 0.0) for row in rows) / len(rows)
        avg_freshness = sum(float(row.get("freshness_hours") or 0.0) for row in rows) / len(rows)
        summary.append(
            {
                "source": source,
                "docs_used": len(rows),
                "avg_quality_score": round(avg_quality, 3),
                "avg_freshness_hours": round(avg_freshness, 1),
                "fresh_docs": sum(1 for row in rows if float(row.get("freshness_hours") or 0.0) <= 24),
                "stale_docs": sum(1 for row in rows if bool(row.get("is_stale"))),
                "noisy_docs": sum(1 for row in rows if bool(row.get("is_noisy"))),
            }
        )
    summary.sort(key=lambda row: row["avg_quality_score"], reverse=True)
    return summary


class IntelligenceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.embedding_client = EmbeddingClient()
        self.vector_store = VectorStore()
        self.retriever = ContextRetriever(self.embedding_client, self.vector_store)
        self.summarizer = ContextSummarizer()
        self._index_refreshed = False
        self._feed_health: List[Dict] = []

    def _load_feed_health_from_audit(self) -> List[Dict]:
        try:
            row = self.db.execute(
                text(
                    """
                    SELECT details
                    FROM intelligence_audit
                    WHERE module = 'indexer'
                    ORDER BY run_time DESC
                    LIMIT 1
                    """
                )
            ).fetchone()
            if not row:
                return []
            details = row[0]
            if isinstance(details, str):
                details = json.loads(details)
            if isinstance(details, dict):
                feed_health = details.get("feed_health")
                if isinstance(feed_health, list):
                    return feed_health
            return []
        except Exception:
            return []

    def _get_game_context(self, game_id: str, season: Optional[str]) -> Dict:
        row = self.db.execute(
            text(
                """
                SELECT
                    m.game_id,
                    m.season,
                    m.game_date,
                    ht.abbreviation AS home_team,
                    at.abbreviation AS away_team,
                    hf.days_rest AS home_days_rest,
                    af.days_rest AS away_days_rest
                FROM matches m
                JOIN teams ht ON m.home_team_id = ht.team_id
                JOIN teams at ON m.away_team_id = at.team_id
                LEFT JOIN match_features hf ON m.game_id = hf.game_id AND m.home_team_id = hf.team_id
                LEFT JOIN match_features af ON m.game_id = af.game_id AND m.away_team_id = af.team_id
                WHERE m.game_id = :game_id
                  AND (:season IS NULL OR m.season = :season)
                LIMIT 1
                """
            ),
            {"game_id": game_id, "season": season},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
        return dict(row._mapping)

    def _refresh_index_if_needed(self) -> None:
        if self._index_refreshed:
            return
        self._index_refreshed = True
        if self.vector_store.count() > 0:
            self._feed_health = self._load_feed_health_from_audit()
            return

        sources = config.INTELLIGENCE_SOURCES + config.INJURY_SOURCES
        docs, health = fetch_context_documents_with_health(
            sources=sources,
            timeout_seconds=config.RAG_REQUEST_TIMEOUT_SECONDS,
            max_items_per_feed=40,
        )
        self._feed_health = health
        if not docs:
            record_intelligence_audit(
                self.db.get_bind(),
                module="indexer",
                status="degraded",
                records_processed=0,
                errors="No context documents fetched from configured sources",
                details={"sources": sources, "feed_health": health},
            )
            return

        payload: List[Dict] = []
        for doc in docs:
            chunked_docs = chunk_context_document(doc)
            for chunk_doc in chunked_docs:
                content = f"{chunk_doc.title}. {chunk_doc.content}".strip()
                payload.append(
                    {
                        "doc_id": chunk_doc.doc_id,
                        "source": chunk_doc.source,
                        "title": chunk_doc.title,
                        "url": chunk_doc.url,
                        "published_at": chunk_doc.published_at.isoformat(),
                        "team_tags": chunk_doc.team_tags,
                        "player_tags": chunk_doc.player_tags,
                        "content": content,
                        "embedding": self.embedding_client.embed_document(content),
                    }
                )

        inserted = self.vector_store.upsert(payload)
        record_intelligence_audit(
            self.db.get_bind(),
            module="indexer",
            status="success" if inserted else "degraded",
            records_processed=inserted,
            details={"sources": sources, "store_count": self.vector_store.count(), "feed_health": health},
        )

    @staticmethod
    def _citations_from_docs(docs: List[Dict]) -> List[Dict]:
        citations = []
        seen = set()
        for doc in docs:
            key = (doc.get("url") or "", doc.get("title") or "")
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                {
                    "title": doc.get("title") or "Untitled context",
                    "url": doc.get("url") or "",
                    "source": doc.get("source") or "unknown-source",
                    "published_at": doc.get("published_at") or "",
                    "snippet": (doc.get("content") or "")[:220],
                    "quality_score": doc.get("quality_score"),
                    "freshness_hours": doc.get("freshness_hours"),
                    "is_stale": bool(doc.get("is_stale")),
                    "is_noisy": bool(doc.get("is_noisy")),
                }
            )
        return citations

    def get_game_intelligence(
        self,
        *,
        game_id: str,
        season: Optional[str],
        top_k: int,
        max_age_hours: int,
    ) -> Dict:
        game = self._get_game_context(game_id, season)
        self._refresh_index_if_needed()

        matchup = f"{game['away_team']} @ {game['home_team']}"
        query_text = (
            f"NBA matchup {matchup}. injury report, lineup availability, travel fatigue, rest, "
            f"recent team updates, tactical notes."
        )
        docs, retrieval_stats = self.retriever.retrieve(
            query_text,
            top_k=top_k,
            max_age_hours=max_age_hours,
            team_filter=[game["home_team"], game["away_team"]],
        )
        scored_docs = [_score_doc_quality(doc, max_age_hours) for doc in docs]
        scored_docs.sort(key=lambda row: float(row.get("quality_score") or 0.0), reverse=True)
        docs = [
            row
            for row in scored_docs
            if float(row.get("quality_score") or 0.0) >= 0.18 and not (row.get("is_noisy") and row["quality_score"] < 0.35)
        ][:top_k]
        retrieval_stats["docs_used"] = len(docs)
        retrieval_stats["source_quality"] = _source_quality_summary(docs)

        risk_signals = derive_risk_signals(
            docs,
            home_days_rest=game.get("home_days_rest"),
            away_days_rest=game.get("away_days_rest"),
            max_age_hours=max_age_hours,
        )
        citations = self._citations_from_docs(docs)
        coverage_status = "sufficient" if citations else "insufficient"

        if citations:
            summary = self.summarizer.summarize(matchup, docs)
        else:
            summary = (
                "Insufficient recent cited context for this matchup. "
                "Use model probabilities as primary signal until context sources refresh."
            )

        response = {
            "game_id": str(game["game_id"]),
            "season": str(game["season"]),
            "generated_at": datetime.utcnow().isoformat(),
            "summary": summary,
            "risk_signals": risk_signals,
            "citations": citations,
            "retrieval": retrieval_stats,
            "coverage_status": coverage_status,
            "feed_health": self._feed_health,
        }

        record_intelligence_audit(
            self.db.get_bind(),
            module="retriever",
            status="success" if citations else "degraded",
            records_processed=retrieval_stats["docs_used"],
            details={
                "game_id": str(game["game_id"]),
                "matchup": matchup,
                "coverage_status": coverage_status,
                "max_age_hours": max_age_hours,
                "top_k": top_k,
            },
        )
        return response

    def get_daily_brief(
        self,
        *,
        brief_date: date,
        season: str,
        limit: int,
        top_k: int,
        max_age_hours: int,
    ) -> Dict:
        rows = self.db.execute(
            text(
                """
                SELECT
                    m.game_id,
                    ht.abbreviation AS home_team,
                    at.abbreviation AS away_team
                FROM matches m
                JOIN teams ht ON m.home_team_id = ht.team_id
                JOIN teams at ON m.away_team_id = at.team_id
                WHERE m.game_date = :brief_date
                  AND m.season = :season
                ORDER BY m.game_id
                LIMIT :limit
                """
            ),
            {"brief_date": brief_date, "season": season, "limit": limit},
        ).fetchall()

        items = []
        for row in rows:
            game_payload = self.get_game_intelligence(
                game_id=str(row.game_id),
                season=season,
                top_k=min(top_k, 6),
                max_age_hours=max_age_hours,
            )
            items.append(
                {
                    "game_id": str(row.game_id),
                    "matchup": f"{row.away_team} @ {row.home_team}",
                    "summary": game_payload["summary"],
                    "risk_level": _risk_level(game_payload.get("risk_signals") or []),
                    "citation_count": len(game_payload.get("citations") or []),
                }
            )

        record_intelligence_audit(
            self.db.get_bind(),
            module="brief",
            status="success",
            records_processed=len(items),
            details={"date": brief_date.isoformat(), "season": season, "limit": limit},
        )
        return {"date": brief_date.isoformat(), "season": season, "items": items}
