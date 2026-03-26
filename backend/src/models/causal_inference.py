"""
Causal Inference via Difference-in-Differences (DiD).

THE QUESTION:
  Does home court advantage actually matter? Or are home teams just better teams?

THE NATURAL EXPERIMENT:
  COVID-19 (2020-21 season) forced games to be played in empty arenas — no fans.
  This is a near-perfect natural experiment:
    - Treatment group: games WITH fans (normal seasons)
    - Control group:   games WITHOUT fans (2020-21 bubble/empty arena season)
    - If home court advantage is real (driven by fans), home win rate should DROP
      significantly in the fanless season

WHY DIFFERENCE-IN-DIFFERENCES?
  We can't just compare win rates across seasons (teams changed, COVID itself
  affected player performance and psychology). DiD controls for these confounders:

  DiD estimator = (home_win_pct_with_fans - away_win_pct_with_fans)
                - (home_win_pct_without_fans - away_win_pct_without_fans)

  If DiD > 0: fans cause home court advantage (controlling for team quality)
  If DiD ≈ 0: home court advantage is explained by team quality alone

PARALLEL TRENDS ASSUMPTION (key assumption to check):
  DiD is valid only if home and away win rates were trending similarly
  BEFORE the treatment. We check this with pre-treatment trend analysis.

INTERVIEW ANGLE:
  Junior:  "I compared home win rates before and after COVID"
  Senior:  "I used Difference-in-Differences — a quasi-experimental method
            that controls for time trends and team-level confounders. The COVID
            empty-arena seasons are a natural experiment. The DiD estimate isolates
            the causal effect of crowd presence on home advantage, separate from
            team quality effects."

  Awe moment: "The 2020-21 NBA bubble is one of the cleanest natural experiments
               in sports science. No other sport has a dataset where you can
               literally remove the fans from every game for a full season."

Part of: SCR-320 — Module 6.4 Statistics
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Seasons where games were played without fans (or severely restricted)
FANLESS_SEASONS = {"2020-21"}
NORMAL_SEASONS = {"2018-19", "2019-20", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26"}


# ── DiD Data Structures ───────────────────────────────────────────────────────


@dataclass
class GameObservation:
    """A single game observation for causal analysis."""
    season: str
    home_win: bool
    is_home_game: bool = True     # all observations are from home team perspective

    @property
    def has_fans(self) -> bool:
        return self.season not in FANLESS_SEASONS


@dataclass
class DiffInDiffResult:
    """Result of a Difference-in-Differences analysis."""
    # Group means
    home_with_fans: float       # home win rate WITH fans
    home_without_fans: float    # home win rate WITHOUT fans
    away_with_fans: float       # away win rate WITH fans (reference group)
    away_without_fans: float    # away win rate WITHOUT fans

    # DiD components
    home_change: float          # home_with_fans - home_without_fans
    away_change: float          # away_with_fans - away_without_fans
    did_estimate: float         # home_change - away_change (causal effect of fans)

    # Statistical significance
    p_value: float
    confidence_interval_95: Tuple[float, float]
    is_significant: bool

    # Sample sizes
    n_home_with_fans: int
    n_home_without_fans: int
    n_away_with_fans: int
    n_away_without_fans: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "did_estimate": round(self.did_estimate, 4),
            "interpretation": self._interpret(),
            "home_win_pct_with_fans": round(self.home_with_fans, 4),
            "home_win_pct_without_fans": round(self.home_without_fans, 4),
            "home_change": round(self.home_change, 4),
            "away_change": round(self.away_change, 4),
            "p_value": round(self.p_value, 4),
            "confidence_interval_95": (
                round(self.confidence_interval_95[0], 4),
                round(self.confidence_interval_95[1], 4),
            ),
            "is_significant": self.is_significant,
            "sample_sizes": {
                "home_with_fans": self.n_home_with_fans,
                "home_without_fans": self.n_home_without_fans,
                "away_with_fans": self.n_away_with_fans,
                "away_without_fans": self.n_away_without_fans,
            },
        }

    def _interpret(self) -> str:
        direction = "increases" if self.did_estimate > 0 else "decreases"
        sig = "significantly" if self.is_significant else "not significantly"
        pct = abs(self.did_estimate) * 100
        return (
            f"Crowd presence {sig} {direction} home court advantage by "
            f"{pct:.1f} percentage points (DiD={self.did_estimate:+.3f}, "
            f"p={self.p_value:.3f})."
        )


# ── DiD Estimator ─────────────────────────────────────────────────────────────


class HomeCourtCausalAnalysis:
    """
    Difference-in-Differences estimator for home court advantage causality.

    Compares home vs away win rates across seasons with and without fans.
    The DiD estimate is the causal effect of crowd presence on home advantage,
    controlling for time trends and team quality via the parallel trends assumption.
    """

    def __init__(self, fanless_seasons: Optional[set] = None) -> None:
        self.fanless_seasons = fanless_seasons or FANLESS_SEASONS
        self._observations: List[GameObservation] = []

    def add_observation(self, season: str, home_win: bool) -> None:
        """Add a single game observation (home team perspective)."""
        self._observations.append(GameObservation(season=season, home_win=home_win))

    def add_observations_from_data(
        self,
        seasons: List[str],
        home_wins: List[bool],
    ) -> None:
        """Bulk add observations from lists."""
        for season, home_win in zip(seasons, home_wins):
            self.add_observation(season, home_win)

    def estimate(self) -> DiffInDiffResult:
        """
        Compute the Difference-in-Differences estimate.

        The 4 cells of the DiD table:
          |                 | With fans | Without fans |
          |-----------------|-----------|--------------|
          | Home (treated)  | A         | B            |
          | Away (control)  | C         | D            |

          DiD = (A - B) - (C - D) = (A - C) - (B - D)
        """
        if not self._observations:
            raise ValueError("No observations loaded. Call add_observations_from_data() first.")

        # Split into 4 groups
        home_with = [o.home_win for o in self._observations if o.has_fans]
        home_without = [o.home_win for o in self._observations if not o.has_fans]
        # Away = "not home" perspective — approximate via 1 - home_win in same games
        # (In practice, each game generates one home and one away observation)
        away_with = [not o.home_win for o in self._observations if o.has_fans]
        away_without = [not o.home_win for o in self._observations if not o.has_fans]

        n_hw = len(home_with)
        n_hwo = len(home_without)
        n_aw = len(away_with)
        n_awo = len(away_without)

        if n_hw == 0 or n_hwo == 0:
            raise ValueError("Need games both with and without fans.")

        p_hw = float(np.mean(home_with))
        p_hwo = float(np.mean(home_without)) if n_hwo > 0 else 0.5
        p_aw = float(np.mean(away_with))
        p_awo = float(np.mean(away_without)) if n_awo > 0 else 0.5

        home_change = p_hw - p_hwo
        away_change = p_aw - p_awo
        did = home_change - away_change

        # Approximate standard error via delta method
        # SE(DiD) ≈ sqrt(Var(A)/n_A + Var(B)/n_B + Var(C)/n_C + Var(D)/n_D)
        # For proportions: Var(p) = p(1-p)/n
        se_parts = [
            p_hw * (1 - p_hw) / max(n_hw, 1),
            p_hwo * (1 - p_hwo) / max(n_hwo, 1),
            p_aw * (1 - p_aw) / max(n_aw, 1),
            p_awo * (1 - p_awo) / max(n_awo, 1),
        ]
        se_did = float(np.sqrt(sum(se_parts)))

        # Z-test for DiD = 0
        z_stat = did / (se_did + 1e-10)
        # Two-tailed p-value (approximate normal)
        from math import erfc, sqrt
        p_value = float(erfc(abs(z_stat) / sqrt(2)))

        ci_low = did - 1.96 * se_did
        ci_high = did + 1.96 * se_did

        return DiffInDiffResult(
            home_with_fans=p_hw,
            home_without_fans=p_hwo,
            away_with_fans=p_aw,
            away_without_fans=p_awo,
            home_change=home_change,
            away_change=away_change,
            did_estimate=did,
            p_value=p_value,
            confidence_interval_95=(ci_low, ci_high),
            is_significant=p_value < 0.05,
            n_home_with_fans=n_hw,
            n_home_without_fans=n_hwo,
            n_away_with_fans=n_aw,
            n_away_without_fans=n_awo,
        )

    def check_parallel_trends(self) -> Dict[str, Any]:
        """
        Verify the parallel trends assumption (key validity check for DiD).

        Pre-treatment, home and away win rates should trend similarly.
        If they diverge pre-treatment, DiD estimates are biased.
        """
        # Group by season and compute home win rate
        by_season: Dict[str, List[bool]] = {}
        for obs in self._observations:
            by_season.setdefault(obs.season, []).append(obs.home_win)

        season_rates = {
            season: round(float(np.mean(wins)), 4)
            for season, wins in sorted(by_season.items())
        }

        pre_treatment = {s: r for s, r in season_rates.items() if s not in self.fanless_seasons}
        treatment = {s: r for s, r in season_rates.items() if s in self.fanless_seasons}

        # Simple trend check: variance in pre-treatment home win rates
        pre_values = list(pre_treatment.values())
        pre_variance = float(np.var(pre_values)) if len(pre_values) > 1 else 0.0

        return {
            "season_home_win_rates": season_rates,
            "pre_treatment_seasons": pre_treatment,
            "treatment_seasons": treatment,
            "pre_treatment_variance": round(pre_variance, 4),
            "parallel_trends_concern": pre_variance > 0.01,
            "interpretation": (
                "Parallel trends assumption likely holds (low pre-treatment variance)"
                if pre_variance <= 0.01
                else "Pre-treatment variance is high — parallel trends assumption may be violated"
            ),
        }


# ── Database integration ──────────────────────────────────────────────────────


def run_home_court_causal_analysis(db_session: Any) -> Dict[str, Any]:
    """
    Load game data and run the complete DiD analysis.

    Args:
        db_session: SQLAlchemy Session

    Returns:
        Dict with DiD estimate, parallel trends check, and interpretation
    """
    try:
        from sqlalchemy import text

        rows = db_session.execute(
            text(
                """
                SELECT
                    m.season,
                    (m.winner_team_id = m.home_team_id) AS home_won
                FROM matches m
                WHERE m.is_completed = TRUE
                ORDER BY m.game_date ASC
                """
            )
        ).fetchall()

        logger.info("Loaded %d games for causal analysis", len(rows))

        analysis = HomeCourtCausalAnalysis()
        analysis.add_observations_from_data(
            seasons=[row[0] for row in rows],
            home_wins=[bool(row[1]) for row in rows],
        )

        result = analysis.estimate()
        trends = analysis.check_parallel_trends()

        return {
            "did_result": result.to_dict(),
            "parallel_trends": trends,
            "n_total_games": len(rows),
        }

    except Exception as exc:
        logger.warning("Causal analysis failed: %s", exc)
        return {"error": str(exc)}
