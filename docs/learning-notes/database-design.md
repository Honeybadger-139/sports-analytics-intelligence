# Database Design for ML Systems — Learning Note

## What Is It?

Database design is the art of structuring your data so it's **fast to query**, **hard to corrupt**, and **easy to evolve**. For ML systems, the database isn't just a storage layer — it's where feature computation happens, where predictions are logged, and where model performance is tracked.

Think of it like building a kitchen: a well-organized kitchen (good schema) makes cooking (feature engineering) fast and reliable. A messy kitchen (denormalized dump) means you spend 80% of your time looking for ingredients.

## Why Does It Matter?

In ML projects, most people jump straight to model training. But your model's ceiling is defined by:
1. **Data quality** — which depends on schema constraints (NOT NULLs, foreign keys, unique constraints)
2. **Feature computation speed** — which depends on indexes and table structure
3. **Reproducibility** — which depends on proper data versioning and immutable records

> "I've seen more ML projects fail because of bad data infrastructure than bad algorithms." — every ML Engineering Lead

## How Does It Work? (Intuition)

### Our Schema: 7 Tables

```
┌───────────┐     ┌──────────────┐     ┌─────────────────┐
│   teams   │◄────│   matches    │────▶│ team_game_stats  │
│ (dim)     │     │ (fact)       │     │ (fact)           │
└───────────┘     └──────────────┘     └─────────────────┘
      ▲                  │                      │
      │                  ▼                      ▼
┌───────────┐     ┌──────────────┐     ┌─────────────────┐
│  players  │     │ match_features│    │  predictions     │
│ (dim)     │     │ (derived)    │     │ (output)         │
└───────────┘     └──────────────┘     └─────────────────┘
                                       ┌─────────────────┐
                                       │     bets         │
                                       │ (tracking)       │
                                       └─────────────────┘
                                       ┌─────────────────┐
                                       │   bankroll       │
                                       │ (tracking)       │
                                       └─────────────────┘
```

### Table Categories

| Category | Tables | Purpose |
|----------|--------|---------|
| **Dimension** | `teams`, `players` | Reference data — "who" |
| **Fact** | `matches`, `team_game_stats` | Events — "what happened" |
| **Derived** | `match_features` | Computed from facts — "ML inputs" |
| **Output** | `predictions`, `bets`, `bankroll` | Model outputs and tracking |

### Key Design Decisions Explained

#### 1. Foreign Keys Everywhere

```sql
home_team_id INTEGER REFERENCES teams(team_id)
```

**What it does**: PostgreSQL refuses to insert a match with a team_id that doesn't exist in `teams`.

**Why it matters**: Without this, a typo in team_id (e.g., 99999) creates orphan records that silently corrupt your feature calculations. You'd only discover this weeks later when model accuracy drops.

**Trade-off**: Slightly slower inserts (FK check on every insert). Worth it for data integrity.

#### 2. Composite Unique Constraints

```sql
UNIQUE (game_id, team_id)   -- in team_game_stats
UNIQUE (game_id, model_name) -- in predictions
```

**What it does**: Ensures one stats row per team per game, one prediction per model per game.

**Why it matters**: This is the **database-level guarantee** that your feature calculations use exactly one set of stats per team per game. Without it, a re-run of ingestion could create duplicate stat rows, causing your rolling averages to be computed over wrong data.

#### 3. Indexes on Query-Heavy Columns

```sql
CREATE INDEX idx_matches_date ON matches(game_date);
CREATE INDEX idx_matches_season ON matches(season);
```

**What it does**: Creates a B-tree index for fast lookups/range scans.

**When**: Our feature queries filter by `season` and order by `game_date` — indexes make these operations O(log n) instead of O(n).

**Why we didn't index everything**: Indexes speed up reads but slow down writes. Every INSERT/UPDATE must update the index too. We only indexed columns used in WHERE/ORDER BY clauses.

#### 4. Separating `match_features` from `team_game_stats`

**Why not compute features in `team_game_stats`?**  
Because `team_game_stats` stores **raw observations** and `match_features` stores **derived computations**. If we change our feature engineering logic (e.g., switch from 5-game to 7-game rolling window), we only need to recompute `match_features` — the raw stats are untouched.

This follows the **immutable raw data** principle from data engineering.

### PostgreSQL-Specific Features We Leverage

| Feature | Where We Use It | Why |
|---------|----------------|-----|
| **Window functions** | `feature_store.py` — rolling averages | Compute ML features directly in the database |
| **UPSERT** (`ON CONFLICT`) | `ingestion.py` — idempotent writes | Re-run safely without duplicates |
| **DECIMAL types** | Probabilities, percentages | Exact arithmetic (no floating-point errors) |
| **SERIAL PRIMARY KEY** | All tables | Auto-incrementing IDs |
| **REFERENCES** (FK) | All fact tables → dimension tables | Referential integrity |

### Normalization Level

Our schema is in **3rd Normal Form (3NF)**:
- 1NF: All columns are atomic (no arrays, no comma-separated lists)
- 2NF: No partial dependencies (every non-key column depends on the FULL primary key)
- 3NF: No transitive dependencies (non-key columns don't depend on other non-key columns)

**When to denormalize**: If analytical queries (big JOINs) become too slow, you'd create materialized views or summary tables. Our data volume (~2400 rows/season) doesn't warrant this yet.

## When to Use vs. Alternatives

| Approach | When to Use | When NOT To |
|----------|-------------|-------------|
| **Relational (PostgreSQL)** | Structured data, complex queries, ACID needed | Unstructured data, massive horizontal scale |
| **Document (MongoDB)** | Schema-less, rapid prototyping | Complex JOINs, transactional consistency |
| **Columnar (DuckDB, BigQuery)** | Heavy analytics on wide tables | OLTP with lots of small writes |
| **Key-Value (Redis)** | Caching, session storage | Complex queries |

## Common Interview Questions

1. **"How did you design your database schema?"**
   → Identified entities (teams, matches, stats), defined relationships (one team has many matches), normalized to 3NF, added indexes for query-heavy columns.

2. **"Why PostgreSQL over MongoDB for this project?"**
   → Structured relational data, needed window functions for feature engineering, ACID transactions for data integrity, and concurrent access from API + ingestion pipeline.

3. **"How do you handle schema evolution?"**
   → Alembic (SQLAlchemy migrations) for ALTER TABLE operations. Always additive (add columns, not remove). Backward-compatible changes that don't break existing queries.

4. **"What's the difference between a B-tree and a hash index?"**
   → B-tree supports range queries (`<`, `>`, `BETWEEN`), hash only supports equality (`=`). PostgreSQL default is B-tree because range queries are far more common.

5. **"When would you denormalize?"**
   → When JOIN performance bottlenecks appear in production. Denormalize with materialized views, not by modifying source tables.

## The Senior Manager Perspective

A lead architect would think about:
- **Cost of bad data**: A wrong FK means feature computation silently produces nonsense. One bad feature → wrong prediction → real money lost. Schema constraints are your first line of defense.
- **Write vs. Read optimization**: We optimized for write speed (batch inserts) during ingestion and read speed (indexes) during prediction. If these conflict, consider separate OLTP/OLAP stores.
- **Schema evolution strategy**: As the project grows (e.g., adding football data), we need migrations that don't break the existing NBA pipeline. Alembic + feature flags.
- **Monitoring**: Track table row counts, index usage stats (`pg_stat_user_indexes`), query latencies. A sudden spike in query time = missing index or data growth.
