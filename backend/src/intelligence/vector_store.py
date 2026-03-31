"""
Vector store with pgvector (Cloud SQL) primary backend.

Priority order:
  1. pgvector on Cloud SQL  — persistent, shared across Cloud Run + Docker
  2. ChromaDB               — local fallback when DATABASE_URL unavailable
  3. JSON file              — last-resort fallback when ChromaDB unavailable

This means the RAG chatbot always has fresh context regardless of container
restarts, because embeddings live in Cloud SQL rather than inside a container.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from src import config
from src.intelligence.embeddings import cosine_similarity

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self) -> None:
        self._impl = _build_store()

    def upsert(self, records: List[Dict]) -> int:
        return self.upsert_with_stats(records)["processed"]

    def upsert_with_stats(self, records: List[Dict]) -> Dict[str, int]:
        return self._impl.upsert_with_stats(records)

    def query(self, query_embedding: List[float], top_k: int) -> List[Dict]:
        return self._impl.query(query_embedding=query_embedding, top_k=top_k)

    def count(self) -> int:
        return self._impl.count()

    @property
    def backend_name(self) -> str:
        return self._impl.__class__.__name__


def _build_store():
    """Build the best available vector store backend."""
    # 1. Try pgvector on Cloud SQL (preferred — persistent and shared)
    database_url = getattr(config, "DATABASE_URL", None) or os.getenv("DATABASE_URL", "")
    if database_url:
        try:
            store = _PgVectorStore(database_url)
            logger.info("VectorStore: using pgvector on Cloud SQL (persistent)")
            return store
        except Exception as exc:
            logger.warning("pgvector unavailable, falling back: %s", exc)

    # 2. Try ChromaDB (local dev without Cloud SQL)
    try:
        import chromadb  # type: ignore
        store = _ChromaStore(chromadb)
        logger.info("VectorStore: using ChromaDB (local fallback)")
        return store
    except Exception as exc:
        logger.warning("ChromaDB unavailable, using JSON fallback: %s", exc)

    # 3. JSON file (absolute last resort)
    logger.warning("VectorStore: using JSON file (ephemeral fallback)")
    return _JsonVectorStore(config.RAG_CHROMA_DIR, config.RAG_COLLECTION)


# ── pgvector backend ──────────────────────────────────────────────────────────

class _PgVectorStore:
    """
    Stores embeddings in Cloud SQL using the pgvector extension.
    All containers share the same database so embeddings are never lost.

    Table schema (created once via migration):
        rag_documents (
            doc_id       TEXT PRIMARY KEY,
            content      TEXT,
            source       TEXT,
            title        TEXT,
            url          TEXT,
            published_at TEXT,
            team_tags    TEXT,   -- comma-separated
            player_tags  TEXT,   -- comma-separated
            embedding    vector(768),
            created_at   TIMESTAMPTZ,
            updated_at   TIMESTAMPTZ
        )
    """

    def __init__(self, database_url: str) -> None:
        import psycopg2  # type: ignore
        from pgvector.psycopg2 import register_vector  # type: ignore

        self._dsn = database_url
        self._psycopg2 = psycopg2
        self._register_vector = register_vector
        # Verify the table exists and pgvector is enabled
        self._check_ready()

    def _connect(self):
        conn = self._psycopg2.connect(self._dsn)
        self._register_vector(conn)
        return conn

    def _check_ready(self) -> None:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM rag_documents")
            conn.commit()
        finally:
            conn.close()

    # Expected embedding dimension matches the rag_documents table schema: vector(768).
    # Gemini text-embedding-* models produce 768-dim vectors.
    # The _hash_embedding fallback in embeddings.py produces 96-dim vectors.
    # Inserting a wrong-dimension vector into vector(768) causes a silent pgvector
    # type error and/or corrupted cosine similarity scores (-0.1 to -0.3 range).
    EXPECTED_EMBEDDING_DIM: int = 768

    def upsert_with_stats(self, records: List[Dict]) -> Dict[str, int]:
        if not records:
            return {"processed": 0, "created": 0, "updated": 0}

        import numpy as np  # type: ignore

        # Validate embedding dimensions before touching the DB.
        # Any record with the wrong number of dimensions is dropped with a loud
        # error log so the problem is immediately visible in Cloud Run logs.
        valid_records: List[Dict] = []
        skipped = 0
        for rec in records:
            emb = rec.get("embedding")
            if emb is not None and len(emb) != self.EXPECTED_EMBEDDING_DIM:
                logger.error(
                    "[vector_store] Dropping doc '%s': embedding has %d dims, expected %d. "
                    "Check whether GEMINI_API_KEY is set and Gemini embedding is active — "
                    "the hash fallback produces %d-dim vectors which are incompatible with "
                    "the vector(768) column schema.",
                    rec.get("doc_id", "unknown"),
                    len(emb),
                    self.EXPECTED_EMBEDDING_DIM,
                    len(emb),
                )
                skipped += 1
                continue
            valid_records.append(rec)

        if skipped:
            logger.warning(
                "[vector_store] %d/%d records skipped due to embedding dimension mismatch.",
                skipped, len(records),
            )

        if not valid_records:
            return {"processed": 0, "created": 0, "updated": 0, "skipped": skipped}

        conn = self._connect()
        try:
            cur = conn.cursor()
            # Find which doc_ids already exist
            ids = [r["doc_id"] for r in valid_records]
            cur.execute(
                "SELECT doc_id FROM rag_documents WHERE doc_id = ANY(%s)",
                (ids,)
            )
            existing_ids = {row[0] for row in cur.fetchall()}

            created = updated = 0
            for rec in valid_records:
                emb = rec.get("embedding")
                emb_val = np.array(emb) if emb else None
                if rec["doc_id"] in existing_ids:
                    cur.execute(
                        """UPDATE rag_documents
                           SET content=%s, source=%s, title=%s, url=%s,
                               published_at=%s, team_tags=%s, player_tags=%s,
                               embedding=%s, updated_at=NOW()
                           WHERE doc_id=%s""",
                        (
                            rec["content"], rec.get("source", "unknown"),
                            rec.get("title", "Untitled"), rec.get("url", ""),
                            rec.get("published_at"), ",".join(rec.get("team_tags", [])),
                            ",".join(rec.get("player_tags", [])), emb_val, rec["doc_id"],
                        ),
                    )
                    updated += 1
                else:
                    cur.execute(
                        """INSERT INTO rag_documents
                           (doc_id, content, source, title, url, published_at,
                            team_tags, player_tags, embedding)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            rec["doc_id"], rec["content"], rec.get("source", "unknown"),
                            rec.get("title", "Untitled"), rec.get("url", ""),
                            rec.get("published_at"), ",".join(rec.get("team_tags", [])),
                            ",".join(rec.get("player_tags", [])), emb_val,
                        ),
                    )
                    created += 1

            conn.commit()
            return {
                "processed": len(valid_records),
                "created": created,
                "updated": updated,
                "skipped": skipped,
            }
        finally:
            conn.close()

    def query(self, query_embedding: List[float], top_k: int) -> List[Dict]:
        if self.count() == 0:
            return []

        import numpy as np  # type: ignore

        conn = self._connect()
        try:
            cur = conn.cursor()
            emb = np.array(query_embedding)
            cur.execute(
                """SELECT doc_id, content, source, title, url, published_at,
                          team_tags, player_tags,
                          1 - (embedding <=> %s) AS score
                   FROM rag_documents
                   WHERE embedding IS NOT NULL
                   ORDER BY embedding <=> %s
                   LIMIT %s""",
                (emb, emb, top_k),
            )
            rows = []
            for row in cur.fetchall():
                doc_id, content, source, title, url, published_at, \
                    team_tags, player_tags, score = row
                rows.append({
                    "doc_id": doc_id,
                    "content": content,
                    "source": source,
                    "title": title,
                    "url": url or "",
                    "published_at": published_at,
                    "team_tags": [t for t in (team_tags or "").split(",") if t],
                    "player_tags": [t for t in (player_tags or "").split(",") if t],
                    "score": float(score) if score is not None else 0.0,
                })
            return rows
        finally:
            conn.close()

    def count(self) -> int:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM rag_documents")
            return int(cur.fetchone()[0])
        finally:
            conn.close()


