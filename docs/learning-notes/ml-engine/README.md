# ML Engine — Learning Notes (Phase 1)

## Overview
The ML Engine represents **Phase 1** of the platform transition. While **Phase 0** focused on Data Foundation (raw data ingestion, schema, and foundational feature preparation), Phase 1 introduces model training and prediction logic.

## Files in This Folder (Phase 1)

| File | Topic | Key Concepts |
|------|-------|-------------|
| [rolling-features.md](rolling-features.md) | **Rolling Features** | Team momentum, point differentials, leakage prevention |
| [head-to-head-metrics.md](head-to-head-metrics.md) | **H2H Analysis** | Matchup-specific edge, historical dominance, self-joins |
| [etl-idempotency.md](etl-idempotency.md) | **Resilient Pipelines** | Idempotency, watermarking, exponential backoff (Advanced Ingestion) |
| [model-selection.md](model-selection.md) | **Model Selection** | XGBoost vs LightGBM, ensemble strategy |

*Note: Phase 0.5 covers resilience/observability hardening and is documented under Data Layer notes.*
