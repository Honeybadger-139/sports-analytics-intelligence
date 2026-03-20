# Domain-Aware Imputation and Validation Gates

## Domain-Aware Imputation

Domain-aware imputation means we replace missing values using a value that matches the meaning of the feature, not just a generic statistical default.

For this project:

- `h2h_win_pct` gets `0.5`
- `h2h_avg_margin` gets `-0.5`
- rolling offensive/defensive rating features get the season median
- everything else falls back to `0`

Why this matters:

- `0` is not neutral for every feature.
- A missing head-to-head win rate does not mean the team is equally bad in that matchup.
- A missing offensive rating is better approximated by the season's central tendency than by a fake zero.

## Why `fillna(0)` Can Hurt Tree Models

Tree models split on thresholds. If we blindly use `0` everywhere:

- missing H2H features can create fake "super weak" signals
- the model may learn splits around the missing value pattern instead of the real basketball pattern
- default zeros can collapse distinct feature meanings into the same bucket

For example, `h2h_win_pct = 0` means "this team has historically never won this matchup," while a missing value really means "we do not have enough history yet." Those are different signals.

## Validation Gate

A validation gate checks raw data before feature engineering starts.

In this pipeline, the gate verifies:

- there are at least 10 matches
- critical null rates stay under 15%
- the latest game date is no older than 7 days

Why it matters:

- it catches ingestion failures early
- it prevents stale or corrupted data from becoming features
- it creates a clear audit trail instead of silent model drift

Think of it as the ML version of a circuit breaker: if the inputs are unhealthy, stop the pipeline before the problem spreads downstream.

## Interview Questions

1. Why is `fillna(0)` dangerous for sports features?
2. When would you use a season median versus a domain constant?
3. What is the difference between missing data and a real zero?
4. Why should feature engineering have a validation gate before it runs?
5. How does fail-fast validation improve ML reliability?
6. How would you explain a stale-data guard to a product manager?

## Short Interview Answer

"I use domain-aware imputation because missing features and true zero-valued features are not the same thing. For matchup features like head-to-head win rate, I use basketball-aware defaults, and I put a validation gate in front of feature engineering so stale or incomplete raw data fails fast before it can corrupt training."
