# Data Pipeline Architecture

## Overview

This document details the data pipeline that powers GameThread — from raw NBA API calls to ML-ready features stored in PostgreSQL.

## Pipeline Architecture Diagram

```mermaid
flowchart TD
    subgraph "Source Layer"
        API["🏀 NBA Stats API<br/>(nba_api package)"]
    end

    subgraph "Resilient Ingestion Layer [ingestion.py]"
        direction TB
        L["1️⃣ Rate Limiter<br/>(2s Delay)"]
        R["2️⃣ Retry Engine<br/>(Exp. Backoff)"]
        T["3️⃣ Ingest Teams"]
        G["4️⃣ Ingest Games<br/>(Incremental Sync)"]
        P["5️⃣ Ingest Players"]
        L --> R --> T --> G --> P
    end

    subgraph "Storage Layer [PostgreSQL]"
        direction TB
        DT["teams"]
        DM["matches"]
        DS["team_game_stats"]
        DP["players"]
        MF["match_features"]
    end

    subgraph "Feature Engine [feature_store.py]"
        direction TB
        WF["SQL Window Functions<br/>(Rolling Stats)"]
        H2H["Self-Joins<br/>(H2H History)"]
        WF --> H2H
    end

    subgraph "Consumption Layer"
        ML["ML Training"]
        PRED["Live Predictions"]
    end

    API --> L
    T --> DT
    G --> DM & DS
    P --> DP

    DM & DS --> WF
    WF --> MF
    H2H --> MF

    MF --> ML & PRED

    style API fill:#f59e0b,color:#000
    style MF fill:#10b981,color:#000
    style ML fill:#6366f1,color:#fff
    style PRED fill:#6366f1,color:#fff
```

## Pipeline Execution Order

```
┌────────────────────────────────────────────────────────┐
│                    DAILY PIPELINE                       │
│                    Scheduled: 8 AM                      │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Step 1: INGESTION (ingestion.py)                      │
│  ├── 1a. ingest_teams()          →  teams table        │
│  ├── 1b. ingest_season_games()   →  matches +          │
│  │    (Incremental via MAX date)    team_game_stats    │
│  ├── 1c. ingest_players()        →  players table      │
│  ├── 1d. advanced-metric backfill → team_game_stats    │
│  │    (target only missing games)                      │
│  ├── 1e. defensive rating backfill (SQL self-join)     │
│  └── 1f. audit_data()            →  Quality Report     │
│                                                        │
│  Step 2: FEATURE ENGINEERING (feature_store.py)        │
│  ├── 2a. compute_features()      →  match_features     │
│  │    (In-DB Rolling Stats)                            │
│  ├── 2b. compute_h2h_features()  →  match_features     │
│  │    (Matchup-specific edge)                          │
│  └── 2c. compute_streak_features() → match_features    │
│       (Pregame, non-leaky streak state)                │
│                                                        │
│  Step 3: CONSUMPTION                                   │
│  └── 3a. API serves fresh features for tonight's games │
│                                                        │
└────────────────────────────────────────────────────────┘
```

## Resilience Strategy

### 1. Robust API Interactions
The NBA stats API is notoriously flaky and sensitive to scraping. We implement three layers of defense:
- **Centralized Config**: All timeouts and delays are managed in `config.py`.
- **Global Rate Limiting**: Every call is followed by a `REQUEST_DELAY` sleep.
- **Exponential Backoff**: Implementation of a `retry_api_call` decorator that handles transient errors (502, 504, 429) by waiting progressively longer durations before giving up.

### 2. Idempotency (Atomic Upserts)
The pipeline is designed to be **safe to fail**. If the ingestion crashes halfway through, rerunning it will not create duplicate data. We achieve this using PostgreSQL's `INSERT ... ON CONFLICT (id) DO UPDATE` pattern.

