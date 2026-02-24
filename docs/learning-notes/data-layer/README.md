# 🏀 The Complete Data Layer — Explained

The Data Layer is the **foundation** of the entire Sports Analytics Intelligence Platform. Think of it like a restaurant kitchen — you can have the best chef (ML model), but if the ingredients (data) are bad, the dish (predictions) will be terrible.

The Data Layer has **3 modules** that work together:

```
NBA Stats API  →  ingestion.py  →  PostgreSQL  →  feature_store.py  →  match_features table  →  ML Engine
```

---

## Architecture Position

```
┌─────────────────────────────────────────────────────┐
│                    DATA LAYER  ◄── You are here      │
│  ┌───────────┐   ┌──────────┐   ┌────────────────┐ │
│  │  nba_api  │──▶│ingestion │──▶│  PostgreSQL     │ │
│  │  (Source)  │   │   .py    │   │  (7 tables)     │ │
│  └───────────┘   └──────────┘   └───────┬────────┘ │
│                                         │          │
│                                  ┌──────▼────────┐ │
│                                  │feature_store  │ │
│                                  │    .py        │ │
│                                  └───────────────┘ │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
               ML Engine (consumes features)
```

---

## Files in This Folder

| File | Topic | Key Concepts |
|------|-------|-------------|
| [data-ingestion.md](data-ingestion.md) | **ETL Pipeline** — How data moves from NBA API to PostgreSQL | Idempotency, rate limiting, exponential backoff, ETL vs ELT, dimension vs fact tables |
| [database-design.md](database-design.md) | **Schema Design** — Why PostgreSQL, how tables are structured | Normalization, foreign keys, indexes, connection pooling, window functions |
| [feature-engineering.md](feature-engineering.md) | **Feature Engineering** — Transforming raw data into ML features | Rolling windows, data leakage prevention, window functions, H2H features |
| [query-tools.md](query-tools.md) | **Query Tools** — pgAdmin setup for SQL exploration and data validation | pgAdmin, Docker integration, useful queries, CLI alternatives |
| [api-header-engineering.md](api-header-engineering.md) | **API Header Engineering** — Bypassing bot detection via metadata | User-Agent, Referer, Client Hints, STATS_HEADERS, security context |

---

## Module 1: `db.py` — The Database Connection

**What it is**: The plumbing that connects your Python code to PostgreSQL.

**What it does**:
- Creates a **SQLAlchemy engine** with **connection pooling** (5 persistent + 10 overflow connections)
- Provides a `get_db()` dependency for FastAPI — each API request gets its own session, auto-closed after use

**Why connection pooling matters**:
> Imagine 100 users hit your API simultaneously. Without pooling, you'd open 100 PostgreSQL connections → expensive → crash. With pooling, 5 connections are reused — like a shared cab vs. everyone taking a separate one.

```python
engine = create_engine(
    DATABASE_URL,
    pool_size=5,        # Max 5 persistent connections
    max_overflow=10,    # Up to 10 more on demand
    pool_timeout=30,    # Wait 30s before error
    pool_recycle=1800,  # Recycle every 30 min (avoids stale connections)
)
```

> **🎯 Interview angle**: *"I used SQLAlchemy with connection pooling because FastAPI handles concurrent requests — without pooling, each prediction request would open a new database connection, which doesn't scale."*

---

## Module 2: `ingestion.py` — Getting Data From the NBA API

**What it is**: The ETL (Extract → Transform → Load) pipeline that pulls NBA data.

**The analogy**: Think of it like a delivery truck system:
- **Where to pick up** = NBA Stats API
- **How to transport safely** = rate limiting + retry logic
- **Where to drop off** = PostgreSQL tables

### The Pipeline Runs in 3 Steps (Order Matters!)

```
Step 1: ingest_teams()           →  30 NBA teams      (dimension table — load FIRST)
Step 2: ingest_season_games()    →  ~1200 games/season (fact table — needs teams loaded)
Step 3: ingest_players()         →  ~450 players       (dimension table — needs teams loaded)
```

**Why this order?** Foreign key constraints. `matches.home_team_id` references `teams.team_id`. If you load matches before teams → FK violation → crash. This is a classic ETL pattern: **load dimension tables before fact tables**.

### Key Pattern 1: Idempotent Writes (ON CONFLICT)

This is the **most important production pattern** in the entire Data Layer:

```sql
INSERT INTO teams (team_id, abbreviation, full_name, city)
VALUES (:team_id, :abbrev, :full_name, :city)
ON CONFLICT (team_id) DO UPDATE SET
    abbreviation = EXCLUDED.abbreviation,
    full_name = EXCLUDED.full_name
```

