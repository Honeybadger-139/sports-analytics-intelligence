# Data + RAG Refresh + Dashboard Restart

Date: 2026-03-04 (Asia/Kolkata)  
Scope: Reload core tables, refresh RAG corpus/search index, restart dashboard

## Steps Executed

1. Reloaded core NBA tables (incremental ingestion):
   - `PYTHONPATH=. venv/bin/python src/data/ingestion.py`
2. Recomputed feature tables:
   - `PYTHONPATH=. venv/bin/python src/data/feature_store.py`
3. Forced RAG refresh:
   - `venv/bin/python scheduler.py --run-now-rag`
4. Restarted dashboard API server:
   - `PYTHONPATH=. venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001`
5. Opened dashboard in browser:
   - `http://127.0.0.1:8001/`

## Results Snapshot

1. Ingestion:
   - teams: 30
   - games: 14 (new incremental)
   - players: 570
   - player logs: 303
   - player season aggregates: 546
   - integrity audit: passed
2. Feature engineering:
   - feature rows refreshed: 1690
3. RAG refresh:
   - fetched raw documents: 48 (1 source timed out)
   - chunks upserted: 48
   - vector store total: 71
4. Runtime verification:
   - `/` served dashboard HTML
   - `/api/v1/raw/tables?season=2025-26` returned updated row counts
   - `/api/v1/intelligence/game/0022500859?season=2025-26` returned refreshed context payload

## Notes

- During initial non-elevated run, RAG refresh hit local DB/network sandbox restrictions; rerun with elevated permissions completed successfully.
- Dashboard is currently running on `127.0.0.1:8001`.
