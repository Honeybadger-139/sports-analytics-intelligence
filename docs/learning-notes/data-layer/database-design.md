# 🗄️ Database Design — Dimension vs. Fact Modeling

Our PostgreSQL schema follows a **Star-like Schema** designed for fast analytical queries and robust foreign key integrity.

## Table Hierarchy

### 1. Dimension Tables (The "Who" and "Where")
These tables contain entities that don't change frequently.
- `teams`: 30 NBA franchises. Primary Key: `team_id`.
- `players`: Active and historical players. Links to `teams`.

### 2. Fact Tables (The "What" and "When")
These tables record events (games) and their metrics.
- `matches`: The core event. Stores `game_id`, `game_date`, `scores`, and `is_completed` flag.
- `team_game_stats`: High-level metrics for one team in one game (Points, Rebounds, Assists).
- `player_game_stats`: Grain-level metrics (every player's performance in every game).

---

## The Plumbing: `db.py` & Connection Pooling

**What it is**: The connection layer that manages how many active links we have to PostgreSQL.

**Why it matters**: 
In production, you don't want to open a new connection for every single query—it's too slow and can crash the database. We use **Connection Pooling** (via SQLAlchemy) to keep a small "stable" of open connections that are reused.

```python
engine = create_engine(
    DATABASE_URL,
    pool_size=5,        # 5 "always-on" connections
    max_overflow=10,    # 10 extra if traffic spikes
    pool_timeout=30,    # Max wait time for a connection
)
```

> **🎯 Interview angle**: *"I used SQLAlchemy with connection pooling because it prevents the database from being overwhelmed during concurrent API requests, ensuring the system remains responsive under load."*

---

## Design Decisions

### 1. Foreign Key Cascading
We utilize `ON DELETE CASCADE` for tables like `predictions` and `match_features`.
- **Reasoning**: If a match is deleted or a season is purged, all downstream analytical artifacts should vanish automatically to maintain referential integrity.

### 2. Indexing for High-Water Mark Ingestion
We indexed `matches(game_date, season)` and `player_game_stats(game_id)`.
- **Benefit**: Incremental syncs need to find the `MAX(game_date)` instantly. Without an index, this becomes a full table scan, slowing down as the season progresses.

### 3. Numeric Precision vs. Scale
We use `DECIMAL(8,2)` for aggregated stats to prevent **Numeric Overflow**.
- **Lesson Learned**: Initial smaller precisions caused crashes when player season-long minute aggregates crossed the 1000.0 threshold.

---

## Logic: Grain of Data
In this system, the base grain is the **Player-Game combination**.
- 1 NBA game → 1 Match record
- 1 NBA game → 2 Team Stats records
- 1 NBA game → ~15-25 Player Stats records

---

## Interview Angle: Normalization
> **"Why use a normalized schema for an ML project instead of one big flat CSV?"**
>
> "Normalization ensures **data consistency**. If a player is traded or a team name changes, we update one row in a dimension table rather than searching through millions of rows in a flat file. This 'single source of truth' prevents the data drift that often plagues long-running ML projects."
