-- Pipeline Health dashboard blueprints
-- Optional variables expected in Metabase:
--   {{module}} -> Text (ingestion / feature_store / ...)
--   {{status}} -> Text (success / failed / ...)

-- 1) Latest status by module
WITH latest AS (
  SELECT
    module,
    status,
    sync_time,
    records_processed,
    records_inserted,
    ROW_NUMBER() OVER (PARTITION BY module ORDER BY sync_time DESC, id DESC) AS rn
  FROM pipeline_audit
)
SELECT
  module,
  status,
  sync_time,
  records_processed,
  records_inserted
FROM latest
WHERE rn = 1
ORDER BY module;

-- 2) Runs by day and status
SELECT
  DATE(sync_time) AS run_day,
  module,
  status,
  COUNT(*) AS runs
FROM pipeline_audit
WHERE 1 = 1
  [[AND module = {{module}}]]
  [[AND status = {{status}}]]
GROUP BY 1, 2, 3
ORDER BY 1 DESC, 2, 3;

-- 3) Records inserted trend
SELECT
  DATE(sync_time) AS run_day,
  module,
  SUM(COALESCE(records_inserted, 0)) AS rows_inserted
FROM pipeline_audit
WHERE 1 = 1
  [[AND module = {{module}}]]
GROUP BY 1, 2
ORDER BY 1 DESC, 2;

-- 4) Freshness in hours by module
SELECT
  module,
  ROUND((EXTRACT(EPOCH FROM (NOW() - MAX(sync_time))) / 3600.0)::numeric, 2) AS freshness_hours,
  MAX(sync_time) AS last_success_time
FROM pipeline_audit
WHERE status = 'success'
GROUP BY module
ORDER BY freshness_hours DESC;

-- 5) Intelligence pipeline freshness (RAG proxy)
SELECT
  module,
  status,
  MAX(run_time) AS last_run_time,
  ROUND((EXTRACT(EPOCH FROM (NOW() - MAX(run_time))) / 3600.0)::numeric, 2) AS freshness_hours
FROM intelligence_audit
GROUP BY module, status
ORDER BY freshness_hours DESC;
