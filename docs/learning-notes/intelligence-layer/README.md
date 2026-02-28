# Intelligence Layer — Learning Notes

> 📌 **Status**: Implemented baseline in **Phase 4A/4B foundation**.

## What Is the Intelligence Layer?

The Intelligence Layer is the "context brain" of the dashboard:

1. Retrieve relevant NBA context (news + injury feeds).
2. Summarize the context with citations.
3. Add deterministic risk overlays (injury/rest/travel/staleness).
4. Present context separately from raw model probability.

Think of it as:
- **Model** = "What is likely to happen?"
- **Intelligence Layer** = "What real-world context might change our confidence?"

## Implemented Architecture (Current)

Modules in `backend/src/intelligence/`:

1. `news_agent.py`
   - Fetches RSS and injury feeds
   - Normalizes docs to:
     - `doc_id`, `source`, `title`, `url`, `published_at`, `team_tags[]`, `player_tags[]`, `content`
2. `embeddings.py`
   - Gemini embedding path (if key + package available)
   - Deterministic hash embedding fallback (offline-safe)
3. `vector_store.py`
   - Chroma persistent store if available
   - JSON vector store fallback if Chroma unavailable
4. `retriever.py`
   - semantic retrieval + freshness filter + team filter
5. `summarizer.py`
   - Gemini summarization if available
   - deterministic summary fallback
6. `rules.py`
   - deterministic risk signals:
     - injury keywords
     - short rest/back-to-back
     - travel fatigue proxy
     - stale context
7. `service.py`
   - Orchestrates indexing, retrieval, summarization, rules, response shape

## Dashboard Integration

1. **Analysis > Match Deep Dive**
   - Added `Context Brief (RAG)` card
   - shows summary + risk chips + citations
2. **Intelligence Tab**
   - Daily brief table
   - selected game citation inspector
   - MLOps monitoring + retrain dry-run panel

## API Contracts

1. `GET /api/v1/intelligence/game/{game_id}`
   - returns:
     - `summary`
     - `risk_signals[]`
     - `citations[]`
     - `retrieval` stats
     - `coverage_status`
2. `GET /api/v1/intelligence/brief?date=YYYY-MM-DD`
   - returns date/season + list of game briefs

## Guardrails We Enforced

1. No citations -> response marks context as insufficient.
2. Retrieval includes freshness window metadata.
3. Rule overlays are deterministic and auditable.
4. Model probability is never overwritten by context logic.

## Why This Matters (Senior Manager Perspective)

This layer improves decision quality by combining:
- statistical signal (model output)
- operational reality (injuries, schedule, context drift)

The key leadership principle: **separate probabilistic inference from contextual governance** so teams can trust both.

## Interview Angle

> "I implemented a grounded RAG layer that sits beside the model, not inside it. We retrieve NBA context, summarize with citations, and apply deterministic risk overlays. This design prevents hallucinated narrative from silently altering model probabilities."

## Junior vs Senior Answer

1. Junior:
   - "I added LLM summaries to predictions."
2. Senior:
   - "I added a guarded RAG pipeline with citation enforcement, freshness filters, deterministic risk overlays, and fallback behavior for dependency/network failures."
