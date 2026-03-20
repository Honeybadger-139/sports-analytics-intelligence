# Vertex AI Experiments Setup

This document captures the console and naming conventions for training-run
tracking in Vertex AI Experiments.

## Experiment Name

- Experiment: `nba-game-predictions`
- Run naming pattern: `run-{timestamp}-{season}`

Examples:

- `run-20260320_101500-2025-26`
- `run-20260320_121045-2024-25`

## What To Log

Track both configuration and outcomes for each run:

- Params: `season`, `validation_season`, `cutoff_date`, `training_games`,
  `validation_games`, `cv_splits`, `feature_count`, `n_estimators`,
  `max_depth`, `learning_rate`
- Metrics: model CV accuracy/AUC, training accuracy/AUC, Brier score,
  log loss, ensemble metrics, validation metrics, and calibration metrics

## How To View Runs In The Console

1. Open the Google Cloud Console.
2. Navigate to Vertex AI.
3. Open the `Experiments` section.
4. Select the `nba-game-predictions` experiment.
5. Compare runs side by side by selecting multiple rows in the runs table.

## What To Compare

- Overall validation accuracy
- Calibration quality, especially Brier score
- Consistency across model families
- Improvement from calibration versus raw predictions
- Whether the ensemble beats the best single model

## Champion / Challenger Workflow

- Champion: the currently deployed or approved model
- Challenger: the newly trained model under evaluation

Typical promotion rule:

- challenger must beat the champion on the primary metric
- calibration should not regress materially
- the improvement should be large enough to justify a rollout

## Practical Notes

- Keep experiment logging best-effort so training never blocks on tracking.
- Use the run name to make it easy to map a model artifact back to the
  training window and season.
- Log enough metrics to answer: "What changed, why did it improve, and is it
  stable?"
