"""
prediction_enricher.py — SCR-331

Enriches base ML predictions for upcoming games with RAG-sourced news context.

WHAT THIS DOES:
  For each game scheduled today or tomorrow that has base predictions but no
  news enrichment yet, we:
  1. Query the RAG vector store for recent news about both teams
     (injuries, lineup changes, form, travel, coach comments)
  2. Ask Gemini to extract a structured confidence adjustment from that context
  3. Apply a bounded adjustment (±10pp max) to the ensemble prediction
  4. Persist the adjusted probabilities + news summary back to the predictions table

WHY BOUNDED ADJUSTMENT:
  The ML models capture long-run team strength.  News captures short-run shocks.
  We don't want one injury report to flip a 70/30 prediction to 20/80 — that's
  over-fitting to noisy signals.  A ±10 percentage point cap keeps the final
  probability grounded in statistical reality while incorporating context.

WHEN THIS RUNS:
  Called from run_rag_refresh.py AFTER the RAG index is refreshed, so the news
  used for enrichment is always fresh (≤6h old).
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger("gamethread.prediction_enricher")

# Maximum probability shift the news layer can apply (±10pp)
MAX_ADJUSTMENT_PP = 0.10

ENRICHMENT_PROMPT = """\
You are a sports analytics assistant. Based on the following recent news \
about an upcoming NBA game, estimate how much the home team's win probability \
should be adjusted.

Game: {home_team} (home) vs {away_team} (away)
Current base prediction: {home_team} win probability = {base_prob:.1%}

Recent news context:
---
{news_context}
---

Respond ONLY with valid JSON in this exact format:
{{
  "adjustment": <float between -0.10 and 0.10>,
  "reasoning": "<one sentence explanation>",
  "key_factors": ["<factor 1>", "<factor 2>"]
}}

Rules:
- adjustment > 0 means news favours the home team
- adjustment < 0 means news favours the away team
- Use 0.0 if news is neutral or irrelevant
- Max magnitude is 0.10 (10 percentage points)
"""


def _get_upcoming_games_needing_enrichment(engine, days_ahead: int = 1) -> list[dict]:
    """Return scheduled games that have base predictions but no news enrichment."""
    from sqlalchemy import text

    today = date.today()
    cutoff = today + timedelta(days=days_ahead)

    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT DISTINCT
                    m.game_id,
                    m.game_date,
                    ht.abbreviation AS home_abbr,
                    ht.full_name    AS home_name,
                    at.abbreviation AS away_abbr,
                    at.full_name    AS away_name,
                    p.home_win_prob AS base_home_prob
                FROM matches m
                JOIN teams ht ON m.home_team_id = ht.id
                JOIN teams at ON m.away_team_id = at.id
                JOIN predictions p
                    ON p.game_id = m.game_id AND p.model_name = 'ensemble'
                WHERE m.is_completed = FALSE
                  AND m.game_date BETWEEN :today AND :cutoff
                  AND (p.enriched_at IS NULL OR p.enriched_at < NOW() - INTERVAL '4 hours')
                ORDER BY m.game_date, m.game_id
            """),
            {"today": today, "cutoff": cutoff},
        ).fetchall()

    return [dict(r._mapping) for r in rows]


def _query_rag_for_teams(home_name: str, away_name: str) -> str:
    """
    Query the RAG vector store for recent news about both teams.
    Returns concatenated relevant passages (max ~1200 chars).
    """
    try:
        from src.intelligence.rag_service import RAGService
        rag = RAGService()
        query = (
            f"NBA news injuries lineup changes {home_name} {away_name} "
            f"recent form fatigue back-to-back"
        )
        results = rag.query(query, n_results=6)
        if not results:
            return ""
        passages = [r.get("document", "") or r.get("text", "") for r in results]
        combined = "\n\n".join(p[:300] for p in passages if p)
        return combined[:1500]
    except Exception as exc:
        logger.warning("[enricher] RAG query failed for %s vs %s: %s", home_name, away_name, exc)
        return ""


def _call_gemini(prompt: str) -> Optional[dict]:
    """Call Gemini and parse the structured JSON response."""
    try:
        import google.generativeai as genai
        import os
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.1, "max_output_tokens": 256},
        )
        text = response.text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as exc:
        logger.warning("[enricher] Gemini call failed: %s", exc)
        return None


def enrich_predictions_with_news(engine) -> int:
    """
    Main entry point. Enriches all upcoming games that need it.
    Returns the number of games enriched.
    """
    try:
        from sqlalchemy.orm import Session
        from src.data.prediction_store import persist_news_enrichment, ensure_pre_game_columns
    except ImportError as exc:
        logger.warning("[enricher] deps not available: %s", exc)
        return 0

    with Session(engine) as session:
        ensure_pre_game_columns(session)

    games = _get_upcoming_games_needing_enrichment(engine)
    if not games:
        logger.info("[enricher] no upcoming games need enrichment")
        return 0

    logger.info("[enricher] enriching %d game(s) with RAG news context", len(games))
    enriched = 0

    with Session(engine) as session:
        for game in games:
            try:
                news_text = _query_rag_for_teams(game["home_name"], game["away_name"])

                if not news_text:
                    # No news found — persist empty context so we don't retry for 4h
                    persist_news_enrichment(
                        session,
                        game_id=game["game_id"],
                        model_name="ensemble",
                        news_context={"passages": [], "adjustment": 0.0, "reasoning": "No relevant news found"},
                    )
                    enriched += 1
                    continue

                prompt = ENRICHMENT_PROMPT.format(
                    home_team=game["home_name"],
                    away_team=game["away_name"],
                    base_prob=float(game["base_home_prob"] or 0.5),
                    news_context=news_text,
                )
                result = _call_gemini(prompt)

                if not result:
                    logger.warning("[enricher] no Gemini result for %s", game["game_id"])
                    continue

                raw_adj = float(result.get("adjustment", 0.0))
                # Clamp to ±MAX_ADJUSTMENT_PP
                adjustment = max(-MAX_ADJUSTMENT_PP, min(MAX_ADJUSTMENT_PP, raw_adj))
                base_prob = float(game["base_home_prob"] or 0.5)
                adjusted_prob = round(max(0.05, min(0.95, base_prob + adjustment)), 4)

                news_context = {
                    "passages_used": len(news_text.split("\n\n")),
                    "adjustment": adjustment,
                    "reasoning": result.get("reasoning", ""),
                    "key_factors": result.get("key_factors", []),
                    "base_prob": base_prob,
                    "adjusted_prob": adjusted_prob,
                }

                persist_news_enrichment(
                    session,
                    game_id=game["game_id"],
                    model_name="ensemble",
                    news_context=news_context,
                    home_win_prob_adjusted=adjusted_prob if adjustment != 0 else None,
                )

                logger.info(
                    "[enricher] %s vs %s — base %.1f%% → adjusted %.1f%% (Δ%+.1f%%) | %s",
                    game["home_abbr"],
                    game["away_abbr"],
                    base_prob * 100,
                    adjusted_prob * 100,
                    adjustment * 100,
                    result.get("reasoning", ""),
                )
                enriched += 1

            except Exception as exc:
                logger.warning("[enricher] failed for %s: %s", game.get("game_id"), exc)

    return enriched
