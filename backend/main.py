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

app = FastAPI(
    title="Sports Analytics Intelligence Platform",
    description="ML-powered sports analytics with prediction, explainability, and risk optimization",
    version="0.1.0",
)

# CORS middleware — allows the HTML frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "name": "Sports Analytics Intelligence Platform",
        "version": "0.1.0",
        "status": "operational",
        "phase": "Phase 1 — Data Foundation",
    }


@app.get("/health")
async def health():
    """Detailed health check including database connectivity."""
    return {
        "api": "healthy",
        "database": "pending",  # Will be updated when DB connection is implemented
        "models": "not_loaded",  # Will be updated in Phase 2
    }


# ---- Phase 1 Routes (Data) ----
# @app.get("/api/v1/teams")
# @app.get("/api/v1/matches/today")
# @app.get("/api/v1/features/{game_id}")

# ---- Phase 2 Routes (Predictions) ----
# @app.get("/api/v1/predictions/today")
# @app.get("/api/v1/predictions/{game_id}")
# @app.get("/api/v1/explain/{game_id}")
# @app.get("/api/v1/sizing/{game_id}")

# ---- Phase 3 Routes (Intelligence) ----
# @app.post("/api/v1/research")
# @app.get("/api/v1/news/{game_id}")

# ---- Phase 4 Routes (Tracking) ----
# @app.post("/api/v1/bets")
# @app.get("/api/v1/bankroll")
# @app.get("/api/v1/performance")
