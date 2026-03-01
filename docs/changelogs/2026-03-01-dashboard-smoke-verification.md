# Dashboard Smoke Verification

Date: 2026-03-01 (Asia/Kolkata)  
Scope: Runtime launch + basic dashboard/API checks before manual UX review

## Launch Confirmation

1. Dashboard served at:
   - `http://127.0.0.1:8001/`
2. Dashboard URL opened in browser for manual review.

## Basic Smoke Test Cases

1. Home page availability:
   - `GET /` -> HTML served (dashboard page loads)
2. Predictions feed:
   - `GET /api/v1/predictions/today` -> 200, payload returned (`count=0` for current date)
3. Raw Data Explorer source contract:
   - `GET /api/v1/raw/tables?season=2025-26` -> 200, table catalog returned
4. Data Quality module contract:
   - `GET /api/v1/quality/overview?season=2025-26` -> 200, quality checks + row counts returned
5. Intelligence module contract:
   - `GET /api/v1/intelligence/game/0022500859?season=2025-26` -> 200, summary + citations payload returned
6. MLOps monitoring card contract:
   - `GET /api/v1/mlops/monitoring?season=2025-26` -> 200, metrics + alerts payload returned
7. Bankroll summary card contract:
   - `GET /api/v1/bets/summary` -> 200, summary payload returned

## Environment Note

PostgreSQL and pgAdmin containers are running (`docker-compose ps`):
- `sports-analytics-db`: healthy
- `sports-analytics-pgadmin`: up

## Review Handoff

Manual UI/UX review is now ready on the opened dashboard URL.  
No additional changes were applied in this batch beyond verification logging.
