# Incremental Sync & Database Precisions — Learning Note

## What Is It?

When building data pipelines, **Incremental Sync** (often called Delta Load or Change Data Capture) is the technique of only fetching and processing data that has been created or modified since the last successful pipeline run. 

In our NBA pipeline:
- We use a "watermark" approach: we query the database for the maximum `game_date` we currently have (`SELECT MAX(game_date) FROM matches`).
- We then filter the API response to only process and insert games that occurred *on or after* this date.

**Database Precisions** refer to the specific scalar limits enforced by the database engine on numeric fields (e.g., `DECIMAL(5,2)` restricts a number to 5 total digits, with 2 decimal places, meaning a maximum value of `999.99`).

## Why Does It Matter?

1. **Incremental Sync = Performance & Safety**:
   - Re-inserting all 1,200 games from a season every day using `UPSERT (ON CONFLICT DO UPDATE)` works, but it causes huge unnecessary database disk I/O, burns CPU, and wastes API rate limits.
   - By only upserting the 5–10 games played *yesterday*, a pipeline that took 5 minutes drops down to 10 seconds.

2. **Database Precisions = Data Integrity**:
   - When we store per-game statistics, a player might play 35.5 minutes (`DECIMAL(5,2)` easily fits this).
   - But when we store **season aggregates**, their total minutes might be 1,500.5. If the database schema uses `DECIMAL(5,2)`, the pipeline crashes with a `NumericValueOutOfRange` exception. 
   - A pipeline failure on day 60 of the season because a player crossed the 1,000-point threshold is a classic, difficult-to-trace production bug.

## How Does It Work? (Intuition)

### 1. The Watermark Pattern (Incremental Sync)
Think of reading a book. If you're reading a book and put a bookmark on page 100, the next time you pick it up, you don't start from page 1. You start from page 100.
- **The Book**: The NBA API's season game logs.
- **The Bookmark (Watermark)**: `SELECT MAX(game_date)` from our database.
- **Resuming**: Filtering the API dataframe `df[df['GAME_DATE_DT'] >= max_date_in_db]`.

### 2. Numeric Field Overflow Prevention
When designing the schema, you must anticipate the **maximum possible value** of a metric across its supported timeframe.
- Per-game points: max ~100. `DECIMAL(5,2)` (max 999.99) is safe.
- Season points: max ~3,000+. `DECIMAL(5,2)` will overflow! We need at least `DECIMAL(6,2)` (max 9999.99). Over-provisioning to `DECIMAL(8,2)` is safest.

## When to Use vs Alternatives

### Incremental Sync Approaches
| Approach | How it Works | When to Use |
|----------|-------------|-------------|
| **Full Refresh (Truncate & Load)** | Deletes all old data, inserts everything anew. | Small datasets, dimension tables (like teams). |
| **Watermarking (What we did)** | Query Max(Date) or Max(ID), fetch everything after. | Append-only logs, immutable time-series data (like completed games). |
| **Change Data Capture (CDC)** | Listen to transaction logs (like Postgres WAL) for changes. | High-frequency syncing between databases, real-time analytics. |

### Data Types Approaches
- **Use `INTEGER`** if there will never be a fraction (e.g., total Points, total Rebounds). 
- **Use `DECIMAL(p, s)` (or `NUMERIC`)** when exact precision is needed (e.g., win percentage `DECIMAL(5,3)` for exactly 3 digits).
- **Use `FLOAT` (or `REAL`/`DOUBLE PRECISION`)** when speed matters more than absolute precision, and you have highly variable scales.

> **Senior Answer**: "When deciding between full refresh and incremental sync, I look at the data volume and the mutability of past data. Matches don't change once decided, so watermarking is incredibly efficient. However, if 'past' match data could randomly change retroactively (e.g., stats corrections 3 weeks later), watermarking by action date would miss those updates. In that case, we'd need to watermark by an `updated_at` timestamp from the source API."

## Common Interview Questions

1. **"Your daily batch job was running in 5 minutes, but 6 months later it takes 2 hours. What's wrong and how do you fix it?"**
   → The job is likely doing a full table scan and full refresh of growing data. I'd implement incremental syncing via a high-water mark (timestamp or auto-incrementing ID) to only process the delta.

2. **"What's the difference between optimistic and pessimistic data ingestion?"**
   → Optimistic assumes all data since the last watermark is good and appends it. Pessimistic will check for conflicts and updates (our UPSERT approach). We pair the watermark with UPSERT to get the speed of optimistic loading with the safety of pessimistic loading.

3. **"We got a `numeric field overflow` error in production. How would you handle this without data loss?"**
   → I would immediately run an `ALTER TABLE <table_name> ALTER COLUMN <column_name> TYPE DECIMAL(x,y)` to increase precision. PostgreSQL can often do this in-place without locking the entire table for a full rewrite if the underlying binary representation fits or the change is purely constraint-widening.

## The Senior Manager Perspective

A lead architect cares about:
- **Resiliency of boundaries**: Did we build in protections against edge cases? (e.g., a player scoring >999 points in a season).
- **Run Duration Constraints (SLAs)**: If an ingestion job runs every hour, it *must* finish in < 60 minutes. Incremental sync guarantees the runtime stays flat O(1) relative to new data, rather than growing O(N) over the season.
- **Resource Costs**: Fewer Database reads/writes = lower hosting costs. Less API calls = we don't get banned. 
