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
app.include_router(router)

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
            "bet_sizing": "/api/v1/predictions/bet-sizing",
            "system_status": "/api/v1/system/status",
            "docs": "/docs",
        },
    }
