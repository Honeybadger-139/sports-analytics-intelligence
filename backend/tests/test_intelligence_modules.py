"""
Unit tests for intelligence ingestion/retrieval utilities.
"""

from datetime import datetime, timedelta, timezone

from src.intelligence.news_agent import chunk_context_document, parse_feed_content
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
