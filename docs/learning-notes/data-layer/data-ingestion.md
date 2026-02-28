# 📥 NBA Data Ingestion Pipeline — Deep Dive

The ingestion pipeline (implemented in `ingestion.py`) is the engine that pulls raw data from the NBA Stats API and transforms it into a structured format for our ML features.

## The ETL Philosophy: Resilience & Correctness

In professional data engineering, "just pulling the data" is only 20% of the work. The other 80% is handling failures, staying under rate limits, and ensuring data integrity.

### 1. Extraction: `nba_api` & Header Engineering
We use the `nba_api` library, but we've hardened it with custom headers to replicate a real browser context.
- **Why**: NBA.com blocks standard Python requests to prevent bot abuse.
- **Solution**: We inject `User-Agent`, `Referer`, and `Origin` headers into every call.

### 2. Transformation: Watermarking for Incremental Sync
Instead of a full refresh every day, we use **Watermarking**.
- **Logic**: `SELECT MAX(game_date) FROM matches WHERE is_completed = TRUE`.
- **Action**: We only fetch/process games *on or after* this date.
- **Phase 0.5 Improvement**: We only trust `is_completed` games as watermarks to avoid skipping games that were initially in a "future" state during a previous sync.

### 3. Loading: Idempotent UPSERTs
We use PostgreSQL's `ON CONFLICT` clause for all inserts.
- **Pattern**: `INSERT INTO matches (...) VALUES (...) ON CONFLICT (game_id) DO UPDATE SET ...`
- **Benefit**: If a job restarts or overlaps, it updates the existing record instead of creating duplicates.

---

## Phase 0.5 Enhancement: Centralized Config & Data Audit

### Centralized Configuration (`config.py`)
We moved all hardcoded strings and environment variables into a single `backend/src/config.py` file.
```python
# config.py
CURRENT_SEASON = "2025-26"
REQUEST_DELAY = 1.0  # Respectful rate limiting
DATABASE_URL = os.getenv("DATABASE_URL")
```
**Decision**: Centralization makes the pipeline environment-agnostic (local vs. docker vs. cloud).

### Automated Data Audit (`audit_data`)
Every ingestion run ends with an automated "sanity check."
1. **Team Stats Check**: Validates that every completed match has exactly 2 `team_game_stats` records.
2. **Player Stats Check**: Ensures no completed matches have zero player box scores.
3. **Score Check**: Flags any completed matches missing either home or away scores.

---

## Phase 0.5 Resilience & Auditing (Current)

We've added a robust resilience and observability layer to ensure production-grade reliability.

### 1. Jittered Rate Limiting
Instead of a fixed delay, we've added random jitter ($\pm 0.2s$) to our requests.
- **Why**: "Robotic" fixed-interval scraping is easily detected by modern API firewalls. Jitter mimics human-like variance.

### 2. Dual-Handler Logging
The system now logs to both `STDOUT` (console) and `logs/pipeline.log`.
- **Why**: Console logs are great for dev, but file logs are critical for post-mortem debugging of failed midnight syncs.

### 3. Pre-flight Health Checks
Before any data movement starts, the pipeline verifies:
- **DB Connection**: Simple `SELECT 1` heartbeat.
- **API Heartbeat**: Fetches a tiny resource from `nba_api` to ensure no IP blocks are in place.

### 4. Structured Auditing Layer
We now record every pipeline event in the `pipeline_audit` table.
- **Observability**: The `/api/v1/system/status` endpoint reads from this table to show the frontend the "Pulse" of the system.

## Interview Angle: The "Flight Recorder" Pattern
> **"How do you handle pipeline observability?"**
> 
> "I implemented what I call the 'Flight Recorder' pattern. Every ingestion and feature engineering run records its start time, status, record counts, and any stack traces into an audit table. This allowed me to build a real-time health dashboard, moving us away from 'guessing' if the data is fresh to 'knowing' the system's state at a glance."
