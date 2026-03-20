# Looker Studio Setup Guide

This guide explains how to connect Looker Studio to the platform data sources
and how to keep the dashboards fresh and shareable.

## 1. Connect To Cloud SQL

Use the PostgreSQL connector in Looker Studio.

Recommended connection settings:
- Host: Cloud SQL PostgreSQL connector or authorized Cloud SQL endpoint
- Port: `5432`
- Database: `sports_analytics`
- User: the read-only analytics user
- Password: store in your secure secret workflow, not in the dashboard spec

Cloud Run and backend services already use Cloud SQL via the Auth Proxy / Unix
socket pattern in production. For Looker Studio, connect through the PostgreSQL
connector so the dashboard can query the same source tables directly.

Suggested tables to expose:
- `predictions`
- `matches`
- `bets`
- `pipeline_audit`
- `intelligence_audit`
- `mlops_monitoring_snapshot`
- `retrain_jobs`

## 2. Create Data Sources

Create one Looker Studio data source per analytical surface when possible:
- Prediction analytics
- Betting analytics
- Pipeline health
- MLOps tracking

That keeps field naming and chart logic easier to manage.

## 3. Refresh Schedule

Recommended refresh policy:
- Prediction and MLOps dashboards: every 1 hour
- Pipeline Health dashboard: every 15 minutes or 30 minutes
- Betting dashboard: every 1 hour

If performance becomes an issue, reduce chart complexity before reducing
refresh frequency.

## 4. Sharing

Recommended sharing pattern:
- Share with read-only access by default
- Group viewers by role: engineering, product, ops
- Restrict edit permissions to a small set of maintainers

If external stakeholders need access, duplicate the dashboard into a separate
share group so operational controls stay tight.

## 5. Useful Filters

Standard filters to include on most dashboards:
- Season
- Date range
- Model name
- Module name
- Confidence tier

The goal is to keep the dashboards consistent so people do not need to learn a
different filter layout for every page.

## 6. Operational Tips

- Validate the SQL query in Cloud SQL before building the chart.
- Keep calculated fields small and readable.
- Use rolling windows for time series charts where raw daily values are noisy.
- Prefer a clear business KPI over a giant table when you need an executive
  summary.

