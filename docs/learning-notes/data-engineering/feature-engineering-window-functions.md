# Feature Engineering: Window Functions & Rolling Stats

## What is it?
In data engineering, a **Window Function** performs calculations across a set of table rows that are somehow related to the current row. Unlike aggregate functions (`GROUP BY`), which collapse rows into a single summary row, window functions keep the individual rows while adding a new column with the calculated result. 

**Rolling Stats** (like rolling averages or moving sums) are a type of calculation you can do with window functions, computing an aggregate over a "window" of the most recent *N* events leading up to the current event.

## Why does it matter?
In sports analytics, stock market trading, or any temporal dataset, the "past" predicts the "future". You cannot feed a machine learning model raw game scores and expect it to know a team is on a 5-game winning streak. You have to engineered those features explicitly. 

Window functions allow you to construct these temporal features efficiently directly inside the database without loading massive amounts of raw data into memory (like Pandas) and looping through it.

## How does it work (Intuition)?
Imagine you are walking along a timeline game by game. For every game you step on, you look backwards at your last 5 games. You calculate your average points scored and your win percentage over those 5 games. Then, you take one step forward, dropping the oldest game and adding the new one. 

In SQL, this "sliding window" is defined using the `OVER` clause with an `ORDER BY` (to sort chronologically) and a `ROWS BETWEEN` clause (to define the lookback period).

```sql
AVG(points) OVER (
    PARTITION BY team_id 
    ORDER BY game_date 
    ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
) as rolling_5g_avg_points
```
*(Notice the `1 PRECEDING`—we exclude the current game to prevent **data leakage**, ensuring the model only trains on information available *before* the game started!)*

## When to use vs alternatives?
- **Use Database Window Functions:** When your data lives in a SQL database (PostgreSQL, BigQuery, Snowflake). It is highly optimized, leverages database compute, and keeps your orchestration pipeline simple (ELT pattern - Extract, Load, Transform).
- **Alternative 1: Pandas `rolling()`:** Use when your data is already fully loaded in memory for quick prototyping or when SQL functions aren't expressive enough (e.g., complex custom decay functions). *Downside: Doesn't scale well to larger-than-memory datasets.*
- **Alternative 2: Streaming Aggregations (e.g., Flink/Spark Streaming):** Use for real-time applications where features need to be updated within milliseconds of a new event. *Downside: Tremendous infrastructure complexity.*

## The "Senior Manager" Perspective
*"We chose to implement feature engineering natively in PostgreSQL using Window Functions because it pushes the compute to the data layer. It reduces data movement, minimizes our application's memory footprint, and simplifies our stack. It's an ELT approach that scales elegantly until we hit true big-data volumes, at which point we'd migrate these exact same SQL patterns to BigQuery or Snowflake."*

## Common Interview Questions
1. **"What is the difference between `GROUP BY` and an `OVER()` window function?"**
   *Answer:* `GROUP BY` reduces the number of rows by returning one output row per group. An `OVER()` function calculates an aggregate but leaves the original rows intact, appending the result as a new column.

2. **"How do you prevent data leakage when computing rolling statistics for predictive modeling?"**
   *Answer:* You must strictly order your data chronologically and ensure your window explicitly excludes the current row (e.g., using `ROWS BETWEEN N PRECEDING AND 1 PRECEDING` or by dropping/shifting the current row in Pandas). If the target variable leaks into the features, your model will heavily overfit and fail in production.

3. **"If your rolling average script is taking too long to run in Pandas, how would you optimize it?"**
   *Answer:* First, Id push the calculation down to the database using SQL Window functions if the data lives there. If it must be in Python, I'd ensure the dataframe is properly sorted and indexed, use built-in vectorized `.rolling().mean()` functions rather than `apply()`, or leverage libraries like Polars or Dask for parallel execution.
