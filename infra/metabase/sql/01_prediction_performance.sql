-- Prediction Performance dashboard blueprints
-- Variables expected in Metabase:
--   {{season}}      -> Text (e.g., 2025-26)
--   {{model_name}}  -> Text (optional)

-- 1) KPI snapshot
SELECT
  COUNT(*) FILTER (WHERE p.was_correct IS NOT NULL) AS evaluated_predictions,
  ROUND(
    AVG(CASE WHEN p.was_correct THEN 1.0 ELSE 0.0 END)::numeric,
    4
  ) AS accuracy,
  ROUND(
    AVG(
      POWER(
        COALESCE(p.home_win_prob, 0.5) -
        CASE WHEN m.winner_team_id = m.home_team_id THEN 1.0 ELSE 0.0 END,
        2
      )
    )::numeric,
    4
  ) AS brier_score
FROM predictions p
JOIN matches m ON m.game_id = p.game_id
WHERE m.season = {{season}}
  [[AND p.model_name = {{model_name}}]]
  AND p.was_correct IS NOT NULL
  AND m.winner_team_id IS NOT NULL;

-- 2) Daily accuracy trend
SELECT
  m.game_date::date AS game_date,
  COUNT(*) AS evaluated_predictions,
  ROUND(
    AVG(CASE WHEN p.was_correct THEN 1.0 ELSE 0.0 END)::numeric,
    4
  ) AS accuracy
FROM predictions p
JOIN matches m ON m.game_id = p.game_id
WHERE m.season = {{season}}
  [[AND p.model_name = {{model_name}}]]
  AND p.was_correct IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- 3) Daily Brier score trend
SELECT
  m.game_date::date AS game_date,
  ROUND(
    AVG(
      POWER(
        COALESCE(p.home_win_prob, 0.5) -
        CASE WHEN m.winner_team_id = m.home_team_id THEN 1.0 ELSE 0.0 END,
        2
      )
    )::numeric,
    4
  ) AS brier_score
FROM predictions p
JOIN matches m ON m.game_id = p.game_id
WHERE m.season = {{season}}
  [[AND p.model_name = {{model_name}}]]
  AND m.winner_team_id IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- 4) Confidence bucket distribution
SELECT
  CONCAT(
    LPAD(((width_bucket(p.confidence, 0, 1, 10) - 1) * 10)::text, 2, '0'),
    '-',
    LPAD((width_bucket(p.confidence, 0, 1, 10) * 10)::text, 2, '0'),
    '%'
  ) AS confidence_bucket,
  COUNT(*) AS prediction_count
FROM predictions p
JOIN matches m ON m.game_id = p.game_id
WHERE m.season = {{season}}
  [[AND p.model_name = {{model_name}}]]
  AND p.confidence IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- 5) Calibration table (bin-level)
WITH bins AS (
  SELECT
    width_bucket(COALESCE(p.home_win_prob, 0.5), 0, 1, 10) AS prob_bin,
    COALESCE(p.home_win_prob, 0.5) AS predicted_home_win_prob,
    CASE WHEN m.winner_team_id = m.home_team_id THEN 1.0 ELSE 0.0 END AS actual_home_win
  FROM predictions p
  JOIN matches m ON m.game_id = p.game_id
  WHERE m.season = {{season}}
    [[AND p.model_name = {{model_name}}]]
    AND m.winner_team_id IS NOT NULL
)
SELECT
  prob_bin,
  ROUND(AVG(predicted_home_win_prob)::numeric, 4) AS avg_predicted_prob,
  ROUND(AVG(actual_home_win)::numeric, 4) AS actual_win_rate,
  COUNT(*) AS samples
FROM bins
GROUP BY prob_bin
ORDER BY prob_bin;
