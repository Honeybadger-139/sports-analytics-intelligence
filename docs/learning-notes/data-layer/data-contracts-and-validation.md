# Data Contracts and Validation

## What Is A Data Contract?

A data contract is a written agreement between two pipeline stages about what the producer guarantees and what the consumer expects.

In this project:

- ingestion guarantees that raw match data has the required columns and enough recent rows
- feature engineering guarantees that the feature table has the required feature columns with acceptable null rates

This makes the pipeline more predictable and easier to debug than ad hoc checks scattered through the code.

## Why Contracts Matter Between Ingestion And Features

Without a contract, feature engineering can silently consume bad raw data and produce broken model inputs.

Examples:

- a stale ingestion run means the latest games never reach the model
- a null spike in `game_date` or `points` can skew downstream joins and rolling windows
- missing feature columns can break prediction serving later, far away from the original failure

A contract turns those problems into an explicit, early failure.

## Validation Gate Pattern

A validation gate sits between stages and checks:

- row counts
- null rates
- freshness
- required columns

If the checks fail, the pipeline stops before bad data can propagate.

That is usually better than letting the pipeline continue and discovering the problem later from model drift or a broken prediction response.

## Dead-Letter Pattern

A dead-letter pattern captures failed work in a separate place instead of dropping it.

For this repo, the idea is:

- successful feature runs continue downstream
- failed validation writes an audit record
- a failure event is published so monitoring can alert independently

That keeps operational visibility high without hiding the original failure.

## Testing Prefect Tasks Locally

You do not need a live Prefect deployment to test the logic inside a task.

The usual approach is:

- move the real validation logic into pure helpers or contract methods
- mock the SQLAlchemy engine or DB connection
- assert on returned summaries and raised exceptions
- keep task wrappers thin so they are easy to patch and reason about

This is the fastest way to verify orchestration logic before wiring it into a Prefect flow.

## Interview Questions

1. What is a data contract and why does it help in ML pipelines?
2. How is a validation gate different from a unit test?
3. Why would you fail fast on stale raw data instead of imputing it later?
4. What is a dead-letter queue or dead-letter pattern?
5. How do you test orchestration code without a live database?
6. Why is it useful to separate validation logic from the Prefect task wrapper?

## Short Interview Answer

"I use data contracts to define what each stage of the pipeline guarantees and expects. That lets me validate raw ingestion before feature computation, stop on stale or malformed data, and send failures to a dead-letter path so monitoring can react instead of silently continuing with bad inputs."
