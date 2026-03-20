# Vertex AI Experiments

## What Is Experiment Tracking?

Experiment tracking is the practice of recording how a model was trained and
how it performed. Instead of just keeping the final model file, we store the
configuration, metrics, and comparison context for each run.

That makes it possible to answer:

- Which data did we train on?
- Which hyperparameters were used?
- Did calibration improve?
- Which model should become the champion?

## Why It Matters In Production ML

Experiment tracking turns model training into an auditable process. Without it,
teams often know only the final score and lose the history behind it.

In production, tracking helps with:

- reproducibility
- rollback confidence
- comparison across model versions
- debugging regressions

## What To Track

Useful run metadata includes:

- params: season, feature count, CV folds, and key hyperparameters
- metrics: accuracy, AUC, Brier score, log loss, calibration quality
- model family comparisons
- validation window size
- any post-processing steps such as calibration

## Params vs Metrics

- Params describe how the model was trained.
- Metrics describe how the model performed.

Example:

- `n_estimators=200` is a param
- `cv_accuracy=0.634` is a metric

## Champion / Challenger

The champion is the current best model in production. The challenger is the
new model being evaluated.

The goal is to make promotion evidence-based:

- train challenger
- log results
- compare against champion
- promote only if the challenger is better enough to justify risk

## Why Vertex AI Experiments

Vertex AI Experiments gives us a GCP-native place to store these runs. That is
useful because the rest of the stack is already GCP-based, so the training,
registry, and deployment story stays consistent.

## Interview Questions

1. What is experiment tracking and why do teams use it?
2. What is the difference between params and metrics?
3. Why is calibration important for probability models?
4. How does experiment tracking support rollback decisions?
5. What does champion/challenger mean in model governance?
6. Why keep experiment logging best-effort instead of blocking training?
