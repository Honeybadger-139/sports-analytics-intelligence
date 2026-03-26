"""
Bayesian Team Strength Ratings using game outcomes.

WHY BAYESIAN RATINGS?
----------------------
Classical win-rate (wins / total games) has a fundamental problem: it treats
all wins equally. Beating the 15-50 Pistons counts the same as beating the
58-10 Celtics.

Bayesian approach (inspired by Elo, TrueSkill, and Bradley-Terry models):
  - Each team has a latent "strength" parameter α_i
  - The probability that team i beats team j is: P(i beats j) = σ(α_i - α_j)
    where σ is the sigmoid function
  - We fit these parameters to maximise the likelihood of observed outcomes

This is the foundation of systems like Elo (chess), Glicko (chess with uncertainty),
TrueSkill (Xbox matchmaking), and FiveThirtyEight's NBA Elo ratings.

APPROACH COMPARISON:
  A. Win rate ranking (simple, biased by schedule)          → ❌ naive
  B. Point differential ranking (better, still schedule-biased) → ✅ ok
  C. Elo (online Bayesian update, no uncertainty estimate) → ✅ good
  D. Bradley-Terry MLE (our approach) → ✅ good, interpretable, fast
  E. Full Bayesian with PyMC (posterior uncertainty) → ✅ best, slower

Choice: D for production (fast, no heavy dependencies), E documented for interviews.

INTERVIEW ANGLE:
  Junior:  "I ranked teams by win percentage"
  Senior:  "I use a Bradley-Terry model — a pairwise comparison model that
            infers latent team strengths from game outcomes. P(i beats j) = σ(α_i - α_j).
            This accounts for schedule strength: a team with α=2.5 is predicted to
            beat a team with α=1.0 about 82% of the time."

  Awe moment: "The Bradley-Terry parameters have a natural interpretation:
               a difference of 1.0 in strength corresponds to ~73% win probability.
               The Golden State Warriors in 2015-16 had α ≈ 3.1 — meaning they
               were predicted to beat an average team (α=0) about 96% of the time."

Part of: SCR-320 — Module 6.4 Statistics
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Bradley-Terry Model (MLE, no heavy deps) ──────────────────────────────────


class BradleyTerryRatings:
    """
    Bayesian team strength ratings via Bradley-Terry maximum likelihood estimation.

    The model: P(team_i beats team_j) = σ(α_i - α_j) = 1 / (1 + exp(-(α_i - α_j)))

    We fit {α_i} by gradient ascent on the log-likelihood of observed outcomes.
    Regularisation (L2 on α_i) keeps strengths near zero for teams with few games.

    Usage:
        ratings = BradleyTerryRatings()
        ratings.fit(game_results)  # list of (team_i, team_j, i_won) tuples
        rankings = ratings.get_rankings()
    """

    def __init__(
        self,
        learning_rate: float = 0.1,
        n_iterations: int = 1000,
        l2_reg: float = 0.01,
        convergence_tol: float = 1e-6,
    ) -> None:
        self.lr = learning_rate
        self.n_iter = n_iterations
        self.l2_reg = l2_reg
        self.tol = convergence_tol
        self.alphas: Dict[str, float] = {}
        self._teams: List[str] = []
        self.is_fitted = False
        self.training_log_likelihood: float = 0.0

    def fit(self, game_results: List[Tuple[str, str, bool]]) -> "BradleyTerryRatings":
        """
        Fit team strength parameters from game outcomes.

        Args:
            game_results: List of (home_team, away_team, home_won) tuples.
                          home_won=True means home team won.

        Returns:
            self (for method chaining)
        """
        if not game_results:
            logger.warning("BradleyTerryRatings: no game results provided")
            return self

        # Initialise teams at zero strength
        teams = set()
        for home, away, _ in game_results:
            teams.update([home, away])
        self._teams = sorted(teams)
        self.alphas = {team: 0.0 for team in self._teams}

        # Gradient ascent on log-likelihood
        prev_ll = -float("inf")
        for iteration in range(self.n_iter):
            gradients = {team: 0.0 for team in self._teams}
            log_likelihood = 0.0

            for home_team, away_team, home_won in game_results:
                alpha_h = self.alphas[home_team]
                alpha_a = self.alphas[away_team]

                # P(home wins) = σ(α_home - α_away)
                diff = alpha_h - alpha_a
                p_home = 1.0 / (1.0 + math.exp(-diff))
                p_away = 1.0 - p_home

                outcome = 1.0 if home_won else 0.0
                # Log-likelihood contribution
                eps = 1e-10
                log_likelihood += outcome * math.log(p_home + eps) + (1 - outcome) * math.log(p_away + eps)

                # Gradients (score function)
                grad = outcome - p_home
                gradients[home_team] += grad
                gradients[away_team] -= grad

            # L2 regularisation (pushes α_i toward 0)
            log_likelihood -= self.l2_reg * sum(a**2 for a in self.alphas.values())
            for team in self._teams:
                gradients[team] -= 2 * self.l2_reg * self.alphas[team]

            # Gradient ascent step
            for team in self._teams:
                self.alphas[team] += self.lr * gradients[team]

            # Convergence check
            if abs(log_likelihood - prev_ll) < self.tol:
                logger.debug("BradleyTerry converged at iteration %d", iteration)
                break
            prev_ll = log_likelihood

        self.training_log_likelihood = prev_ll
        self.is_fitted = True
        logger.info(
            "BradleyTerry fitted: %d teams, %d games, final LL=%.3f",
            len(self._teams), len(game_results), self.training_log_likelihood,
        )
        return self

    def predict_win_probability(self, team_i: str, team_j: str) -> float:
        """
        Predict P(team_i beats team_j) using fitted strength parameters.

        Returns probability in [0.0, 1.0].
        """
        if not self.is_fitted:
            return 0.5
        alpha_i = self.alphas.get(team_i, 0.0)
        alpha_j = self.alphas.get(team_j, 0.0)
        return 1.0 / (1.0 + math.exp(-(alpha_i - alpha_j)))

    def get_rankings(self, top_n: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Return teams ranked by strength parameter (highest to lowest).

        Includes win probability against a hypothetical "average" team (α=0).
        """
        if not self.is_fitted:
            return []

        rankings = []
        for rank, (team, alpha) in enumerate(
            sorted(self.alphas.items(), key=lambda x: x[1], reverse=True), start=1
        ):
            p_vs_average = 1.0 / (1.0 + math.exp(-alpha))
            rankings.append({
                "rank": rank,
                "team": team,
                "strength": round(alpha, 4),
                "win_vs_average_team": round(p_vs_average, 3),
                "tier": self._classify_tier(p_vs_average),
            })

        return rankings[:top_n] if top_n else rankings

    def get_strength(self, team: str) -> float:
        """Return the fitted strength parameter for a team."""
        return self.alphas.get(team, 0.0)

    def strength_summary(self) -> Dict[str, Any]:
        """Statistical summary of the strength distribution."""
        if not self.alphas:
            return {}
        values = list(self.alphas.values())
        return {
            "mean": round(float(np.mean(values)), 4),
            "std": round(float(np.std(values)), 4),
            "max": round(float(max(values)), 4),
            "min": round(float(min(values)), 4),
            "strongest_team": max(self.alphas, key=self.alphas.get),
            "weakest_team": min(self.alphas, key=self.alphas.get),
            "n_teams": len(self.alphas),
            "training_log_likelihood": round(self.training_log_likelihood, 3),
        }

    @staticmethod
    def _classify_tier(p_vs_average: float) -> str:
        """Classify a team's tier based on win probability against an average team."""
        if p_vs_average >= 0.75:
            return "elite"
        if p_vs_average >= 0.60:
            return "contender"
        if p_vs_average >= 0.45:
            return "average"
        if p_vs_average >= 0.30:
            return "rebuilding"
        return "lottery"


