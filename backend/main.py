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

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
import os
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.logging_setup import configure_logging, trace_id_var
from src.data.db import get_db
from src.rate_limit import (
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
    limiter,
    rate_limit_available,
)

configure_logging()

logger = logging.getLogger(__name__)
_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5174,http://localhost:3000,https://sports-analytics-intelligence.vercel.app",
)
ALLOWED_ORIGINS = [origin.strip() for origin in _raw_origins.split(",") if origin.strip()]
EMBEDDED_SCHEDULER_ENABLED = os.getenv("EMBEDDED_SCHEDULER_ENABLED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


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

    scheduler = None
    if EMBEDDED_SCHEDULER_ENABLED:
        # Start the daily ingestion scheduler only in local/dev mode.
        from scheduler import create_scheduler

        scheduler = create_scheduler()
        scheduler.start()
        logger.info("⏰ [lifespan] Daily pipeline scheduler started.")
    else:
        logger.info("⏰ [lifespan] Scheduler disabled - using Cloud Run Jobs in production.")

    try:
        from src.api.routes import get_predictor
        import pandas as pd

        warmup_started = time.perf_counter()
        predictor = get_predictor()
        feature_columns = predictor.feature_columns or []
        if feature_columns:
            dummy_features = pd.DataFrame([[0.0] * len(feature_columns)], columns=feature_columns)
            predictor.predict_game(dummy_features)
            warmup_ms = round((time.perf_counter() - warmup_started) * 1000, 2)
            logger.info("🔥 [lifespan] Model warm-up complete in %sms", warmup_ms)
        else:
            logger.warning("⚠️ [lifespan] Skipping model warm-up — feature columns unavailable.")
    except Exception as exc:
        logger.warning("⚠️ [lifespan] Model warm-up failed (non-fatal): %s", exc)

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
        if scheduler is not None:
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
    allow_origins=ALLOWED_ORIGINS,
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


@app.get("/healthz", include_in_schema=False)
async def healthz():
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
async def readyz(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        from src.api.routes import get_predictor

        predictor = get_predictor()
        models_loaded = bool(getattr(predictor, "models", {}))
        if not models_loaded:
            raise RuntimeError("Predictor models are not loaded")
        return {"status": "ready", "db": "ok", "models_loaded": True}
    except Exception as exc:
        logger.warning("⚠️ [readyz] readiness check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "db": "error",
                "models_loaded": False,
                "error": str(exc),
            },
        )

# Include API routes
from src.api.routes import router
from src.api.intelligence_routes import router as intelligence_router
from src.api.mlops_routes import router as mlops_router
from src.api.chat_routes import router as chat_router
from src.api.scribble_routes import router as scribble_router
from src.api.lab_routes import router as lab_router
from src.api.admin_routes import router as admin_router
from src.api.stats_routes import router as stats_router        # Phase 6.4 — Statistics (SCR-326)
from src.api.forecast_routes import router as forecast_router  # Phase 6.5 — Time-Series (SCR-327)
app.include_router(router)
app.include_router(intelligence_router)
app.include_router(mlops_router)
app.include_router(chat_router)
app.include_router(scribble_router)
app.include_router(lab_router)    # Wave 3: dead-letter inspection
app.include_router(admin_router)  # Wave 3: runtime config management
app.include_router(stats_router)     # Phase 6.4: Bradley-Terry, DiD, SPRT
app.include_router(forecast_router)  # Phase 6.5: Prophet+ARIMA forecasts, momentum

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
            "chat_agents": "POST /api/v1/chat/agents",
            "stats_team_ratings": "/api/v1/stats/team-ratings?season=2025-26",
            "stats_home_court_effect": "/api/v1/stats/home-court-effect",
            "stats_ab_test": "POST /api/v1/stats/ab-test",
            "forecast_team": "/api/v1/forecast/{team_name}?season=2025-26",
            "forecast_momentum": "/api/v1/forecast/{team_name}/momentum",
            "forecast_league": "/api/v1/forecast/league/momentum",
            "docs": "/docs",
        },
    }
