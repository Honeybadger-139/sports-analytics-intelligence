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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(
    title="Sports Analytics Intelligence Platform",
    description="ML-powered sports analytics with prediction, explainability, and risk optimization",
    version="1.0.0",
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
app.include_router(router)
app.include_router(intelligence_router)
app.include_router(mlops_router)

# Serve static frontend files (Phase 4)
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "name": "Sports Analytics Intelligence Platform",
        "version": "1.0.0",
        "status": "operational",
        "phase": "Phase 2 Complete — Prediction Engine + Resilience",
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
            "mlops_retrain_policy": "/api/v1/mlops/retrain/policy?dry_run=true",
            "bets_create": "POST /api/v1/bets",
            "bets_history": "/api/v1/bets",
            "bets_summary": "/api/v1/bets/summary",
            "system_status": "/api/v1/system/status",
            "docs": "/docs",
        },
    }
