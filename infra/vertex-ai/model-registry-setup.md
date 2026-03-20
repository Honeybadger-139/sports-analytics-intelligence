# Vertex AI Model Registry Setup

## Purpose

This document captures the model registry convention for NBA prediction models.
We use Vertex AI Model Registry for versioned metadata and alias-based rollbacks,
while the serving API still loads local or GCS artifacts directly.

## Naming Convention

- Model display name: `nba-ensemble` or a model-family name such as `xgboost`
- Version aliases:
  - `production` for the live serving candidate
  - `staging` for the challenger under evaluation
  - `champion` for the currently best validated version
  - `previous` for the last good production version

## Upload Flow

1. Train the model locally.
2. Save the artifact to GCS.
3. Register the artifact in Vertex AI Model Registry.
4. Apply a version alias to the resulting model version.

## Rollback Procedure

Rollback is an alias change, not a redeploy.

1. Identify the previous version that should become active.
2. Remove `production` from the bad version if needed.
3. Add `production` to the previous good version.
4. Keep `staging` or `champion` labels aligned with the evaluation state.

## Why Aliases Beat Raw Version Numbers

- Version numbers are useful for history.
- Aliases are useful for operations.
- A deployment can always point at `production` without caring which numeric version owns it today.
- Rolling back is one alias reassignment instead of an image rebuild or app redeploy.

## Console Checks

- Open Vertex AI Model Registry in the GCP console.
- Confirm the model name and version lineage.
- Verify the expected alias is attached to the live version.
- Check the artifact URI for the uploaded GCS path.

## Operational Notes

- The predictor can continue to load from local or GCS artifacts.
- The registry is the source of truth for version lineage and alias policy.
- Keep the alias strategy consistent across training, promotion, and rollback.