### 3. Incremental Watermarking
To minimize the load on the NBA API and our database, we use a **Watermarking Strategy**:
- We query the database for the `MAX(game_date)` of existing records.
- We only request and process games from the API that occurred on or after this date.
- This reduces a full season poll (~1230 games) to a tiny delta (~5-10 games) in daily runs.

### 4. Targeted Historical Backfill
When the schema evolves (for example, adding new advanced metrics), we do not run a full season replay by default. Instead:
- We detect games whose advanced columns are still NULL.
- We include only those game_ids in the next incremental pass.
- We keep the same UPSERT pattern so reruns stay idempotent.

This gives migration-like repair behavior with daily pipeline cost.

## Feature Store Strategy: "Push Compute to Data"

Instead of pulling raw data into Python (Pandas) for feature engineering, we use **PostgreSQL Window Functions**. This follows the "Senior Manager" philosophy of **Pushing Computation to the Data Layer**:

1. **Scalability**: DBs are optimized for relational operations (joins, aggregates).
2. **Efficiency**: Zero data movement overhead.
3. **Consistency**: The same SQL logic produces features for both training and real-time prediction service.

### Anti-Leakage Guardrails
We strictly use `ROWS BETWEEN ... PRECEDING AND 1 PRECEDING` in all window functions. This ensures that a feature record for "Game X" only knows about performance in "Games X-1, X-2...", never "Game X" itself.

## Data Quality & Observability

We implement an `audit_data()` function that runs post-ingestion to check for:
- **Consistency**: Does every completed match have exactly 2 team_game_stats records?
- **Completeness**: Are there any NULL scores in completed games?
- **Health**: Total row count changes compared to historical averages.

### Structured Audit Output

Audit results are now represented as a structured contract and stored in pipeline audit details:

- `team_stats_violations`
- `player_stats_missing_games`
- `null_score_matches`
- `passed`

The API surfaces this data additively via `/api/v1/system/status` at:

- `pipeline.audit_violations`

### Audit Table Bootstrap Guardrail
For legacy Docker volumes, `pipeline_audit` might not exist even though it is present in `init.sql`.
- On missing-table error, ingestion/feature pipeline now creates `pipeline_audit` + indexes (`CREATE TABLE IF NOT EXISTS ...`) and retries the write once.
- `/api/v1/system/status` returns an empty audit history (instead of failing) if the table is missing at read-time.

## Data Lineage

```mermaid
flowchart LR
    subgraph "Raw"
        R1["NBA API JSON"]
    end

    subgraph "Ingested"
        I1["teams"]
        I2["matches"]
        I3["team_game_stats"]
        I4["players"]
    end

    subgraph "Engineered"
        E1["match_features<br/>(rolling + H2H)"]
    end

    subgraph "Modeled"
        M1["predictions"]
        M2["bets"]
        M3["bankroll"]
    end

    R1 --> I1 & I2 & I3 & I4
    I2 & I3 --> E1
    E1 --> M1
    M1 --> M2
    M2 --> M3
```

## Phase 2 Operational Loop

After feature generation, the serving layer now closes the loop:

1. `/api/v1/predictions/today` produces and optionally persists model outputs per game/model.
2. `sync_prediction_outcomes` marks `predictions.was_correct` for completed games.
3. `/api/v1/predictions/performance` aggregates accuracy and Brier score from persisted outcomes.
4. `/api/v1/bets` ledger endpoints track stake decisions and settled PnL for bankroll analytics.

This creates a full audit trail from model inference to financial outcome.

## Interview Angle

> **If asked "Walk me through your data pipeline":**
> 
> "I built a daily batch ETL pipeline. The ingestion layer pulls NBA data via the official API, deduplicates games (each appears for both teams), and upserts into PostgreSQL using ON CONFLICT to ensure idempotency. The feature layer then computes rolling statistics — win percentages, point differentials, offensive/defensive ratings — using PostgreSQL window functions directly in the database, avoiding expensive data movement into Python. I was very careful to use `ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING` to prevent data leakage — this is the number one mistake in time-series ML feature engineering."
