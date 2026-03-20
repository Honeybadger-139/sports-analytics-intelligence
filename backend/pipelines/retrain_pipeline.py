"""
Vertex AI retrain pipeline for NBA model governance.

This module defines a six-step Kubeflow Pipeline that:
1. loads and validates the historical training dataset,
2. trains the challenger ensemble,
3. compares it with the champion,
4. registers the model in Vertex AI,
5. promotes it when it clears the threshold, and
6. writes a retrain audit record.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, NamedTuple

from kfp import dsl


TrainOutputs = NamedTuple(
    "TrainOutputs",
    [
        ("gcs_model_uri", str),
        ("cv_accuracy", float),
        ("brier_score", float),
        ("log_loss", float),
    ],
)

@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "google-cloud-storage==2.18.2",
        "pandas==2.2.3",
        "numpy==1.26.4",
        "sqlalchemy==2.0.36",
        "psycopg2-binary==2.9.10",
    ],
)
def load_and_validate_data(season: str, database_url: str, min_games: int = 50) -> str:
    """Load the retraining dataset, validate freshness, and persist a GCS snapshot."""
    import os
    import tempfile
    from datetime import datetime, timezone

    import pandas as pd
    from google.cloud import storage
    from sqlalchemy import create_engine, text

    if not database_url:
        raise ValueError("database_url is required for retraining")

    engine = create_engine(database_url)

    with engine.connect() as conn:
        match_count = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM matches
                    WHERE season = :season
                    """
                ),
                {"season": season},
            ).scalar()
            or 0
        )
        team_stats_count = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM team_game_stats
                    WHERE season = :season
                    """
                ),
                {"season": season},
            ).scalar()
            or 0
        )
        max_game_date = conn.execute(
            text(
                """
                SELECT MAX(game_date)
                FROM matches
                WHERE season = :season
                """
            ),
            {"season": season},
        ).scalar()

        if match_count < min_games:
            raise ValueError(f"not enough matches for retraining: {match_count} < {min_games}")

        if max_game_date is None:
            raise ValueError("matches table has no game_date values for the requested season")

        freshness_days = (
            pd.Timestamp.utcnow().tz_localize(None).normalize() - pd.Timestamp(max_game_date)
        ).days
        if team_stats_count == 0:
            raise ValueError(f"no team_game_stats rows found for season={season}")
        if freshness_days > 7:
            raise ValueError(f"stale matches data: latest game_date is {max_game_date}")

        query = text(
            """
            SELECT
                m.game_id,
                m.game_date,
                m.season,
                m.home_team_id,
                m.away_team_id,
                m.winner_team_id,
                hf.win_pct_last_5,
                hf.win_pct_last_10,
                hf.avg_point_diff_last_5,
                hf.avg_point_diff_last_10,
                1 AS is_home,
                hf.days_rest,
                CASE WHEN hf.is_back_to_back THEN 1 ELSE 0 END AS is_back_to_back,
                hf.avg_off_rating_last_5,
                hf.avg_def_rating_last_5,
                hf.avg_pace_last_5,
                hf.avg_efg_last_5,
                hf.h2h_win_pct,
                hf.h2h_avg_margin,
                CASE WHEN hf.h2h_win_pct IS NOT NULL THEN 1 ELSE 0 END AS h2h_data_available,
                hf.current_streak,
                af.win_pct_last_5 AS opp_win_pct_last_5,
                af.win_pct_last_10 AS opp_win_pct_last_10,
                af.avg_point_diff_last_5 AS opp_avg_point_diff_last_5,
                af.avg_point_diff_last_10 AS opp_avg_point_diff_last_10,
                af.days_rest AS opp_days_rest,
                CASE WHEN af.is_back_to_back THEN 1 ELSE 0 END AS opp_is_back_to_back,
                af.avg_off_rating_last_5 AS opp_avg_off_rating_last_5,
                af.avg_def_rating_last_5 AS opp_avg_def_rating_last_5,
                af.avg_pace_last_5 AS opp_avg_pace_last_5,
                af.avg_efg_last_5 AS opp_avg_efg_last_5
            FROM matches m
            LEFT JOIN match_features hf
                ON m.game_id = hf.game_id AND m.home_team_id = hf.team_id
            LEFT JOIN match_features af
                ON m.game_id = af.game_id AND m.away_team_id = af.team_id
            WHERE m.season = :season
              AND m.winner_team_id IS NOT NULL
            ORDER BY m.game_date ASC, m.game_id ASC
            """
        )
        df = pd.read_sql(query, conn, params={"season": season})

    if df.empty:
        raise ValueError(f"no training rows found for season={season}")

    df = df.copy()
    df["home_team_win"] = (df["winner_team_id"] == df["home_team_id"]).astype(int)
    df = df.sort_values(["game_date", "game_id"]).reset_index(drop=True)

    # Minimal feature hygiene: the downstream trainer will perform
    # domain-aware imputation again, but we still normalise the raw snapshot.
    feature_columns = [
        "win_pct_last_5",
        "win_pct_last_10",
        "avg_point_diff_last_5",
        "avg_point_diff_last_10",
        "is_home",
        "days_rest",
        "is_back_to_back",
        "avg_off_rating_last_5",
        "avg_def_rating_last_5",
        "avg_pace_last_5",
        "avg_efg_last_5",
        "h2h_win_pct",
        "h2h_avg_margin",
        "h2h_data_available",
        "current_streak",
        "opp_win_pct_last_5",
        "opp_win_pct_last_10",
        "opp_avg_point_diff_last_5",
        "opp_avg_point_diff_last_10",
        "opp_days_rest",
        "opp_is_back_to_back",
        "opp_avg_off_rating_last_5",
        "opp_avg_def_rating_last_5",
        "opp_avg_pace_last_5",
        "opp_avg_efg_last_5",
    ]
    df["h2h_data_available"] = df["h2h_win_pct"].notna().astype(int)
    df = df[["game_id", "game_date", "season", "home_team_id", "away_team_id", "winner_team_id", "home_team_win"] + feature_columns]

    bucket_name = os.getenv("GCS_MODELS_BUCKET") or os.getenv("GCS_RAW_BUCKET") or "gamethread-models"
    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    object_name = f"pipelines/retrain/{season}/{run_stamp}/training_dataset.csv"

    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as handle:
        temp_path = handle.name
        df.to_csv(handle, index=False)

    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        bucket.blob(object_name).upload_from_filename(temp_path)
        gcs_uri = f"gs://{bucket_name}/{object_name}"
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass

    return gcs_uri


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "google-cloud-storage==2.18.2",
        "pandas==2.2.3",
        "numpy==1.26.4",
        "scikit-learn==1.6.1",
        "xgboost==2.1.3",
        "lightgbm==4.5.0",
        "joblib",
    ],
)
def train_ensemble(dataset_uri: str, season: str, database_url: str) -> TrainOutputs:
    """Train the challenger ensemble and persist the model bundle in GCS."""
    import io
    import os
    import tempfile
    from datetime import datetime, timezone

    import joblib
    import numpy as np
    import pandas as pd
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, brier_score_loss, log_loss
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.utils.validation import check_is_fitted
    from sklearn.ensemble import VotingClassifier
    import xgboost as xgb
    import lightgbm as lgb

    from google.cloud import storage

    if not dataset_uri:
        raise ValueError("dataset_uri is required")

    if dataset_uri.startswith("gs://"):
        _, bucket_and_path = dataset_uri.split("gs://", 1)
        bucket_name, object_name = bucket_and_path.split("/", 1)
        client = storage.Client()
        blob = client.bucket(bucket_name).blob(object_name)
        csv_bytes = blob.download_as_bytes()
        df = pd.read_csv(io.BytesIO(csv_bytes))
    else:
        df = pd.read_csv(dataset_uri)

    if df.empty:
        raise ValueError("training dataset is empty")

    df = df.sort_values(["game_date", "game_id"]).reset_index(drop=True)
    y = df["home_team_win"].astype(int).to_numpy()
    feature_columns = [
        "win_pct_last_5",
        "win_pct_last_10",
        "avg_point_diff_last_5",
        "avg_point_diff_last_10",
        "is_home",
        "days_rest",
        "is_back_to_back",
        "avg_off_rating_last_5",
        "avg_def_rating_last_5",
        "avg_pace_last_5",
        "avg_efg_last_5",
        "h2h_win_pct",
        "h2h_avg_margin",
        "h2h_data_available",
        "current_streak",
        "opp_win_pct_last_5",
        "opp_win_pct_last_10",
        "opp_avg_point_diff_last_5",
        "opp_avg_point_diff_last_10",
        "opp_days_rest",
        "opp_is_back_to_back",
        "opp_avg_off_rating_last_5",
        "opp_avg_def_rating_last_5",
        "opp_avg_pace_last_5",
        "opp_avg_efg_last_5",
    ]
    X = df[feature_columns].apply(pd.to_numeric, errors="coerce").fillna(0.0)

    split_index = max(int(len(df) * 0.8), 1)
    train_X = X.iloc[:split_index]
    train_y = y[:split_index]
    test_X = X.iloc[split_index:]
    test_y = y[split_index:]
    if test_X.empty:
        test_X = train_X
        test_y = train_y

    logistic = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value=0.0)),
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=1000, random_state=42)),
        ]
    )
    logistic.fit(train_X, train_y)

    xgb_model = xgb.XGBClassifier(
        n_estimators=120,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="logloss",
        random_state=42,
        n_jobs=1,
    )
    xgb_model.fit(train_X, train_y)

    lgb_model = lgb.LGBMClassifier(
        n_estimators=120,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        n_jobs=1,
    )
    lgb_model.fit(train_X, train_y)

    logistic_prob = logistic.predict_proba(test_X)[:, 1]
    xgb_prob = xgb_model.predict_proba(test_X)[:, 1]
    lgb_prob = lgb_model.predict_proba(test_X)[:, 1]
    ensemble_prob = np.average([logistic_prob, xgb_prob, lgb_prob], axis=0, weights=[0.3, 0.4, 0.3])
    ensemble_pred = (ensemble_prob >= 0.5).astype(int)

    cv_accuracy = float(accuracy_score(test_y, ensemble_pred))
    brier = float(brier_score_loss(test_y, ensemble_prob))
    loss = float(log_loss(test_y, np.clip(ensemble_prob, 1e-6, 1 - 1e-6)))

    bundle = {
        "logistic_regression": logistic,
        "xgboost": xgb_model,
        "lightgbm": lgb_model,
        "weights": {"logistic_regression": 0.3, "xgboost": 0.4, "lightgbm": 0.3},
        "feature_columns": feature_columns,
    }

    bucket_name = os.getenv("GCS_MODELS_BUCKET") or os.getenv("GCS_RAW_BUCKET") or "gamethread-models"
    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    object_prefix = f"pipelines/retrain/{season}/{run_stamp}/model"
    model_object = f"{object_prefix}/ensemble_bundle.joblib"
    gcs_model_uri = f"gs://{bucket_name}/{object_prefix}/"

    with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as handle:
        temp_model_path = handle.name
    try:
        joblib.dump(bundle, temp_model_path)
        client = storage.Client()
        client.bucket(bucket_name).blob(model_object).upload_from_filename(temp_model_path)
    finally:
        try:
            os.remove(temp_model_path)
        except OSError:
            pass

    metrics_path = None
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        metrics_path = handle.name
        json.dump(
            {
                "season": season,
                "cv_accuracy": cv_accuracy,
                "brier_score": brier,
                "log_loss": loss,
                "rows": int(len(df)),
            },
            handle,
            indent=2,
        )
    try:
        client = storage.Client()
        client.bucket(bucket_name).blob(f"{object_prefix}/metrics.json").upload_from_filename(metrics_path)
    finally:
        if metrics_path:
            try:
                os.remove(metrics_path)
            except OSError:
                pass

    return gcs_model_uri, cv_accuracy, brier, loss


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "google-cloud-aiplatform==1.70.0",
    ],
)
def evaluate_vs_champion(
    new_model_metrics: Dict[str, float],
    vertex_model_name: str,
    project_id: str,
    min_improvement: float = 0.01,
) -> bool:
    """Return True when the challenger clears the minimum improvement threshold."""
    if not new_model_metrics:
        return False

    challenger_accuracy = float(new_model_metrics.get("cv_accuracy", 0.0) or 0.0)
    challenger_brier = float(new_model_metrics.get("brier_score", 1.0) or 1.0)

    champion_accuracy = float(os.getenv("CHAMPION_CV_ACCURACY", "0.55"))
    champion_brier = float(os.getenv("CHAMPION_BRIER_SCORE", "0.25"))

    accuracy_gain = challenger_accuracy - champion_accuracy
    brier_gain = champion_brier - challenger_brier
    return accuracy_gain >= min_improvement or brier_gain >= min_improvement


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "google-cloud-aiplatform==1.70.0",
    ],
)
def register_model(
    gcs_model_uri: str,
    new_model_metrics: Dict[str, float],
    project_id: str,
    should_promote: bool,
) -> str:
    """Register the retrained bundle in Vertex AI Model Registry."""
    if not gcs_model_uri:
        raise ValueError("gcs_model_uri is required")

    try:
        from google.cloud import aiplatform
    except Exception:
        return gcs_model_uri

    location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    display_name = os.getenv("VERTEX_MODEL_NAME", "nba-ensemble")
    serving_image = os.getenv(
        "VERTEX_SERVING_IMAGE_URI",
        "us-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-6:latest",
    )

    aiplatform.init(project=project_id or os.getenv("GOOGLE_CLOUD_PROJECT"), location=location)
    model = aiplatform.Model.upload(
        display_name=display_name,
        artifact_uri=gcs_model_uri,
        serving_container_image_uri=serving_image,
        description="NBA retrain pipeline challenger model",
        labels={
            "season": str(os.getenv("VERTEX_TRAIN_SEASON", "unknown")),
            "accuracy": f"{float(new_model_metrics.get('cv_accuracy', 0.0) or 0.0):.4f}",
            "brier_score": f"{float(new_model_metrics.get('brier_score', 0.0) or 0.0):.4f}",
            "promotion_candidate": str(bool(should_promote)).lower(),
        },
    )
    return getattr(model, "resource_name", gcs_model_uri)


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "google-cloud-aiplatform==1.70.0",
    ],
)
def promote_to_production(
    model_resource_name: str,
    project_id: str,
    should_promote: bool,
) -> str:
    """Assign the production alias when the challenger wins."""
    if not should_promote:
        return "promotion_skipped"

    try:
        from google.cloud import aiplatform
    except Exception:
        return "promotion_skipped"

    if not model_resource_name or not model_resource_name.startswith("projects/"):
        return "promotion_skipped"

    location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    aiplatform.init(project=project_id or os.getenv("GOOGLE_CLOUD_PROJECT"), location=location)
    model = aiplatform.Model(model_resource_name)
    model.add_version_aliases(["production"])
    return "production"


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "sqlalchemy==2.0.36",
        "psycopg2-binary==2.9.10",
    ],
)
def write_retrain_audit(
    run_id: str,
    new_metrics: Dict[str, float],
    promoted: bool,
    database_url: str,
    trigger_reason: str,
) -> str:
    """Persist retrain audit details for governance and rollback tracing."""
    import json

    from sqlalchemy import create_engine, text

    if not database_url:
        return "audit_skipped"

    engine = create_engine(database_url)
    rollback_plan = {
        "strategy": "revert_to_previous_model_artifact",
        "criteria": [
            "post-retrain accuracy below prior baseline by > 0.03",
            "post-retrain brier worsens by > 0.02",
        ],
    }
    run_details = {
        "run_id": run_id,
        "trigger_reason": trigger_reason,
        "promoted": bool(promoted),
        "new_metrics": new_metrics,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO retrain_jobs (
                    season,
                    status,
                    trigger_source,
                    reasons,
                    metrics,
                    thresholds,
                    artifact_snapshot,
                    rollback_plan,
                    run_details
                )
                VALUES (
                    :season,
                    :status,
                    :trigger_source,
                    CAST(:reasons AS JSONB),
                    CAST(:metrics AS JSONB),
                    CAST(:thresholds AS JSONB),
                    CAST(:artifact_snapshot AS JSONB),
                    CAST(:rollback_plan AS JSONB),
                    CAST(:run_details AS JSONB)
                )
                """
            ),
            {
                "season": str(os.getenv("VERTEX_TRAIN_SEASON", "2025-26")),
                "status": "completed" if promoted else "review",
                "trigger_source": trigger_reason,
                "reasons": json.dumps([trigger_reason]),
                "metrics": json.dumps(new_metrics),
                "thresholds": json.dumps(
                    {
                        "min_improvement": float(os.getenv("VERTEX_MIN_IMPROVEMENT", "0.01")),
                    }
                ),
                "artifact_snapshot": json.dumps(
                    {
                        "model_registry": os.getenv("VERTEX_MODEL_NAME", "nba-ensemble"),
                        "promotion": bool(promoted),
                    }
                ),
                "rollback_plan": json.dumps(rollback_plan),
                "run_details": json.dumps(run_details),
            },
        )

    return "audit_written"


