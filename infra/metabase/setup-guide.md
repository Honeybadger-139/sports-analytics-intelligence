# Metabase Setup Guide (GCP + Vercel)

This guide gives a practical path to run Metabase against your Cloud SQL
PostgreSQL database and connect it to the existing Vercel frontend.

## 1. Deploy Metabase

Recommended:
- Cloud Run service `gamethread-metabase`.

Container:
- `metabase/metabase:latest`

Required env vars:
- `MB_DB_TYPE=postgres`
- `MB_DB_DBNAME=<metabase_app_db>`
- `MB_DB_PORT=5432`
- `MB_DB_USER=<metabase_app_user>`
- `MB_DB_PASS=<metabase_app_password>`
- `MB_DB_HOST=/cloudsql/<project>:<region>:<instance>` (Cloud SQL socket)
- `JAVA_TIMEZONE=UTC`

Notes:
- Use a separate database/schema for Metabase metadata.
- Add Cloud SQL connection on the Cloud Run service.

## 2. Browser Setup Steps

1. Open the Metabase URL in browser and complete admin onboarding.
2. Add a data source:
   - Type: PostgreSQL
   - Host: Cloud SQL endpoint or socket-backed host
   - Database: `sports_analytics`
   - User/password: read-only analytics credentials
3. Validate connection and save.
4. Create a collection named `GameThread Dashboards`.

## 3. Create the Two Dashboards

1. Open SQL editor in Metabase.
2. Run queries from:
   - `infra/metabase/sql/01_prediction_performance.sql`
   - `infra/metabase/sql/02_pipeline_health.sql`
3. Save each question into `GameThread Dashboards`.
4. Build dashboards:
   - `Prediction Performance`
   - `Pipeline Health`
5. Add dashboard filters (`season`, `model_name`, date range) and map them to
   each card.

## 4. Wire Frontend (Vercel)

Set Vercel project env vars:

- `VITE_DASHBOARD_PROVIDER=metabase`
- `VITE_METABASE_URL=https://<metabase-host>`
- `VITE_METABASE_DASHBOARD_PREDICTION_ID=<metabase-dashboard-id>`
- `VITE_METABASE_DASHBOARD_PIPELINE_ID=<metabase-dashboard-id>`

Redeploy frontend after env var changes.

## 5. Security Baseline

- Use a read-only DB user for analytics queries.
- Restrict Metabase access with workspace auth and strong admin password.
- Keep Metabase behind HTTPS only.
