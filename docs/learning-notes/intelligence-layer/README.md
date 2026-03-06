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

## Phase 4B Hardening Additions

1. Source quality scoring now penalizes low-signal/noisy betting content.
2. Citation payload now includes:
   - `quality_score`
   - `freshness_hours`
   - `is_stale`
   - `is_noisy`
3. Retrieval payload now includes source-level quality aggregates.
4. Feed health telemetry is captured during indexing and surfaced in game intelligence responses.
5. Intelligence tab now supports operator filtering/sorting so high-risk and high-citation games are prioritized quickly.
6. Rule precision improvements:
   - noisy docs are excluded from injury severity inference
   - mixed injury certainty emits explicit conflict signal

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

---

## Chatbot Backend — Phase 7B (`chat_service.py`)

> **Commits**: `c7b0c6b` | **Linear**: SCR-147

### What was built

`backend/src/intelligence/chat_service.py` — a new module inside the intelligence layer that powers the AI chatbot.

```
POST /api/v1/chat
        ↓
IntentRouter (keyword, <1ms) → "rag" | "db" | "off_topic"
        ↓
    if "rag":  ChromaDB retrieve → LLMClient.synthesise(context)
    if "db":   LLMClient.nl_to_sql(question + schema) → safe execute → LLMClient.narrate(rows)
    if "off_topic": immediate decline, no LLM call
        ↓
{ reply, path, sql_used?, citations? }
```

### Key classes

#### `LLMClient` — Adapter pattern
Single point of LLM contact. Currently wraps Gemini. Swapping to Minimax (or any other provider) requires changing **one class** and zero other files.

```python
class LLMClient:
    def generate(self, prompt: str) -> str: ...
    def embed(self, text: str) -> list[float]: ...
```

Design pattern: **Adapter**. The rest of the system depends on this interface, not on Gemini's SDK. This is how production AI platforms manage provider migrations.

#### `IntentRouter` — keyword classification, no LLM
Routes questions to the correct backend by scoring keyword sets:

- DB keywords: `average`, `points`, `win`, `season`, `stats`, `team`, `player`, `game`, `record`...
- RAG keywords: `news`, `injured`, `report`, `trade`, `suspend`, `latest`...
- Off-topic: score both sets = 0 → immediate decline

**Why no LLM for classification?** LLM intent classification adds 500–1000ms latency. Keyword scoring is deterministic, <1ms, and handles 95% of real queries correctly. The LLM is reserved for what only it can do: synthesising answers.

#### `ChatService` — orchestrator

```python
class ChatService:
    def __init__(self, sport: str = 'nba'):
        self.sport = sport   # designed for future multi-sport extensibility

    def chat(self, message: str, history: list) -> ChatResponse:
        intent = IntentRouter.route(message)
        if intent == 'off_topic': return decline()
        if intent == 'rag':  return self._rag_path(message)
        if intent == 'db':   return self._db_path(message)
```

#### Dynamic schema fetching
For the DB path, `ChatService` fetches live column names from `information_schema.columns` before building the NL→SQL prompt. This prevents SQL hallucination and automatically stays current as the schema evolves.

**Interview framing**: "I gave the LLM a real map, not a rough sketch. Dynamic schema fetching means the LLM always knows the exact column names — hardcoded schemas drift as the DB evolves."

### Off-topic gate
Before any LLM call, the question is checked against the off-topic condition. Questions about recipes, politics, etc. are declined immediately at microsecond cost — no LLM charge, no product scope creep.

### `sport` parameter
`ChatService(sport='nba')` is parameterised from day one. When cricket or football is added, the frontend passes `sport='cricket'`, the service loads sport-specific SQL tables and intent keywords. Open-Closed Principle: extend without modifying.

### API contract

```
POST /api/v1/chat
{ "message": str, "history": [...], "sport": "nba" }

→ { "reply": str, "path": "rag"|"db"|"off_topic",
    "sql_used"?: str, "citations"?: [...] }
```

### Interview Angles

> "I designed the chatbot with intent-aware routing. Stats questions go to SQL, news questions go to RAG. This mirrors how production AI assistants route to different knowledge sources — each tool is used for what it's good at."

