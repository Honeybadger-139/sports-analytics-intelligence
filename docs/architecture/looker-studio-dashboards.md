# Looker Studio Dashboards

This document specifies the four Looker Studio dashboards that should be built
for the Sports Analytics Intelligence Platform. These are documentation-only
artifacts; the actual dashboards can be assembled manually in Looker Studio
using the data sources and metrics described below.

## Dashboard 1: Prediction Performance

Purpose:
Track how well the live prediction system is performing over time.

Data sources:
- Cloud SQL `predictions` table
- Cloud SQL `matches` table

Core charts:
- Rolling 30-day accuracy time series
- Brier score time series
- Calibration curve: predicted probability vs actual win rate
- Prediction volume by confidence bucket

KPIs:
- Overall accuracy
- Last 7 days accuracy
- Brier score
- Total predictions

Filters:
- Season selector
- Date range selector
- Model selector

Notes:
- Use `was_correct` as the correctness target.
- Prefer a rolling window metric for trend stability rather than only raw daily
  accuracy.
- Keep the calibration chart visible so the dashboard shows probability quality,
  not just classification accuracy.

## Dashboard 2: Bankroll And Betting

Purpose:
Show betting performance and capital allocation behavior.

Data source:
- Cloud SQL `bets` table

Core charts:
- Cumulative P&L line chart
- Stake distribution histogram
- ROI by confidence tier
- Win rate by stake size

KPIs:
- Total P&L
- Total bets
- ROI %
- Current bankroll

Filters:
- Season selector
- Bet status selector
- Confidence tier selector

Notes:
- Use the bet ledger as the source of truth for realized returns.
- Keep confidence-tier slicing consistent with the logic used in the betting
  service so the dashboard and model behavior stay aligned.

## Dashboard 3: Pipeline Health

Purpose:
Give an operational view of ingestion, feature engineering, and RAG refresh
freshness.

Data sources:
- Cloud SQL `pipeline_audit` table
- Cloud SQL `intelligence_audit` table

Core charts:
- Ingestion run status timeline
- Rows ingested per day
- Feature computation elapsed-time trend
- RAG refresh freshness

KPIs:
- Last ingestion status
- Last feature run
- Data freshness hours

Filters:
- Module selector: ingestion, features, rag
- Season selector
- Date range selector

Notes:
- Highlight failed and stale runs clearly so operators can spot issues fast.
- Keep the module filter narrow so the dashboard remains readable during
  incident review.

## Dashboard 4: MLOps

Purpose:
Surface model quality, retrain history, and promotion behavior.

Data sources:
- Cloud SQL `mlops_monitoring_snapshot` table
- Cloud SQL `retrain_jobs` table
- Vertex AI Experiments export or queryable experiment metadata

Core charts:
- Model accuracy over time
- Brier score over time
- Retrain history with trigger reason and accuracy delta
- Model version timeline

KPIs:
- Current model accuracy
- Last retrain date
- Total retrain count
- Accuracy improvement per retrain

Filters:
- Season selector
- Model selector
- Trigger reason selector

Notes:
- Keep champion/challenger context visible in chart labels when possible.
- If the Vertex export is not available yet, start with Cloud SQL-backed
  retrain history and add the Vertex panel later.

## Build Order

If building manually, start with:
1. Prediction Performance
2. Pipeline Health
3. MLOps
4. Bankroll And Betting

That sequence gives the fastest operational value while the rest of the system
is still evolving.

