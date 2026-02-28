"""
Vector store abstraction with Chroma primary backend and JSON fallback.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List

from src import config
from src.intelligence.embeddings import cosine_similarity

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self) -> None:
        self._impl = _build_store()

    def upsert(self, records: List[Dict]) -> int:
        return self._impl.upsert(records)

    def query(self, query_embedding: List[float], top_k: int) -> List[Dict]:
        return self._impl.query(query_embedding=query_embedding, top_k=top_k)

    def count(self) -> int:
        return self._impl.count()


def _build_store():
    try:
        import chromadb  # type: ignore

        return _ChromaStore(chromadb)
    except Exception as exc:
        logger.warning("Chroma unavailable, using JSON vector fallback: %s", exc)
        return _JsonVectorStore(config.RAG_CHROMA_DIR, config.RAG_COLLECTION)


class _ChromaStore:
    def __init__(self, chromadb_module) -> None:
        self._client = chromadb_module.PersistentClient(path=str(config.RAG_CHROMA_DIR))
        self._collection = self._client.get_or_create_collection(name=config.RAG_COLLECTION)

    def upsert(self, records: List[Dict]) -> int:
        if not records:
            return 0
        ids = [record["doc_id"] for record in records]
        documents = [record["content"] for record in records]
        embeddings = [record["embedding"] for record in records]
        metadatas = [
            {
                "source": record["source"],
                "title": record["title"],
                "url": record["url"],
                "published_at": record["published_at"],
                "team_tags": ",".join(record.get("team_tags", [])),
                "player_tags": ",".join(record.get("player_tags", [])),
            }
            for record in records
        ]
        self._collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
        return len(records)

    def query(self, query_embedding: List[float], top_k: int) -> List[Dict]:
        if self.count() == 0:
            return []
        result = self._collection.query(query_embeddings=[query_embedding], n_results=top_k)
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        rows: List[Dict] = []
        for idx, doc_id in enumerate(ids):
            meta = metas[idx] if idx < len(metas) else {}
            rows.append(
                {
                    "doc_id": doc_id,
                    "content": docs[idx] if idx < len(docs) else "",
                    "source": meta.get("source", "unknown-source"),
                    "title": meta.get("title", "Untitled"),
                    "url": meta.get("url", ""),
                    "published_at": meta.get("published_at"),
                    "team_tags": [tag for tag in (meta.get("team_tags", "") or "").split(",") if tag],
                    "player_tags": [tag for tag in (meta.get("player_tags", "") or "").split(",") if tag],
                    "score": 1.0 - float(distances[idx] if idx < len(distances) else 1.0),
                }
            )
        return rows

    def count(self) -> int:
        return int(self._collection.count())


class _JsonVectorStore:
    def __init__(self, base_dir: Path, collection: str) -> None:
        base_dir.mkdir(parents=True, exist_ok=True)
        self._path = base_dir / f"{collection}.json"
        if not self._path.exists():
            self._path.write_text("[]", encoding="utf-8")

    def _load(self) -> List[Dict]:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save(self, payload: List[Dict]) -> None:
        self._path.write_text(json.dumps(payload), encoding="utf-8")

    def upsert(self, records: List[Dict]) -> int:
        if not records:
            return 0
        existing = {row["doc_id"]: row for row in self._load()}
        for record in records:
            existing[record["doc_id"]] = record
        merged = list(existing.values())
        self._save(merged)
        return len(records)

    def query(self, query_embedding: List[float], top_k: int) -> List[Dict]:
        rows = self._load()
        if not rows:
            return []
        scored = []
        for row in rows:
            score = cosine_similarity(query_embedding, row.get("embedding", []))
            item = dict(row)
            item["score"] = score
            scored.append(item)
        scored.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        return scored[:top_k]

    def count(self) -> int:
        return len(self._load())