**What "idempotent" means**: Running the pipeline 1 time or 100 times produces the **exact same result**. No duplicates, no corruption.

**Why it matters**: In production:
- Cron jobs can fire twice
- Workers crash and retry
- You'll manually re-run during debugging

If your pipeline isn't idempotent, every retry **corrupts** your data. This is what separates real engineering from Kaggle notebooks.

### Key Pattern 2: Rate Limiting + Exponential Backoff

```python
REQUEST_DELAY = 2.0   # 2 seconds between API calls
MAX_RETRIES = 3       # Retry up to 3 times
BASE_BACKOFF = 10     # Wait 10s → 20s → 40s
```

The retry logic:
```
Attempt 1 fails → wait 10s
Attempt 2 fails → wait 20s (10 × 2¹)
Attempt 3 fails → wait 40s (10 × 2²) → give up
```

**Why exponential backoff?** If NBA.com is temporarily down, hammering it with retries every second makes things worse. Exponential backoff gives the server time to recover. This is the **standard pattern** for all flaky API integrations (AWS, Google, any external service).

### Key Pattern 3: Error Isolation

```python
for team in all_teams:
    try:
        # Pull data for this team
    except Exception as e:
        logger.error(f"Error pulling {team}: {e}")
        continue  # Move to next team, don't crash!
```

If pulling data for the Lakers fails (API timeout, bad response, whatever), we **skip the Lakers and continue with the Celtics**. One team's failure doesn't kill the entire pipeline. In a non-isolated design, a single error would crash the entire 30-team run.

### Key Pattern 4: Game Deduplication

Each NBA game appears in **two different teams' game logs** (home team + away team). So when we loop through 30 teams, we'd get every game twice. We track `games_seen = set()` and only insert a match once:

```python
if game_id not in games_seen:
    # Insert into matches table
    games_seen.add(game_id)
```

But we insert **team_game_stats** for both teams (each team gets their own stats row for the game).

---

## Module 3: `feature_store.py` — The ML Feature Engineering

**What it is**: The module that transforms raw game data into **ML-ready features**. This is where your Analytics Engineering SQL skills become a superpower.

**The analogy**: Raw data says "Lakers scored 110 points." Features say "Lakers have won 4 of their last 5, average +6.2 point differential, are coming off a back-to-back, and are 3-1 against this opponent."

### The 10 Features We Compute

| # | Feature | What It Captures | Why ML Needs It |
|---|---------|-----------------|-----------------|
| 1 | **Rolling 5-game Win %** | Short-term momentum | Is the team hot right now? |
| 2 | **Rolling 10-game Win %** | Medium-term form | More stable than 5-game |
| 3 | **Point Diff (5-game)** | Margin of wins/losses | Winning by 20 ≠ winning by 1 |
| 4 | **Point Diff (10-game)** | Medium-term margin trend | |
| 5 | **H2H Win %** | Matchup-specific edge | Some teams consistently dominate others |
| 6 | **H2H Average Margin** | How dominant the matchup is | |
| 7 | **Rest Days** | Fatigue factor | Back-to-backs are brutal in the NBA |
| 8 | **Back-to-Back Flag** | Extreme fatigue | Boolean: played yesterday? |
| 9 | **Off/Def Ratings (5-game)** | Efficiency per 100 possessions | Better than raw points |
| 10 | **Current Streak** | Hot/cold streaks | Psychological momentum |

### The Critical Concept: Data Leakage Prevention

This is the **#1 mistake** juniors make with time-series ML. Here's the problem:

❌ **WRONG**: "What's the Lakers' win% over their last 5 games **including today's game**?"
→ But today's game **hasn't happened yet!** You're using the future to predict the present.

✅ **RIGHT**: "What's the Lakers' win% over their last 5 games **before today**?"

In SQL, this one word makes all the difference:

```sql
-- ❌ LEAKING: includes current row
ROWS BETWEEN 5 PRECEDING AND CURRENT ROW

-- ✅ SAFE: excludes current row
ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
```

That `1 PRECEDING` instead of `CURRENT ROW` is the difference between a model that looks great in testing but fails in production, and one that actually works.

> **🎯 Interview awe moment**: *"I was very careful to use `ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING` to prevent data leakage. This is the #1 mistake in time-series feature engineering — your model looks amazing in backtesting because it's cheating by seeing the answer."*

### Why Features Are Computed in PostgreSQL (Not Python)

