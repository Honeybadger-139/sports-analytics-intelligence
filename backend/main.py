"""
GameThread — FastAPI Backend

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
import signal
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
import os

from src.logging_setup import configure_logging, trace_id_var
from src.rate_limit import (
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
    limiter,
    rate_limit_available,
)

configure_logging()

logger = logging.getLogger(__name__)


def _configure_metrics(app: FastAPI) -> None:
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator().instrument(app).expose(app)
    except Exception as exc:
        logger.warning("Prometheus instrumentator unavailable, exposing fallback /metrics endpoint: %s", exc)

        @app.get("/metrics", include_in_schema=False)
        async def metrics_fallback():
            return PlainTextResponse(
                "gamethread_metrics_available 0\n",
                media_type="text/plain; version=0.0.4",
            )


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

    # ── Wave 3: Run Alembic migrations on startup ─────────────────────────────
    try:
        import subprocess, sys, os as _os
        alembic_cfg = _os.path.join(_os.path.dirname(__file__), "alembic.ini")
        if _os.path.exists(alembic_cfg):
            result = subprocess.run(
                [sys.executable, "-m", "alembic", "-c", alembic_cfg, "upgrade", "head"],
                capture_output=True,
                text=True,
                cwd=_os.path.dirname(__file__),
            )
            if result.returncode == 0:
                logger.info("🗄️  [lifespan] Alembic migrations applied: %s", result.stdout.strip() or "already up to date")
            else:
                logger.warning("⚠️  [lifespan] Alembic migration warning: %s", result.stderr.strip())
        else:
            logger.info("🗄️  [lifespan] alembic.ini not found — skipping migration step.")
    except Exception as _alembic_exc:
        logger.warning("⚠️  [lifespan] Alembic startup migration failed (non-fatal): %s", _alembic_exc)

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

    previous_sigterm = signal.getsignal(signal.SIGTERM)

    def _handle_sigterm(signum, frame):  # type: ignore[unused-arg]
        logger.info("🛑 [lifespan] SIGTERM received, waiting for scheduler jobs to finish.")
        if callable(previous_sigterm):
            previous_sigterm(signum, frame)

    signal.signal(signal.SIGTERM, _handle_sigterm)

    yield

    # Flush any pending Langfuse traces before shutdown
    if langfuse_ready:
        try:
            from langfuse import get_client
            get_client().flush()
        except Exception:
            pass

    try:
        job_state = [job.id for job in scheduler.get_jobs()]
        scheduler.shutdown(wait=True)
        logger.info("🛑 [lifespan] Daily pipeline scheduler stopped. final_jobs=%s", job_state)
    except Exception as exc:
        logger.warning("🛑 [lifespan] Scheduler shutdown encountered an issue: %s", exc)
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)

    logger.info("🛑 [lifespan] Shutdown complete.")


app = FastAPI(
    title="GameThread",
    description="ML-powered sports analytics with prediction, explainability, and risk optimization",
    version="1.0.0",
    lifespan=lifespan,
)
_configure_metrics(app)
if limiter is not None:
    app.state.limiter = limiter
if rate_limit_available and RateLimitExceeded is not None and _rate_limit_exceeded_handler is not None:
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware — allows the HTML frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_trace_context(request: Request, call_next):
    trace_id = str(uuid.uuid4())
    token = trace_id_var.set(trace_id)
    started = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logging.getLogger("gamethread.request").info(
            "request_completed",
            extra={
                "trace_id": trace_id,
                "route": request.url.path,
                "duration_ms": duration_ms,
                "status_code": getattr(response, "status_code", 500),
                "method": request.method,
            },
        )
        trace_id_var.reset(token)

# Include API routes
from src.api.routes import router
from src.api.intelligence_routes import router as intelligence_router
from src.api.mlops_routes import router as mlops_router
from src.api.chat_routes import router as chat_router
from src.api.scribble_routes import router as scribble_router
from src.api.lab_routes import router as lab_router
from src.api.admin_routes import router as admin_router
app.include_router(router)
app.include_router(intelligence_router)
app.include_router(mlops_router)
app.include_router(chat_router)
app.include_router(scribble_router)
app.include_router(lab_router)    # Wave 3: dead-letter inspection
app.include_router(admin_router)  # Wave 3: runtime config management

# Serve the production build of the React frontend (frontend/dist/)
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "name": "GameThread",
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
