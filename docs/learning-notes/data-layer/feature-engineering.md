# Feature Engineering — Learning Note

## What Is It?

Feature engineering is the process of transforming raw data into meaningful inputs that help ML models make better predictions. Think of it like a chef preparing ingredients — raw chicken and spices are data; marinated, seasoned, perfectly-cut pieces are features.

## Why Does It Matter?

> "Applied ML is basically feature engineering" — Andrew Ng

Models can only learn from the patterns in their input features. If you give a model raw game scores (110, 105), it can't understand "team momentum" or "fatigue." But if you compute **rolling 5-game win%** and **days since last game** — those features ENCODE the real-world patterns.

**This is where 80% of model performance improvement comes from** — not from choosing XGBoost over Random Forest.

## How Does It Work? (Intuition)

### Types of Features We Built

| Feature | Raw Data | Engineered Feature | Why It Helps |
|---------|----------|-------------------|-------------|
| **Rolling Win %** | W, L, W, W, L | 0.60 (3/5) | Captures **momentum** — is the team on a roll? |
| **Point Differential** | +5, -3, +12, +7, -1 | +4.0 avg | More nuanced than win/loss — a team winning by 20 is different from winning by 1 |
| **Rest Days** | Last game 2 days ago | 2 | Models **fatigue** — back-to-backs are brutal |
| **H2H Win %** | 3 wins in 4 games vs LAL | 0.75 | Some teams consistently dominate specific matchups |
| **Home/Away** | Home game | 1 (boolean) | Home-court advantage is real (~60% win rate in NBA) |

### The Critical Concept: Data Leakage

**Data leakage** is when you accidentally include future information in your features when predicting the current game.

❌ **Wrong**: "Lakers' 5-game rolling win% INCLUDING today's game is 0.8" → but today's game hasn't happened yet!

✅ **Right**: "Lakers' 5-game rolling win% from the PREVIOUS 5 games is 0.6"

In our SQL: `ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING` (excludes current row)

This is the **#1 mistake juniors make** in time-series ML.

### Window Functions (The SQL Superpower)

We used PostgreSQL window functions to compute features directly in the database:

```sql
-- Rolling 5-game win percentage
AVG(won) OVER (
    PARTITION BY team_id    -- Separate calc per team
    ORDER BY game_date      -- Chronological order
    ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING  -- Last 5 games, exclude current
)
```

**Why in SQL, not Python?**
- No data movement (stays in DB)
- Scales to millions of rows
- Leverages PostgreSQL query optimizer
- Shows interviewers you know production patterns

## When to Use vs. Alternatives

| Approach | When to Use | When NOT To |
|----------|-------------|-------------|
| **Manual (our approach)** | Domain-specific features, you know the sport | Too many columns to handle manually |
| **Auto-feature (featuretools)** | Wide tables, want to explore all combos | When you need interpretable features |
| **Deep Learning features** | Unstructured data (images, text) | Tabular data <100K rows |

## Common Interview Questions

1. **"How do you handle feature engineering for time-series data?"**
   → Rolling windows with careful lag to avoid data leakage

2. **"What's data leakage and how do you prevent it?"**
   → Including future info in training features. Prevent with strict temporal ordering.

3. **"How do you decide which features to create?"**
   → Domain knowledge first, then statistical analysis (correlation, mutual information)

4. **"Feature engineering vs. feature selection — what's the difference?"**
   → Engineering = creating new features. Selection = choosing which to keep.

## The Senior Manager Perspective

A lead architect would think about:
- **Computation cost**: Can this feature be computed in real-time for live predictions? Our window functions run in ~100ms.
- **Staleness**: How quickly does this feature become outdated? Rolling 5-game is more responsive than rolling 20-game.
- **Interpretability**: Can a business user understand why this feature matters? "Rolling win%" is intuitive.
- **Maintenance**: Will this feature break if the data schema changes? We designed it to be robust to missing data.

---

## Phase 1A Hardening: H2H and Pregame Streak Reliability

### Gap We Fixed
`compute_h2h_features()` existed but was not called in the main feature pipeline. Also, `current_streak` was a placeholder (`0`) instead of a real pregame signal.

### What Changed
1. Feature pipeline execution now runs:
   - `compute_features()`
   - `compute_h2h_features()`
   - `compute_streak_features()`
2. `current_streak` is now computed as **pregame streak**, not postgame streak.

### Why Pregame Streak Matters
If you compute streak including the current game, you leak outcome information into features. Pregame streak ensures the model only sees what was known before tipoff.

### Intuition
If Lakers are on a 4-game win streak before tonight, feature = `+4`.
If they lost 3 straight before tonight, feature = `-3`.
For first game with no history, feature = `0`.

### Interview Angle
**Junior answer:** "I added streak as a feature."

**Senior answer:** "I explicitly implemented pregame streak segmentation and lag logic so the feature is leakage-safe and production-realistic."