We could have done `df.rolling(5).mean()` in pandas. Here's why we didn't:

| | Python (pandas) | PostgreSQL (window functions) |
|--|----------------|------------------------------|
| **Data movement** | Pull all data to Python memory | Stays in database |
| **Scale** | Breaks at millions of rows | Handles it natively |
| **Speed** | O(n) per feature in Python | DB query optimizer |
| **Reusability** | Script-dependent | Any SQL client can query |
| **Resume signal** | "I used pandas" | "I pushed computation to the DB layer" ← production pattern |

```sql
AVG(won) OVER (
    PARTITION BY team_id          -- Separate calculation per team
    ORDER BY game_date            -- Chronological order
    ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING  -- Last 5 games, EXCLUDING current
) as win_pct_last_5
```

### How H2H Features Work

The `compute_h2h_features()` function is a separate step because it requires a **self-join**:

1. For each game, identify the opponent
2. Look at all **previous** games between these two teams
3. Compute the win% and average margin from those past matchups
4. `UPDATE` the `match_features` table with H2H columns

This captures patterns like "the Warriors always struggle against the Nuggets" that overall team stats would miss.

### The Filter: `WHERE game_num > 5`

We only create features for games where the team has played **at least 5 prior games** (otherwise rolling 5-game stats would be based on insufficient data / NULLs). First few games of the season get skipped — this is a deliberate quality filter.

---

## Data Flow (End to End Summary)

```
NBA Stats API
    │
    ▼
ingestion.py (Extract → Transform → Load)
    ├── ingest_teams()         →  teams table          (30 rows, dimension)
    ├── ingest_season_games()  →  matches table        (~1200 rows/season, fact)
    │                          →  team_game_stats      (~2400 rows/season, fact)
    └── ingest_players()       →  players table        (~450 rows, dimension)
    │
    ▼
feature_store.py (Feature Engineering)
    ├── compute_features()     →  match_features       (rolling stats via window functions)
    └── compute_h2h_features() →  match_features       (head-to-head win%, margin)
    │
    ▼
ML Engine (trainer.py consumes match_features for model training)
```

**Total data volume**: < 1 MB per season. PostgreSQL handles this trivially.

---

## Key Decisions Made

| # | Decision | Why | Interview Angle |
|---|----------|-----|-----------------|
| 1 | **PostgreSQL** over SQLite | Window functions, concurrent access, production-grade | "I needed window functions for rolling feature computation" |
| 2 | **nba_api** over web scraping | Structured JSON, reliable, no HTML fragility | "API > scraping for maintainability" |
| 3 | **SQL-based features** over pandas | No data movement, scales to millions of rows | "I pushed computation to the database layer" |
| 4 | **Separated raw vs. features** | Immutable raw data, re-engineer without re-ingesting | "Following the immutable raw data principle" |
| 5 | **SQLAlchemy** over raw psycopg2 | Connection pooling, database-agnostic, Alembic integration | "Connection pooling is critical for concurrent FastAPI requests" |

---

## Key Production Patterns Summary

1. **Idempotent Writes** — `ON CONFLICT DO UPDATE` ensures re-running the pipeline doesn't create duplicates
2. **Rate Limiting** — 2-second delay between API calls to avoid throttling/bans
3. **Exponential Backoff** — Failed calls retry at 10s → 20s → 40s intervals
4. **Error Isolation** — One team's failure doesn't crash the entire pipeline
5. **Data Leakage Prevention** — `ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING` excludes current game
6. **FK-Ordered Loading** — Dimension tables (teams) loaded before fact tables (matches)
7. **Connection Pooling** — 5 persistent + 10 overflow connections for concurrent API requests
8. **Game Deduplication** — Track `games_seen` set to avoid inserting the same match twice

---

## Interview Quick Reference

> **"Walk me through your data pipeline"**
>
> "I built a daily batch ETL pipeline. The ingestion layer pulls NBA data via the official API with exponential backoff for resilience, deduplicates games since each appears for both teams, and upserts into PostgreSQL using `ON CONFLICT` to ensure idempotency. The feature layer then computes rolling statistics — win percentages, point differentials, offensive/defensive ratings — using PostgreSQL window functions directly in the database, avoiding expensive data movement into Python. I was careful to use `ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING` to prevent data leakage, and I separated raw data from computed features following the immutable raw data principle — so I can re-engineer features without re-ingesting."

That answer hits: **ETL design, resilience patterns, idempotency, SQL expertise, data leakage prevention, separation of concerns**. That's a senior engineer's answer.
