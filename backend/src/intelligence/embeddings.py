"""
Embedding client with Gemini primary path and deterministic fallback.
"""

from __future__ import annotations

import hashlib
import logging
import math
from typing import List

from src import config

logger = logging.getLogger(__name__)


def cosine_similarity(left: List[float], right: List[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_mag = math.sqrt(sum(a * a for a in left))
    right_mag = math.sqrt(sum(b * b for b in right))
    if left_mag == 0.0 or right_mag == 0.0:
        return 0.0
    return dot / (left_mag * right_mag)


def _hash_embedding(text: str, dim: int = 96) -> List[float]:
    """
    Deterministic no-network fallback embedding.
    """
    out = [0.0] * dim
    normalized = (text or "").lower().strip() or "empty"
    for token in normalized.split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for i in range(dim):
            out[i] += ((digest[i % len(digest)] / 255.0) - 0.5)
    magnitude = math.sqrt(sum(v * v for v in out)) or 1.0
    return [v / magnitude for v in out]


class EmbeddingClient:
    def __init__(self) -> None:
        self._use_gemini = False
        self._genai = None
        if config.GEMINI_API_KEY:
            try:
                import google.generativeai as genai  # type: ignore

                genai.configure(api_key=config.GEMINI_API_KEY)
                self._genai = genai
                self._use_gemini = True
            except Exception as exc:
                logger.warning("Gemini embedding unavailable, using deterministic fallback: %s", exc)

    def embed_document(self, text: str) -> List[float]:
        if not self._use_gemini:
            return _hash_embedding(text)
        try:
            payload = self._genai.embed_content(  # type: ignore[union-attr]
                model=config.RAG_EMBEDDING_MODEL,
                content=text[:6000],
                task_type="retrieval_document",
            )
            return [float(v) for v in payload["embedding"]]
        except Exception as exc:
            logger.warning("Gemini embedding failed, using deterministic fallback: %s", exc)
            return _hash_embedding(text)

    def embed_query(self, text: str) -> List[float]:
        if not self._use_gemini:
            return _hash_embedding(text)
        try:
            payload = self._genai.embed_content(  # type: ignore[union-attr]
                model=config.RAG_EMBEDDING_MODEL,
                content=text[:3000],
                task_type="retrieval_query",
            )
            return [float(v) for v in payload["embedding"]]
        except Exception as exc:
            logger.warning("Gemini query embedding failed, using deterministic fallback: %s", exc)
            return _hash_embedding(text)
