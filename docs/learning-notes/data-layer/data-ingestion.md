# Data Ingestion Pipelines — Learning Note

## What Is It?

Data ingestion is the process of extracting data from external sources and loading it into your database. Think of it like a delivery truck: you need to know **where** to pick up the goods (data source), **how** to transport them safely (transformation), and **where** to drop them off (database tables).

In our platform, we pull NBA game data from the official NBA Stats API and load it into PostgreSQL.

## Why Does It Matter?

> "Garbage in, garbage out" — Every Data Scientist, ever

Your ML model is only as good as the data feeding it. If your ingestion pipeline:
- **Drops records** silently → your model trains on incomplete data
- **Creates duplicates** → your model overfits to repeated patterns
- **Doesn't handle failures** → one bad API call crashes the entire pipeline

This is the **plumbing** of ML systems. Nobody talks about it in demos, but it's where production systems succeed or fail.

## How Does It Work? (Intuition)

### Our Pipeline: 3-Stage ETL

```
┌───────────────┐     ┌───────────────┐     ┌────────────────┐
│   EXTRACT     │────▶│   TRANSFORM   │────▶│     LOAD       │
│  nba_api      │     │  Parse, map,  │     │  PostgreSQL    │
│  (30 teams,   │     │  deduplicate  │     │  (upsert)      │
│   ~1200 games)│     │               │     │                │
└───────────────┘     └───────────────┘     └────────────────┘
```

### Key Patterns We Used

| Pattern | What It Does | Why It Matters |
|---------|-------------|----------------|
| **Idempotent Writes** | `ON CONFLICT ... DO UPDATE` | Re-running the pipeline doesn't create duplicates |
| **Rate Limiting** | 1-second delay between API calls | Prevents getting throttled/banned by NBA.com |
| **Dependency Ordering** | Teams → Games → Players | Foreign keys require parent records to exist first |
| **Error Isolation** | Try/except per team, not per pipeline | One team's failure doesn't crash the entire run |
| **Logging** | Structured `asctime | level | message` | Debugging production failures at 3 AM |

### The ETL vs. ELT Debate

| Approach | Pattern | When to Use |
|----------|---------|-------------|
| **ETL** (our approach) | Extract → Transform → Load | When transformations are known upfront, data volume is moderate |
| **ELT** | Extract → Load (raw) → Transform (in-DB) | When raw data needs to be preserved, or transformations evolve over time |
| **Streaming** | Extract in real-time, continuous | When freshness matters (live scores, stock prices) |

> **Senior answer**: "I used ETL because the transformations are well-defined and the data volume (~1200 games/season) doesn't warrant a streaming architecture. For live scores, I'd switch to a CDC (Change Data Capture) or WebSocket-based streaming approach."

### Idempotency: The Most Important Property

**Idempotent** means: running the operation multiple times produces the same result as running it once.

❌ **Non-idempotent**: `INSERT INTO teams VALUES (...)` — Running twice → duplicate rows  
✅ **Idempotent**: `INSERT INTO teams ... ON CONFLICT (team_id) DO UPDATE` — Running twice → same state

This matters because in production:
- Cron jobs can fire twice
- Workers crash and retry
- Manual re-runs during debugging

If your pipeline isn't idempotent, every retry corrupts your data.

### Dimension Tables vs. Fact Tables (Star Schema)

Our ingestion follows the data warehouse pattern:

```
DIMENSION TABLES (load first):        FACT TABLES (load second):
┌────────────┐                        ┌──────────────────┐
│   teams    │◄───────────────────────│     matches      │
│  (30 rows) │                        │  (~1200/season)  │
└────────────┘                        └──────────────────┘
┌────────────┐                        ┌──────────────────┐
│  players   │                        │ team_game_stats  │
│ (~450 rows)│                        │  (~2400/season)  │
└────────────┘                        └──────────────────┘
```

**Why order matters**: `matches.home_team_id` references `teams.team_id` via a foreign key. If you load matches before teams → foreign key violation → crash.

## When to Use vs. Alternatives

| Approach | When to Use | When NOT To |
|----------|-------------|-------------|
| **Batch (our approach)** | Historical data, daily updates | Real-time requirements |
| **Streaming (Kafka, Kinesis)** | Live data, sub-second freshness | Simple batch workloads (over-engineering) |
| **Change Data Capture** | Syncing between databases | Read-only source APIs |
| **API polling** | When source provides REST endpoints | When webhooks are available |

## Common Interview Questions

1. **"How would you design a data ingestion pipeline?"**
   → Define the data source, choose ETL vs. ELT, implement idempotent writes, add error handling and logging, schedule with cron/Airflow.

2. **"How do you handle failures in your pipeline?"**
   → Error isolation per unit of work (per-team, not per-pipeline), idempotent retries, dead-letter queues for persistent failures, alerting on anomalies.

3. **"How do you ensure data quality?"**
   → Schema validation at ingestion, row count monitoring, null-rate checks, deduplication via unique constraints.

4. **"How would you scale this to 10x data volume?"**
   → Parallelize extraction (async/concurrent workers), partition PostgreSQL tables by season, consider Apache Spark or Airflow for orchestration.

5. **"What's the difference between ETL and ELT?"**
   → ETL transforms before loading (saves storage, structured). ELT loads raw first, transforms in the warehouse (flexible, modern — used by dbt/Snowflake/BigQuery patterns).

## The Senior Manager Perspective

A lead architect would think about:
- **Observability**: Can I tell at a glance if yesterday's ingestion ran, how many records it processed, and whether any failures occurred? Our pipeline logs every step.
- **Recoverability**: If it crashes at team 15/30, can I restart without reprocessing teams 1-14? Idempotent writes make this trivial.
- **Monitoring**: Set up alerts for abnormal record counts (e.g., if a season usually has ~1200 games but today's run only found 200 — something's wrong).
- **Cost**: nba_api is free. In enterprise settings, API calls cost money. Batch + caching > polling.
- **Compliance**: In regulated industries, you'd also need audit trails (who ran the pipeline, when, what changed). Our `created_at` timestamps partially serve this purpose.