@dsl.pipeline(
    name="nba-retrain-pipeline",
    description="Champion vs challenger retrain with governance",
)
def retrain_pipeline(
    season: str = "2025-26",
    trigger_reason: str = "scheduled",
    database_url: str = "",
    project_id: str = "",
    min_improvement: float = 0.01,
) -> None:
    """Define the retrain pipeline graph."""
    run_id = f"retrain-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    with dsl.ExitHandler(
        write_retrain_audit(
            run_id=run_id,
            new_metrics={},
            promoted=False,
            database_url=database_url,
            trigger_reason=trigger_reason,
        )
    ):
        dataset_task = load_and_validate_data(
            season=season,
            database_url=database_url,
        )
        train_task = train_ensemble(
            dataset_uri=dataset_task.output,
            season=season,
            database_url=database_url,
        )

        metrics = {
            "cv_accuracy": train_task.outputs["cv_accuracy"],
            "brier_score": train_task.outputs["brier_score"],
            "log_loss": train_task.outputs["log_loss"],
        }
        champion_task = evaluate_vs_champion(
            new_model_metrics=metrics,
            vertex_model_name=os.getenv("VERTEX_MODEL_NAME", "nba-ensemble"),
            project_id=project_id,
            min_improvement=min_improvement,
        )
        register_task = register_model(
            gcs_model_uri=train_task.outputs["gcs_model_uri"],
            new_model_metrics=metrics,
            project_id=project_id,
            should_promote=champion_task.output,
        )
        promote_to_production(
            model_resource_name=register_task.output,
            project_id=project_id,
            should_promote=champion_task.output,
        )


if __name__ == "__main__":
    retrain_pipeline(
        season=os.getenv("VERTEX_TRAIN_SEASON", "2025-26"),
        trigger_reason="manual",
        database_url=os.getenv("DATABASE_URL", ""),
        project_id=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
    )
