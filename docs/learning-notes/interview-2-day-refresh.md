# Interview 2-Day Refresh

Use this when you return to the project after 1-3 days and need fast recall.

## 1) 60-Second System Pitch

"GameThread is an API-first sports analytics platform. A scheduled ingestion + feature pipeline writes to Postgres, prediction services expose model and SHAP outputs, intelligence services add citation-grounded context, and a React command center organizes workflows across Pulse, Arena, Lab, Scribble, and Chatbot. MLOps snapshots and retrain queue tables close the loop from data freshness to model governance."

## 2) Layer-by-Layer Memory Map

1. Data ingestion: `backend/src/data/ingestion.py`
2. Feature engineering: `backend/src/data/feature_store.py`
3. Prediction serving: `backend/src/models/predictor.py` + `backend/src/api/routes.py`
4. Intelligence/RAG: `backend/src/intelligence/*` + `backend/src/api/intelligence_routes.py`
5. Chatbot orchestration: `backend/src/intelligence/chat_service.py` and `langgraph_chat_service.py`
6. Frontend routing: `frontend/src/App.tsx`
7. Ops loop: `backend/src/mlops/*` + `backend/src/api/mlops_routes.py`

## 3) Endpoint Families To Remember

- Core predictions: `/api/v1/predictions/*`
- Data quality + system health: `/api/v1/quality/overview`, `/api/v1/system/status`
- Intelligence: `/api/v1/intelligence/game/{id}`, `/api/v1/intelligence/brief`
- MLOps: `/api/v1/mlops/monitoring`, `/trend`, `/retrain/*`
- Chat: `/api/v1/chat`, `/api/v1/chat/stream`, `/api/v1/chat/health`
- Scribble: `/api/v1/scribble/query`, `/notebooks`, `/views`, `/ai-sql`

## 4) High-Signal Interview Talking Points

1. Why API-first over notebook-first UI.
2. How you prevented leakage in rolling features.
3. Why prediction persistence matters for real performance measurement.
4. How citation + rule overlays reduce hallucination risk.
5. Why LangGraph was feature-flagged instead of hard-swapped.
6. How retrain policy and queue make MLOps decisions auditable.

## 5) 10-Minute Pre-Interview Checklist

1. Re-read `docs/architecture/system-design.md`.
2. Re-read `docs/learning-notes/api-layer/README.md`.
3. Re-read `docs/learning-notes/intelligence-layer/README.md`.
4. Re-read one recent changelog in `docs/changelogs/`.
5. Prepare one example each for: failure handling, trade-off decision, and measurable impact.
