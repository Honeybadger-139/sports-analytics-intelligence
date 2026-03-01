# MLOps — Learning Notes

> 📌 **Status**: Implemented baseline in **Phase 5 foundation**.

## What Is MLOps?

MLOps (Machine Learning Operations) is the practice of deploying, monitoring, and maintaining ML models in production. It bridges the gap between "model works in a notebook" and "model works reliably at scale, 24/7."

## What We Implemented

1. Monitoring module: `backend/src/mlops/monitoring.py`
   - evaluated prediction volume
   - accuracy + Brier score
   - game-data freshness + pipeline freshness
   - rule-based alerts
2. Retrain policy module: `backend/src/mlops/retrain_policy.py`
   - deterministic dry-run decision engine
   - triggers:
     - accuracy breach
     - Brier breach
     - minimum new-label threshold
3. API contracts:
   - `GET /api/v1/mlops/monitoring`
   - `GET /api/v1/mlops/monitoring/trend`
   - `GET /api/v1/mlops/retrain/policy?dry_run=true`
4. Governance signal:
   - `/api/v1/system/status` now includes model artifact snapshot metadata.
5. Snapshot persistence:
   - monitoring overview writes `mlops_monitoring_snapshot` rows for trend analysis.
6. Deterministic escalation policy:
   - alerts now include `breach_streak`, `escalation_level`, and `recommended_action`
   - payload includes escalation summary state for incident routing (`none|active|watch|incident`)
7. Retrain queue automation baseline:
   - `dry_run=false` queues a retrain job with policy evidence snapshots
   - duplicate guard prevents repeated queued/running jobs in short windows
   - retrain queue is exposed via `GET /api/v1/mlops/retrain/jobs`
   - rollback baseline criteria are persisted with each queued job

## Why It Matters

Without MLOps, a strong model degrades silently in production.
This baseline gives us operational visibility and deterministic retrain logic before full automation.
Trend snapshots now make this visibility time-series ready for charting and alert trend analysis.

## Senior Manager Perspective

MLOps is not only "auto-retrain." It is a governance loop:

1. measure model behavior
2. compare against explicit thresholds
3. decide and document action
4. keep every decision auditable

## Interview Angle

> "I implemented a policy-driven MLOps baseline. Monitoring and retrain decisions are API-exposed and reproducible, which lets product and engineering teams agree on *when* retraining is justified."

## Junior vs Senior Answer

1. Junior:
   - "I monitor accuracy and retrain sometimes."
2. Senior:
   - "I codified monitoring and retrain policy as deterministic contracts with explicit thresholds, freshness checks, and dry-run action outputs to reduce operational ambiguity."
