"""
Prefect flow data contracts for the feature engineering pipeline.

These contracts formalize the handoff between raw ingestion and feature
computation so validation can fail fast before bad data reaches downstream
tasks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable, Optional, Sequence

from sqlalchemy import text


FEATURE_COLUMNS = [
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


def _as_set(columns: Iterable[str]) -> set[str]:
    return {str(col) for col in columns}


def _scalar(engine, sql: str, params: Optional[dict] = None):
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        return result.scalar()


def _iso_date(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


@dataclass
class IngestionContract:
    """What the ingestion job guarantees to the feature pipeline."""

    min_matches_per_day: int = 1
    max_null_rate: float = 0.15
    max_data_age_days: int = 7
    required_columns_matches: list[str] = field(
        default_factory=lambda: [
            "game_id",
            "game_date",
            "home_team_id",
            "away_team_id",
            "winner_team_id",
        ]
    )

    def validate_required_columns(self, actual_columns: Sequence[str]) -> None:
        missing = [col for col in self.required_columns_matches if col not in _as_set(actual_columns)]
        if missing:
            raise ValueError(f"Missing required matches columns: {', '.join(missing)}")

    def validate_raw_data(
        self,
        engine,
        seasons: Sequence[str],
        *,
        minimum_total_matches: int = 10,
        current_date: Optional[date] = None,
    ) -> dict:
        """Validate raw tables before feature engineering starts."""
        seasons = list(seasons) or []
        if not seasons:
            raise ValueError("At least one season is required for raw-data validation")

        today = current_date or datetime.utcnow().date()
        season_stats: list[dict] = []
        failures: list[dict] = []

        for season in seasons:
            matches_count = int(
                _scalar(
                    engine,
                    """
                    SELECT COUNT(*) AS matches_count
                    FROM matches
                    WHERE season = :season
                    """,
                    {"season": season},
                )
                or 0
            )
            team_stats_count = int(
                _scalar(
                    engine,
                    """
                    SELECT COUNT(*) AS team_stats_count
                    FROM team_game_stats tgs
                    JOIN matches m ON m.game_id = tgs.game_id
                    WHERE m.season = :season
                    """,
                    {"season": season},
                )
                or 0
            )
            max_game_date = _scalar(
                engine,
                """
                SELECT MAX(game_date) AS max_game_date
                FROM matches
                WHERE season = :season
                """,
                {"season": season},
            )

            null_counts = {
                "game_date": int(
                    _scalar(
                        engine,
                        """
                        SELECT COUNT(*) AS game_date_null_count
                        FROM matches
                        WHERE season = :season AND game_date IS NULL
                        """,
                        {"season": season},
                    )
                    or 0
                ),
                "home_team_id": int(
                    _scalar(
                        engine,
                        """
                        SELECT COUNT(*) AS home_team_id_null_count
                        FROM matches
                        WHERE season = :season AND home_team_id IS NULL
                        """,
                        {"season": season},
                    )
                    or 0
                ),
                "away_team_id": int(
                    _scalar(
                        engine,
                        """
                        SELECT COUNT(*) AS away_team_id_null_count
                        FROM matches
                        WHERE season = :season AND away_team_id IS NULL
                        """,
                        {"season": season},
                    )
                    or 0
                ),
                "points": int(
                    _scalar(
                        engine,
                        """
                        SELECT COUNT(*) AS points_null_count
                        FROM team_game_stats tgs
                        JOIN matches m ON m.game_id = tgs.game_id
                        WHERE m.season = :season AND tgs.points IS NULL
                        """,
                        {"season": season},
                    )
                    or 0
                ),
            }

            season_stats.append(
                {
                    "season": season,
                    "matches": matches_count,
                    "team_game_stats": team_stats_count,
                    "max_date": _iso_date(max_game_date),
                    "null_counts": null_counts,
                }
            )

            if matches_count < minimum_total_matches:
                failures.append(
                    {
                        "reason": "not_enough_matches",
                        "value": {"season": season, "matches": matches_count},
                    }
                )

            match_denominator = matches_count or 1
            team_stats_denominator = team_stats_count or 1
            null_rates = {
                "game_date": null_counts["game_date"] / match_denominator,
                "home_team_id": null_counts["home_team_id"] / match_denominator,
                "away_team_id": null_counts["away_team_id"] / match_denominator,
                "points": null_counts["points"] / team_stats_denominator,
            }
            for column, rate in null_rates.items():
                if rate > self.max_null_rate:
                    failures.append(
                        {
                            "reason": "critical_null_rate_exceeded",
                            "value": {
                                "season": season,
                                "column": column,
                                "null_rate": round(rate, 4),
                            },
                        }
                    )

            if max_game_date is None:
                failures.append(
                    {
                        "reason": "stale_or_missing_game_date",
                        "value": {"season": season, "max_date": None},
                    }
                )
            else:
                max_dt = max_game_date.date() if hasattr(max_game_date, "date") else max_game_date
                days_old = (today - max_dt).days
                if days_old > self.max_data_age_days:
                    failures.append(
                        {
                            "reason": "stale_game_data",
                            "value": {
                                "season": season,
                                "max_date": _iso_date(max_game_date),
                                "days_old": days_old,
                            },
                        }
                    )

        if failures:
            raise ValueError(f"Raw data validation failed: {failures[0]['reason']}")

        return {
            "validation": "passed",
            "matches": sum(item["matches"] for item in season_stats),
            "team_game_stats": sum(item["team_game_stats"] for item in season_stats),
            "max_date": max(
                (item["max_date"] for item in season_stats if item["max_date"]),
                default=None,
            ),
            "seasons": seasons,
        }


@dataclass
class FeatureContract:
    """What the feature pipeline guarantees to the prediction pipeline."""

    required_feature_columns: list[str] = field(
        default_factory=lambda: list(FEATURE_COLUMNS)
    )
    max_null_rate_features: float = 0.05
    min_feature_rows_per_match: int = 2

    def validate_required_columns(self, actual_columns: Sequence[str]) -> None:
        missing = [col for col in self.required_feature_columns if col not in _as_set(actual_columns)]
        if missing:
            raise ValueError(f"Missing required feature columns: {', '.join(missing)}")

    def validate_feature_output(
        self,
        engine,
        seasons: Sequence[str],
        *,
        expected_match_count: int,
    ) -> dict:
        """Validate the materialized feature table after computation."""
        seasons = list(seasons) or []
        if not seasons:
            raise ValueError("At least one season is required for feature validation")

        expected_rows = expected_match_count * self.min_feature_rows_per_match
        season_stats: list[dict] = []
        failures: list[dict] = []

        for season in seasons:
            feature_rows = int(
                _scalar(
                    engine,
                    """
                    SELECT COUNT(*) AS feature_rows
                    FROM match_features mf
                    JOIN matches m ON m.game_id = mf.game_id
                    WHERE m.season = :season
                    """,
                    {"season": season},
                )
                or 0
            )

            null_rates: dict[str, float] = {}
            for column in self.required_feature_columns:
                null_count = int(
                    _scalar(
                        engine,
                        f"""
                        SELECT COUNT(*) AS {column}_null_count
                        FROM match_features mf
                        JOIN matches m ON m.game_id = mf.game_id
                        WHERE m.season = :season AND mf.{column} IS NULL
                        """,
                        {"season": season},
                    )
                    or 0
                )
                null_rates[column] = null_count / (feature_rows or 1)
                if null_rates[column] > self.max_null_rate_features:
                    failures.append(
                        {
                            "reason": "feature_null_rate_exceeded",
                            "value": {
                                "season": season,
                                "column": column,
                                "null_rate": round(null_rates[column], 4),
                            },
                        }
                    )

            season_stats.append(
                {
                    "season": season,
                    "feature_rows": feature_rows,
                    "expected_feature_rows": expected_rows,
                    "null_rates": null_rates,
                }
            )

            if feature_rows < expected_rows:
                failures.append(
                    {
                        "reason": "feature_row_count_too_low",
                        "value": {
                            "season": season,
                            "feature_rows": feature_rows,
                            "expected_feature_rows": expected_rows,
                        },
                    }
                )

        if failures:
            raise ValueError(f"Feature output validation failed: {failures[0]['reason']}")

        return {
            "validation": "passed",
            "feature_rows": sum(item["feature_rows"] for item in season_stats),
            "expected_feature_rows": expected_rows,
            "seasons": seasons,
        }
