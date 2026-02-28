"""
Citation-grounded summarization service.
"""

from __future__ import annotations

import logging
from typing import Dict, List

from src import config

logger = logging.getLogger(__name__)


class ContextSummarizer:
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
                logger.warning("Gemini summarizer unavailable, using deterministic fallback: %s", exc)

    def summarize(self, matchup: str, docs: List[Dict]) -> str:
        if not docs:
            return (
                "Insufficient recent context available for this matchup. "
                "Model probabilities are available, but context insights are deferred until sources are refreshed."
            )

        if not self._use_gemini:
            return self._fallback_summary(matchup, docs)

        prompt = self._build_prompt(matchup, docs)
        try:
            response = self._genai.GenerativeModel(config.RAG_SUMMARY_MODEL).generate_content(  # type: ignore[union-attr]
                prompt,
                generation_config={"temperature": 0.2, "max_output_tokens": 240},
            )
            text = (response.text or "").strip()
            if text:
                return text
        except Exception as exc:
            logger.warning("Gemini summarization failed, using fallback: %s", exc)

        return self._fallback_summary(matchup, docs)

    @staticmethod
    def _build_prompt(matchup: str, docs: List[Dict]) -> str:
        bullets = []
        for idx, doc in enumerate(docs[:6], start=1):
            bullets.append(
                f"{idx}. [{doc.get('source')}] {doc.get('title')} | "
                f"published_at={doc.get('published_at')} | excerpt={doc.get('content', '')[:280]}"
            )
        context_blob = "\n".join(bullets)
        return (
            "You are generating a concise NBA game context brief for a sports analytics dashboard.\n"
            "Rules:\n"
            "- Use only provided context snippets.\n"
            "- If context is weak, say that directly.\n"
            "- Keep output to 3-5 sentences.\n"
            "- Mention concrete risk factors where present (injury/rest/travel).\n\n"
            f"Matchup: {matchup}\n"
            f"Context:\n{context_blob}\n"
        )

    @staticmethod
    def _fallback_summary(matchup: str, docs: List[Dict]) -> str:
        top = docs[:3]
        headlines = "; ".join(doc.get("title", "context update") for doc in top if doc.get("title"))
        return (
            f"Context brief for {matchup}: {headlines}. "
            "Review cited sources for player availability and schedule-related risk before final bet decisions."
        )
