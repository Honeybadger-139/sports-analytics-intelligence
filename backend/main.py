"""
Sports Analytics Intelligence Platform — FastAPI Backend

This is the entry point for the FastAPI application. It serves ML predictions,
SHAP explanations, and risk-optimized stake sizing via REST API endpoints.

Architecture Decision:
    We chose FastAPI over Flask/Django because:
    - Async support for concurrent API calls (multiple model predictions in parallel)
    - Automatic OpenAPI/Swagger docs (self-documenting API)
    - Pydantic for request/response validation (type safety)
    - Native dependency injection (clean & testable code)
    See docs/decisions/decision-log.md for full rationale.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context — runs startup logic before the app starts
    serving requests, and shutdown logic when the process exits.

    Startup:
        Starts the APScheduler BackgroundScheduler that fires the daily
        NBA ingestion pipeline at PIPELINE_SCHEDULE_HOUR UTC.  The scheduler
        runs in a daemon thread and does NOT block the async event loop.

    Shutdown:
        Gracefully stops the scheduler so in-flight pipeline jobs can finish.
    """
    from scheduler import create_scheduler
    from src.intelligence.langfuse_client import init_langfuse

    # Start Langfuse observability (no-op if keys not set)
    langfuse_ready = init_langfuse()
    if langfuse_ready:
        logger.info("📊 [lifespan] Langfuse observability active.")
    else:
        logger.info("📊 [lifespan] Langfuse observability disabled (set LANGFUSE_* keys to enable).")

    # Start the daily ingestion scheduler
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("⏰ [lifespan] Daily pipeline scheduler started.")

    yield

    # Flush any pending Langfuse traces before shutdown
    if langfuse_ready:
        try:
            from langfuse import get_client
            get_client().flush()
        except Exception:
            pass

    scheduler.shutdown(wait=False)
    logger.info("🛑 [lifespan] Daily pipeline scheduler stopped.")


app = FastAPI(
    title="Sports Analytics Intelligence Platform",
    description="ML-powered sports analytics with prediction, explainability, and risk optimization",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware — allows the HTML frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
from src.api.routes import router
from src.api.intelligence_routes import router as intelligence_router
from src.api.mlops_routes import router as mlops_router
from src.api.chat_routes import router as chat_router
from src.api.scribble_routes import router as scribble_router
app.include_router(router)
app.include_router(intelligence_router)
app.include_router(mlops_router)
app.include_router(chat_router)
app.include_router(scribble_router)

# Serve the production build of the React frontend (frontend/dist/)
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "name": "Sports Analytics Intelligence Platform",
        "version": "1.0.0",
        "status": "operational",
        "phase": "Phase 7 Active — UI Redesign + Chatbot + Scribble",
        "endpoints": {
            "teams": "/api/v1/teams",
            "matches": "/api/v1/matches?season=2025-26",
            "standings": "/api/v1/standings?season=2025-26",
            "predict": "/api/v1/predictions/game/{game_id}",
            "predict_today": "/api/v1/predictions/today",
            "prediction_performance": "/api/v1/predictions/performance?season=2025-26",
            "bet_sizing": "/api/v1/predictions/bet-sizing",
            "intelligence_game": "/api/v1/intelligence/game/{game_id}",
            "intelligence_brief": "/api/v1/intelligence/brief",
            "mlops_monitoring": "/api/v1/mlops/monitoring",
            "mlops_monitoring_trend": "/api/v1/mlops/monitoring/trend?season=2025-26&days=14",
            "mlops_retrain_policy": "/api/v1/mlops/retrain/policy?dry_run=true",
            "mlops_retrain_jobs": "/api/v1/mlops/retrain/jobs?season=2025-26&limit=10",
            "mlops_retrain_worker": "POST /api/v1/mlops/retrain/worker/run-next?execute=false",
            "bets_create": "POST /api/v1/bets",
            "bets_history": "/api/v1/bets",
            "bets_summary": "/api/v1/bets/summary",
            "system_status": "/api/v1/system/status",
            "chat": "POST /api/v1/chat",
            "docs": "/docs",
        },
    }
