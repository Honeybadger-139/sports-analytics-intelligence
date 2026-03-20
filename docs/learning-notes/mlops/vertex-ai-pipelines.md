# Vertex AI Pipelines

Vertex AI Pipelines is Google Cloud's managed runtime for Kubeflow Pipelines (KFP). It is useful when a workflow needs step-level visibility, retries, and governed promotion rules.

## What Is a Kubeflow Pipeline Component?

A component is one isolated step in a pipeline. It has:

1. declared inputs and outputs
2. its own container image or package set
3. its own retry and caching behavior

In the retrain pipeline, examples are:

1. `load_and_validate_data`
2. `train_ensemble`
3. `evaluate_vs_champion`
4. `register_model`
5. `promote_to_production`
6. `write_retrain_audit`

This is better than a single script because each step is observable and independently debuggable.

## What Is an ExitHandler?

`ExitHandler` is a KFP pattern that guarantees a cleanup or audit step runs even if an earlier component fails.

That matters for retraining because we do not want a failed training run to disappear without a record. The audit step can still write:

1. the triggering reason
2. the run identifier
3. the model metrics that were available
4. the rollback strategy

## Champion vs Challenger

Champion/challenger testing compares the current production model against a new candidate.

1. Champion = the model currently serving traffic.
2. Challenger = the newly trained model.
3. The challenger is promoted only if it clears the improvement threshold.

This reduces the risk of shipping a model that is technically new but operationally worse.

## Minimum Improvement Threshold

The minimum improvement threshold is the smallest gain required before promotion.

Examples:

1. accuracy must improve by at least `0.01`
2. Brier score must improve by at least `0.01`

The point is to avoid noisy promotions caused by tiny metric fluctuations.

## How Rollback Works on Vertex AI

Rollback should be alias-based, not version-number-based.

1. the current production alias points to a live model version
2. if a new version regresses, reassign the alias to the previous version
3. traffic switches back without changing the application code

That gives you a zero-downtime rollback path.

## Why Use Pipelines Instead of a Single Cron Script?

1. step-level retries are clearer
2. component outputs are explicit
3. audit trails are more complete
4. promotion logic is encoded in the pipeline graph
5. it is easier to add governance later, such as approval gates

## Interview Questions

1. What is the difference between a KFP component and a plain Python function?
2. Why is `ExitHandler` useful in a retraining workflow?
3. What is champion/challenger testing?
4. Why is a minimum improvement threshold better than auto-promoting every retrain?
5. How does alias-based rollback reduce deployment risk?
