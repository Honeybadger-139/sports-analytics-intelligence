# API Layer — Learning Notes

> 📌 **Status**: Implemented — FastAPI REST API serving predictions, health checks, and system observability.

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
| `GET /api/v1/predictions/bet-sizing` | Kelly Criterion stake sizing |
| `GET /api/v1/features/{id}` | Computed features for a game |
| `GET /api/v1/system/status` | Pipeline health + audit trail |

## Key Design Patterns

1. **Dependency Injection**: Database sessions via `Depends(get_db)` — FastAPI auto-manages lifecycle
2. **Lazy Loading**: ML models loaded on first request, not at startup
3. **CORS Middleware**: Allows frontend to call API from any origin (dev mode)
4. **API Versioning**: All routes under `/api/v1/` for future backwards compatibility

## Interview Angle

> "I designed a stateless REST API that separates model serving from model training. The API lazy-loads model artifacts and uses FastAPI's dependency injection for database session management. This lets us scale horizontally — add more API instances behind a load balancer without shared state."
