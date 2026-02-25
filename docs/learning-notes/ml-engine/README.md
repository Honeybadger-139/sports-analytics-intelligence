# ML Engine — Learning Notes (Phase 1)

## Overview
The ML Engine represents **Phase 1** of the platform transition. While Phase 0 focused on the raw data ingestion (Data Layer), Phase 1 introduces the feature store and the foundational logic for generating predictions.

## Files in This Folder (Phase 1)

| File | Topic | Key Concepts |
|------|-------|-------------|
| [rolling-features.md](rolling-features.md) | **Rolling Features** | Team momentum, point differentials, leakage prevention |
| [head-to-head-metrics.md](head-to-head-metrics.md) | **H2H Analysis** | Matchup-specific edge, historical dominance, self-joins |
| [etl-idempotency.md](etl-idempotency.md) | **Resilient Pipelines** | Idempotency, watermarking, exponential backoff (Advanced Ingestion) |
| [model-selection.md](model-selection.md) | **Model Selection** | XGBoost vs LightGBM, ensemble strategy |

*Note: Phase 2 (Infrastructure/Intelligence Layer) nodes will be documented in their respective higher-level folders.*
