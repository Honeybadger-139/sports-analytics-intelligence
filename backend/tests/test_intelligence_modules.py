"""
Unit tests for intelligence ingestion/retrieval utilities.
"""

from datetime import datetime, timedelta, timezone

from src.intelligence.news_agent import (
    chunk_context_document,
    fetch_context_documents_with_health,
    parse_feed_content,
)
from src.intelligence.rules import derive_risk_signals
from src.intelligence.service import _score_doc_quality
from src.intelligence.types import ContextDocument
from src.intelligence.retriever import ContextRetriever


class _EmbeddingClient:
    def embed_query(self, _text):
        return [1.0, 0.0, 0.0]


class _VectorStore:
    def __init__(self, rows):
        self._rows = rows

    def count(self):
        return len(self._rows)

    def query(self, query_embedding, top_k):  # noqa: ARG002 - signature parity
        return self._rows[:top_k]


def test_parse_feed_content_handles_malformed_xml():
    docs = parse_feed_content("<rss><item></rss>", "https://example.com/rss")
    assert docs == []


def test_parse_feed_content_handles_missing_title_and_url():
    xml = """
    <rss>
      <channel>
        <item>
          <description>Lakers player listed as questionable for tonight</description>
          <pubDate>Sat, 28 Feb 2026 10:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    docs = parse_feed_content(xml, "https://example.com/rss")
    assert len(docs) == 1
    assert docs[0].source == "example.com"
    assert docs[0].url == "https://example.com/rss"
    assert "LAL" in docs[0].team_tags


def test_retriever_applies_freshness_and_topk():
    now = datetime.now(tz=timezone.utc)
    rows = [
        {
            "doc_id": "fresh-a",
            "title": "Fresh",
            "url": "https://example.com/a",
            "source": "example.com",
            "published_at": now.isoformat(),
            "team_tags": ["LAL"],
            "player_tags": [],
            "content": "fresh document",
            "score": 0.9,
        },
        {
            "doc_id": "stale-b",
            "title": "Stale",
            "url": "https://example.com/b",
            "source": "example.com",
            "published_at": (now - timedelta(hours=400)).isoformat(),
            "team_tags": ["LAL"],
            "player_tags": [],
            "content": "stale document",
            "score": 0.8,
        },
    ]

    retriever = ContextRetriever(_EmbeddingClient(), _VectorStore(rows))
    docs, stats = retriever.retrieve(
        "LAL matchup",
        top_k=2,
        max_age_hours=120,
        team_filter=["LAL"],
    )
    assert len(docs) == 1
    assert docs[0]["doc_id"] == "fresh-a"
    assert stats["docs_considered"] == 2
    assert stats["docs_used"] == 1


def test_chunk_context_document_overlap_boundaries_are_deterministic():
    long_text = "".join(str(i % 10) for i in range(2500))
    doc = ContextDocument(
        doc_id="doc-1",
        source="example.com",
        title="Long context",
        url="https://example.com/doc-1",
        published_at=datetime(2026, 2, 28, 10, 0, tzinfo=timezone.utc),
        team_tags=["LAL"],
        player_tags=[],
        content=long_text,
    )

    chunks = chunk_context_document(doc, chunk_size=1000, chunk_overlap=200)
    assert len(chunks) == 3
    assert chunks[0].doc_id == "doc-1::chunk_0"
    assert chunks[1].doc_id == "doc-1::chunk_1"
    assert chunks[2].doc_id == "doc-1::chunk_2"
    assert chunks[0].content[-200:] == chunks[1].content[:200]
    assert chunks[1].content[-200:] == chunks[2].content[:200]


def test_fetch_context_documents_with_health_reports_source_statuses(monkeypatch):
    class _Resp:
        def __init__(self, body):
            self.text = body

        def raise_for_status(self):
            return None

    xml = """
    <rss>
      <channel>
        <item>
          <title>Lakers injury update</title>
          <description>Questionable tag before tipoff</description>
          <pubDate>Sat, 28 Feb 2026 10:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """

    def _fake_get(url, timeout):  # noqa: ARG001 - parity with requests.get signature
        if "bad-feed" in url:
            raise RuntimeError("network error")
        return _Resp(xml)

    monkeypatch.setattr("src.intelligence.news_agent.requests.get", _fake_get)
    docs, health = fetch_context_documents_with_health(
        ["https://good-feed.test/rss", "https://bad-feed.test/rss"],
        timeout_seconds=2,
        max_items_per_feed=5,
    )

    assert len(docs) == 1
    assert any(item["status"] == "ok" and item["source"] == "good-feed.test" for item in health)
    assert any(item["status"] == "error" and item["source"] == "bad-feed.test" for item in health)


def test_score_doc_quality_penalizes_noisy_betting_content():
    now = datetime.now(tz=timezone.utc).isoformat()
    baseline = _score_doc_quality(
        {
            "title": "BOS lineup update",
            "content": "Injury status changed to questionable",
            "published_at": now,
            "score": 0.9,
        },
        max_age_hours=120,
    )
    noisy = _score_doc_quality(
        {
            "title": "NBA parlay odds and promo code",
            "content": "Best betting longshot",
            "published_at": now,
            "score": 0.9,
        },
        max_age_hours=120,
    )

    assert baseline["is_noisy"] is False
    assert noisy["is_noisy"] is True
    assert noisy["quality_score"] < baseline["quality_score"]


def test_rules_ignore_noisy_docs_for_injury_signal():
    now = datetime.now(tz=timezone.utc).isoformat()
    signals = derive_risk_signals(
        [
            {
                "title": "Parlay odds update",
                "content": "questionable doubtful out",
                "published_at": now,
                "is_noisy": True,
            }
        ],
        home_days_rest=3,
        away_days_rest=3,
        max_age_hours=120,
    )
    ids = {signal["id"] for signal in signals}
    assert "injury_high" not in ids
    assert "injury_watch" not in ids
    assert "low_signal_context" in ids


def test_rules_emit_injury_conflict_when_high_and_medium_signals_present():
    now = datetime.now(tz=timezone.utc).isoformat()
    signals = derive_risk_signals(
        [
            {
                "title": "Starter ruled out tonight",
                "content": "official report says out",
                "published_at": now,
                "is_noisy": False,
            },
            {
                "title": "Another player questionable",
                "content": "game-time decision note",
                "published_at": now,
                "is_noisy": False,
            },
        ],
        home_days_rest=2,
        away_days_rest=2,
        max_age_hours=120,
    )
    ids = {signal["id"] for signal in signals}
    assert "injury_high" in ids
    assert "injury_signal_conflict" in ids