> "I applied the Adapter pattern for the LLM client. The rest of the system depends on the interface, not on Gemini. When Minimax goes live, it's a one-class swap."

> "I added a hard off-topic gate before any LLM call. If the question isn't about sports analytics, we decline at zero LLM cost. This keeps the product focused, costs minimal, and behavior auditable."

---

## LangChain + LangGraph Completion — Phase 7 (`langgraph_chat_service.py`)

> **Linear**: SCR-200

### What is it?

`backend/src/intelligence/langgraph_chat_service.py` adds a graph-based orchestration engine on top of the existing chatbot. It keeps the legacy chatbot intact and exposes a feature-flag switch:

- `CHAT_ENGINE=legacy` (default)
- `CHAT_ENGINE=langgraph` (new graph path)

### Why does it matter?

The old service had good logic but mostly linear control flow. LangGraph gives explicit state-machine behavior for guardrails and retries:

1. Intent routing is explicit and testable.
2. RAG quality gate blocks uncited/empty-context narratives.
3. DB retry node enables a deterministic second attempt on known failure replies.
4. Finalize node validates output shape before returning.

This is reliability engineering for LLM systems, not just "using a new framework."

### How it works (intuition first)

```text
route_intent -> rewrite_query ->
  rag: retrieve -> quality_gate -> rag_respond -> finalize
  db : db_query -> (retry?) -> finalize
  off_topic -> finalize
```

- **LangChain usage**: each node tool call is wrapped with `RunnableLambda` for consistent invocation.
- **LangGraph usage**: conditional edges decide branch transitions (`rag`, `db`, `off_topic`, retry/no-retry).
- **Fallback behavior**: if LangGraph deps are unavailable or runtime fails, service falls back to `ChatService`.

### API contract impact

`POST /api/v1/chat` response now includes:

- `reply`
- `intent`
- `engine` (`legacy` or `langgraph`)

`GET /api/v1/chat/health` now reports:

- `chat_engine_configured`
- `chat_engine_active`
- `langgraph_available`

### Evaluation harness (Phase 7 evidence)

`backend/src/intelligence/chat_eval.py` compares legacy vs langgraph on fixed cases:

1. DB analytical query
2. RAG context query
3. off-topic guard query

It records intent match, reply lengths, and basic signal-presence checks into JSON for repeatable comparisons.

### Senior Manager perspective

This phase introduces a controlled migration pattern:

1. Keep production-safe default (`legacy`).
2. Incrementally enable `langgraph`.
3. Keep observability and regression checks during rollout.

That is the same pattern used in platform modernization projects: no risky hard cutovers.

### Common interview questions

1. Why use LangGraph when you already have working Python orchestration?
2. Why a feature flag instead of replacing the old chatbot directly?
3. How do you prevent hallucinations in the RAG path?
4. How does your DB retry policy avoid infinite loops?
5. What metrics in your eval harness would you upgrade next for production?

---

## Phase 8 — Streaming Chat + Offline Observability Hardening

### What was added

1. **Streaming route**: `POST /api/v1/chat/stream` in `chat_routes.py` (SSE).
2. **Frontend stream consumption**: `useChatbot` now consumes token events and renders incremental assistant output.
3. **Safe observability wrapper**: `langfuse_client.observe` now acts as a no-op decorator when tracing is disabled.
4. **Eval resilience**: `chat_eval.py` now:
   - forces local-safe defaults (`LANGFUSE_ENABLED=false`, `OTEL_SDK_DISABLED=true`, empty Gemini key),
   - probes DB availability,
   - skips DB cases when DB is unavailable and still writes a report.

### Why this matters

- Streaming improves perceived latency and user trust ("it is thinking now").
- Fail-open tracing keeps local development clean while preserving production observability as an option.
- Eval scripts now produce artifacts even in restricted environments, which helps CI and interview demos.

### Interview angle

> "I treated streaming as an additive API contract and observability as optional infrastructure. The assistant works in both high-observability and constrained local environments without behavior drift."