# ── Database integration ──────────────────────────────────────────────────────


def load_ratings_from_db(db_session: Any, season: str = "2025-26") -> BradleyTerryRatings:
    """
    Load game outcomes from PostgreSQL and fit Bradley-Terry ratings.

    Args:
        db_session: SQLAlchemy Session
        season: Season string to filter games

    Returns:
        Fitted BradleyTerryRatings instance
    """
    try:
        from sqlalchemy import text

        rows = db_session.execute(
            text(
                """
                SELECT
                    home_t.team_name AS home_team,
                    away_t.team_name AS away_team,
                    (m.winner_team_id = m.home_team_id) AS home_won
                FROM matches m
                JOIN teams home_t ON m.home_team_id = home_t.team_id
                JOIN teams away_t ON m.away_team_id = away_t.team_id
                WHERE m.is_completed = TRUE
                  AND m.season = :season
                ORDER BY m.game_date ASC
                """
            ),
            {"season": season},
        ).fetchall()

        game_results = [(row[0], row[1], bool(row[2])) for row in rows]
        logger.info("Loaded %d games for Bayesian ratings (season=%s)", len(game_results), season)

        ratings = BradleyTerryRatings()
        if game_results:
            ratings.fit(game_results)
        return ratings

    except Exception as exc:
        logger.warning("Could not load ratings from DB: %s", exc)
        return BradleyTerryRatings()
