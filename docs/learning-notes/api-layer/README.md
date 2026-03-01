# API Layer — Learning Notes

> 📌 **Status**: Implemented — FastAPI REST API serving predictions, health checks, observability, and bankroll ledger operations.

## What Is the API Layer?

The API Layer exposes the platform's capabilities as RESTful endpoints using FastAPI. It's the interface between the ML Engine and the outside world (frontend, mobile apps, third-party integrations).

## Implemented Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/health` | Simple liveness check |
| `GET /api/v1/teams` | All 30 NBA teams |
| `GET /api/v1/matches` | Games with filters (season, team, limit) |
| `GET /api/v1/standings` | Win-loss standings by season |
| `GET /api/v1/predictions/game/{id}` | ML prediction + SHAP explanation |
| `GET /api/v1/predictions/today` | Batch predictions for today's scheduled games |
| `GET /api/v1/predictions/performance` | Historical model accuracy + calibration metrics |
| `GET /api/v1/predictions/bet-sizing` | Kelly Criterion stake sizing |
| `POST /api/v1/bets` | Create pending bet in bankroll ledger |
| `GET /api/v1/bets` | Fetch bet history with filters (`season`, `result`) |
| `POST /api/v1/bets/{id}/settle` | Settle bet (`win/loss/push`) and compute PnL |
| `GET /api/v1/bets/summary` | Aggregate bankroll KPIs (PnL, ROI, open/settled mix) |
| `GET /api/v1/features/{id}` | Computed features for a game |
| `GET /api/v1/system/status` | Pipeline health + audit trail |
| `POST /api/v1/chat` | AI chatbot — hybrid RAG+DB query engine (Phase 7B) |
| `POST /api/v1/scribble/query` | Read-only SQL execution for data playground (Phase 7C) |

## Key Design Patterns

1. **Dependency Injection**: Database sessions via `Depends(get_db)` — FastAPI auto-manages lifecycle
2. **Lazy Loading**: ML models loaded on first request, not at startup
3. **CORS Middleware**: Allows frontend to call API from any origin (dev mode)
4. **API Versioning**: All routes under `/api/v1/` for future backwards compatibility
5. **Operational Traceability**: Prediction + betting outputs are persisted for reproducible analysis

## Phase 2 Interview Notes

### What Is It?
Phase 2 turns the API from a stateless prediction surface into an operations surface:
- prediction outputs are persisted,
- outcomes are synchronized,
- bankroll actions are logged and settled.

### Why It Matters
Without persistence, you cannot prove model quality or portfolio discipline. Interviewers care about this because real ML systems are judged by production outcomes, not only point-in-time scores.

### How It Works (Intuition)
1. Predict tonight's games and optionally persist model outputs.
2. After games finish, sync truth labels (`was_correct`) for each stored prediction.
3. Log betting decisions in a ledger (`bets`) and settle them using deterministic PnL rules.
4. Expose summary metrics (`accuracy`, `brier`, `ROI`, bankroll curve inputs) through APIs.

### When to Use vs Alternatives
- Use this API-ledger model when you need transparent audits and frontend portability.
- A notebook-only flow is faster initially, but weak for interview storytelling and cross-team collaboration.

### Senior Manager Perspective
This design creates a measurable feedback loop: model quality, decision quality, and capital impact all become queryable artifacts. That is the foundation for later monitoring, retraining, and risk policy automation.

### Common Interview Questions
1. Why persist predictions instead of recalculating later?
2. How do you prevent data leakage in post-game performance metrics?
3. Why expose Brier score alongside accuracy?
4. How would you handle duplicate or amended bets in a real sportsbook integration?
5. What controls would you add before enabling auto-bet placement?

## Phase 7 Additions

### `POST /api/v1/chat` — Chatbot endpoint

```python
# chat_routes.py
@router.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    service = ChatService(sport=request.sport or 'nba')
    return service.chat(request.message, request.history)
```

- **Request**: `{ message, history[], sport? }`
- **Response**: `{ reply, path: "rag"|"db"|"off_topic", sql_used?, citations? }`
- HTTP 500 with detail message on unexpected errors (graceful degradation)
- Registered in `main.py` as `chat_router`

See `intelligence-layer/README.md` for the full backend architecture.

### `POST /api/v1/scribble/query` — Safe SQL endpoint

```python
# scribble_routes.py
@router.post("/scribble/query")
async def run_query(req: QueryRequest, db: Session = Depends(get_db)) -> QueryResponse:
    # Validate → execute in read-only transaction → return rows
```

- **Request**: `{ sql: str }`
- **Response**: `{ columns: str[], rows: any[][], row_count: int }`
- Security layers: regex whitelist, DML blocklist, 500-row cap, 10s timeout, read-only transaction
- Registered in `main.py` as `scribble_router`

See `frontend/scribble-playground.md` for the full security rationale.

---

## Interview Angle

> "I designed a stateless REST API that separates model serving from model training. The API lazy-loads model artifacts and uses FastAPI's dependency injection for database session management. This lets us scale horizontally — add more API instances behind a load balancer without shared state."

> "The chat endpoint delegates all intelligence logic to `ChatService` — the route is intentionally thin. Routes are contracts; services are implementations. This separation makes the chatbot logic testable without an HTTP layer."

> "The Scribble SQL endpoint enforces security at the application layer: SELECT-only via regex, DML blocklist, read-only transaction, and a 500-row cap. This is defense-in-depth without requiring infrastructure changes."
