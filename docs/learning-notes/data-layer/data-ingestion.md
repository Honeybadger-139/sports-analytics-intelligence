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

## Interview Angle: Resilience Patterns
> **"How do you handle flaky external APIs?"**
> 
> "I implemented a multi-layered resilience strategy:
> 1. **Exponential Backoff**: If the API fails, we retry at 10s, 20s, and 40s intervals.
> 2. **Rate Limiting**: A strict delay between calls to stay within the service's SLA.
> 3. **Error Isolation**: Each team's loop is wrapped in a `try-except`, so a failure in one team doesn't crash the entire ingestion run."
