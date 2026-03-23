# Metabase Dashboard Plan (2 Starter Dashboards)

This document defines the two dashboards to stand up first in Metabase for the
Sports Analytics Intelligence Platform.

## Why Metabase

- Drag/drop exploration for dimensions, measures, filters, and grouping.
- Fast dashboard authoring directly on PostgreSQL (Cloud SQL).
- Easy embedding/linking from Vercel frontend.

## Dashboard 1: Prediction Performance

Goal:
- Show model quality and calibration, not only win/loss accuracy.

Data:
- `predictions` joined with `matches`.

Questions to create:
1. Overall KPIs (accuracy, brier score, evaluated predictions).
2. Daily accuracy trend.
3. Daily Brier score trend.
4. Confidence bucket distribution.
5. Calibration table (bucketed predicted probability vs actual win rate).

SQL blueprint:
- `infra/metabase/sql/01_prediction_performance.sql`

Dashboard filters:
- `season`
- `model_name`
- date range (`game_date`)

## Dashboard 2: Pipeline Health

Goal:
- Give a single operational view of ingestion + feature + intelligence freshness.

Data:
- `pipeline_audit`
- `intelligence_audit`

Questions to create:
1. Latest status by module.
2. Daily run volume and status counts.
3. Records inserted trend by module.
4. Freshness in hours for ingestion/features/rag-like intelligence jobs.

SQL blueprint:
- `infra/metabase/sql/02_pipeline_health.sql`

Dashboard filters:
- module
- status
- date range

## Frontend Wiring

Set these env vars in Vercel for direct links from `/dashboard`:

- `VITE_DASHBOARD_PROVIDER=metabase`
- `VITE_METABASE_URL=https://<your-metabase-host>`
- `VITE_METABASE_DASHBOARD_PREDICTION_ID=<id>`
- `VITE_METABASE_DASHBOARD_PIPELINE_ID=<id>`

If dashboard IDs are not set, the frontend falls back to opening the Metabase
builder screen.
