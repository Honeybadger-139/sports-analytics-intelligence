# LangChain / LangGraph Deep Dive

> **Module**: Phase 6.1 — SCR-317
> **Project**: Sports Analytics Intelligence Platform
> **Date**: 2026-03-26

---

## What Is It?

**LangChain** is an orchestration framework for LLM applications. It provides:
- **Chains** — composable pipelines (prompt → LLM → parser)
- **Tools** — callable functions that LLMs can choose to invoke
- **Memory** — persistence layer for conversation state
- **Runnables** — a universal interface (`.invoke()`, `.stream()`, `.batch()`)

**LangGraph** is a state machine layer on top of LangChain. It lets you build:
- **Stateful, multi-step workflows** where each step can branch
- **Cycles** — a node can re-run (retry DB queries, loop until quality threshold)
- **Multi-agent systems** — multiple LLMs cooperating via shared state

Think of LangChain as the LEGO bricks, LangGraph as the instruction manual that says which bricks connect where.

---

## Why Does It Matter?

50% of DS/AI job postings on LinkedIn mention LangChain or LangGraph explicitly.

More importantly, the *pattern* matters even when the framework isn't named:
- Tool-calling agent → almost every production AI system
- Memory-backed chat → every customer service / analytics chatbot
- State machine orchestration → every complex LLM workflow

**Without LangGraph**: you write `if intent == "db": call_db() elif intent == "rag": call_rag()` — flat, brittle, hard to extend.

**With LangGraph**: you define nodes and edges. New capabilities = new nodes. No spaghetti conditionals.

---

## How Does It Work? (Intuition)

### LangGraph State Machine

```
memory_load → policy_gate → route_intent → rewrite_query
                                │
              ┌─────────────────┼──────────────────┐
              ↓                 ↓                  ↓
          rag_retrieve      db_query          off_topic
              ↓                 ↓
          rag_quality_gate  db_retry?
              ↓                 ↓
          rag_respond        finalize
              ↓
          memory_save → finalize
```

Each **node** = a Python function `(state: dict) -> dict`. It reads from state, returns updates.
Each **edge** = a connection. Conditional edges = `if state["intent"] == "rag": go to rag_retrieve`.

The `StateGraph` merges node outputs into a shared state dict automatically. No passing arguments between functions.

### LangChain Tools

A **Tool** is a function with a name, description, and schema. The LLM reads the description to decide *which* tool to call.

```python
class SQLQueryTool(BaseTool):
    name = "sql_query_tool"
    description = "Use this to query NBA stats from the database..."

    def _run(self, question: str) -> str:
        # calls NL→SQL→execute pipeline
        return reply
```

The key insight: **tools decouple what a capability does from how it's invoked**. The chatbot doesn't know whether it's calling a DB or an API — it just calls `tool.run(input)`.

---

## What We Built (Platform Implementation)

### 5 Tools (`langchain_tools.py`)

| Tool | Wraps | Use Case |
|------|-------|----------|
| `SQLQueryTool` | `ChatService._db_reply()` | Stats, standings, records |
| `RAGRetrieverTool` | `ContextRetriever.retrieve()` | News, injuries, context |
| `TeamStatsTool` | Direct SQL (fast path) | Team summary stats |
| `PredictionTool` | `Predictor` + team win rates | Win probability |
| `ExplainabilityTool` | `explain_prediction()` SHAP | Why the model predicted X |

**Key decision**: Factory pattern `create_tools(db, sport)` instead of global instances.
**Why**: DB session is request-scoped. If tools were global, they'd share connections across requests → race conditions in multi-threaded FastAPI.

### Structured Output (`output_schemas.py`)

```python
class GameAnalysis(BaseModel):
    home_win_probability: float  # clamped [0,1]
    key_factors: List[KeyFactor]
    narrative: str
```

**Why Pydantic over raw strings?**
- Field clamping: probability of 1.5 → silently becomes 1.0
- Default values: partial LLM output doesn't crash the graph
- `.model_dump()` → JSON for API responses, zero extra code

### PostgreSQL Memory (`memory.py`)

```
chat_sessions:  id | session_id | sport | created_at | last_active_at | turn_count
chat_messages:  id | session_id | role  | content    | created_at
```