# ── ChromaDB backend (local dev fallback) ────────────────────────────────────

class _ChromaStore:
    def __init__(self, chromadb_module) -> None:
        self._client = chromadb_module.PersistentClient(path=str(config.RAG_CHROMA_DIR))
        self._collection = self._client.get_or_create_collection(name=config.RAG_COLLECTION)

    def upsert_with_stats(self, records: List[Dict]) -> Dict[str, int]:
        if not records:
            return {"processed": 0, "created": 0, "updated": 0}
        ids = [record["doc_id"] for record in records]
        existing_ids: set = set()
        try:
            existing = self._collection.get(ids=ids, include=[])
            existing_ids = set(existing.get("ids", []))
        except Exception:
            pass
        self._collection.upsert(
            ids=ids,
            documents=[r["content"] for r in records],
            embeddings=[r["embedding"] for r in records],
            metadatas=[
                {
                    "source": r["source"],
                    "title": r["title"],
                    "url": r["url"],
                    "published_at": r["published_at"],
                    "team_tags": ",".join(r.get("team_tags", [])),
                    "player_tags": ",".join(r.get("player_tags", [])),
                }
                for r in records
            ],
        )
        unique_ids = set(ids)
        created = len([i for i in unique_ids if i not in existing_ids])
        return {"processed": len(records), "created": created, "updated": len(unique_ids) - created}

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
            rows.append({
                "doc_id": doc_id,
                "content": docs[idx] if idx < len(docs) else "",
                "source": meta.get("source", "unknown-source"),
                "title": meta.get("title", "Untitled"),
                "url": meta.get("url", ""),
                "published_at": meta.get("published_at"),
                "team_tags": [t for t in (meta.get("team_tags", "") or "").split(",") if t],
                "player_tags": [t for t in (meta.get("player_tags", "") or "").split(",") if t],
                "score": 1.0 - float(distances[idx] if idx < len(distances) else 1.0),
            })
        return rows

    def count(self) -> int:
        return int(self._collection.count())


# ── JSON fallback (absolute last resort) ─────────────────────────────────────

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

    def upsert_with_stats(self, records: List[Dict]) -> Dict[str, int]:
        if not records:
            return {"processed": 0, "created": 0, "updated": 0}
        existing = {row["doc_id"]: row for row in self._load()}
        existing_ids = set(existing)
        for record in records:
            existing[record["doc_id"]] = record
        self._save(list(existing.values()))
        unique_ids = {r["doc_id"] for r in records}
        created = len([i for i in unique_ids if i not in existing_ids])
        return {"processed": len(records), "created": created, "updated": len(unique_ids) - created}

    def query(self, query_embedding: List[float], top_k: int) -> List[Dict]:
        rows = self._load()
        if not rows:
            return []
        scored = sorted(
            [{**row, "score": cosine_similarity(query_embedding, row.get("embedding", []))} for row in rows],
            key=lambda r: r.get("score", 0.0),
            reverse=True,
        )
        return scored[:top_k]

    def count(self) -> int:
        return len(self._load())