`add_message(session_id, role, content)` → INSERT + UPDATE last_active_at
`get_history(session_id, max_turns=10)` → SELECT ORDER BY DESC LIMIT N, then reversed

**Why not Redis?** Extra infra, extra ops cost. PostgreSQL is already running. For a chatbot with <1000 concurrent sessions, PostgreSQL is fast enough (indexed by session_id + created_at).

**Why not LangChain's built-in memory?** It uses in-memory lists. In a Cloud Run environment that scales to zero, the list dies between requests.

---

## When to Use vs Alternatives

| Approach | When to use |
|----------|-------------|
| **LangGraph** | Multi-step workflows, branching logic, retry loops |
| **LangChain chains** | Simple linear pipelines (prompt → LLM → parse) |
| **Direct LLM calls** | Single-turn, no branching, no memory needed |
| **Semantic Kernel** | .NET shops, Azure-first organizations |
| **DSPy** | When you want to optimise prompts via gradient-based search |

---

## Interview Questions

### Q1: Why use LangGraph instead of just `if/else` conditionals?
**Junior**: "LangGraph is a framework that handles routing."
**Senior**: "LangGraph lets me define the workflow as a directed graph — nodes are capabilities, edges are control flow. When I add a new capability (say, a Prediction node), I add one node and two edges. With `if/else`, I'd need to touch every branch. LangGraph also gives me cycle support — I can retry a DB query without a while loop, just add an edge back to db_query."

### Q2: How does conversation memory work in production?
**Junior**: "I store history in a list and pass it to the LLM."
**Senior**: "In-memory lists die on container restarts — Cloud Run scales to zero between requests. I use PostgreSQL-backed memory: each turn is persisted to a `chat_messages` table keyed by session_id. The LangGraph graph loads history at the start via a `memory_load` node and saves the reply via `memory_save`. This means any replica can serve any session."

### Q3: What's the difference between a LangChain Tool and a Runnable?
**Senior**: "A Runnable is LangChain's universal interface — anything with `.invoke()`. A Tool is a Runnable with extra metadata: name, description, and input schema. The description is what enables LLM-driven tool selection — the model reads descriptions to decide which tool to call. In our system, we don't use LLM-driven tool selection yet (the graph hardcodes routing), but the tool abstraction means we can upgrade to full tool-calling with one config change."

### Q4: How would you scale this to 10K concurrent users?
**Senior**: "Three things: (1) The LangGraph graph is stateless per-request — no singleton state, so horizontal scaling is free. (2) PostgreSQL memory has an index on `(session_id, created_at)` — reads are O(log n). For 10K users, we'd add a read replica. (3) The tools use the same SQLAlchemy session pool as the rest of the API — connection pooling is already configured in db.py."

---

## "Awe Moment" Insights for Interviews

**1. Zero capability duplication**
The chatbot uses the same prediction engine as the REST API. When the ML team updates the model, the chatbot automatically uses the new version. No sync required.

**2. Tools as the abstraction boundary**
The LangGraph graph doesn't know whether `sql_query_tool` hits PostgreSQL, BigQuery, or a mock. Swap the implementation, the graph stays identical. This is dependency inversion applied to AI systems.

**3. Memory-load as a graph node**
Most tutorials show memory as a parameter you pass in. We made it a node — `memory_load` runs at the start of every graph invocation. This means memory loading participates in LangGraph's tracing, timing, and error handling like any other step. You can observe how long memory loading takes in Langfuse.

---

## Files Created (SCR-317)

| File | Purpose |
|------|---------|
| `backend/src/intelligence/langchain_tools.py` | 5 LangChain tools |
| `backend/src/intelligence/output_schemas.py` | Pydantic output schemas |
| `backend/src/intelligence/memory.py` | PostgreSQL-backed memory |
| `backend/alembic/versions/0003_add_chat_memory_table.py` | DB migration |
| `backend/tests/test_langchain_tools.py` | Unit tests |
| `backend/src/intelligence/langgraph_chat_service.py` | Refactored (memory + tools wired) |

---

## Next Module

**6.2 PyTorch Neural Network** (SCR-318) — add MLP game predictor, compare with XGBoost, learn when neural nets beat trees (spoiler: rarely on tabular data, but embeddings change the game).
