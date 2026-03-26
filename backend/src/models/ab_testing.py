"""
Sequential A/B Testing with SPRT for NBA model comparison.

WHY SPRT INSTEAD OF CLASSICAL T-TEST?
---------------------------------------
Classical A/B testing (t-test, chi-squared) requires a fixed sample size
chosen before the experiment. In ML model evaluation, we don't know
upfront how many games we need to see before concluding one model is better.

SPRT (Sequential Probability Ratio Test — Wald, 1945) solves this:
  - Test after EVERY new observation
  - Stop as soon as the evidence is strong enough (either direction)
  - Control false positive rate (α) and false negative rate (β) simultaneously
  - On average, requires 50-70% fewer samples than fixed-size tests

REAL-WORLD ANALOGY:
  Classical A/B: "Watch 100 games, then decide"
  SPRT:          "Watch games one by one; stop when you're confident enough"

APPLICATION HERE:
  We use SPRT to compare model versions:
    - Is PyTorch MLP significantly better/worse than XGBoost?
    - Does calibration improve actual prediction accuracy?
    - Did the new feature set improve predictions on 2025-26 games?

INTERVIEW ANGLE:
  Junior:  "I split the data 80/20 and compared accuracy"
  Senior:  "I used SPRT so I could continuously monitor model performance
            and stop the comparison as soon as I had enough evidence, rather
            than waiting for an arbitrary fixed sample size. This saved
            ~60% of the evaluation time while controlling both Type I and II
            errors at 5%."

  Awe moment: "SPRT is the same technique used in clinical trials to stop
               early when a treatment is clearly working or harmful. We're
               applying the same rigour to model evaluation."

Part of: SCR-320 — Module 6.4 Statistics
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ── SPRT Core ─────────────────────────────────────────────────────────────────


@dataclass
class SPRTConfig:
    """Configuration for a Sequential Probability Ratio Test."""
    alpha: float = 0.05     # Type I error rate (false positive — conclude A≠B when A=B)
    beta: float = 0.05      # Type II error rate (false negative — miss a real difference)
    p0: float = 0.5         # Null hypothesis: proportion of correct predictions (baseline)
    p1: float = 0.55        # Alternative hypothesis: minimum detectable effect

    def __post_init__(self):
        if not 0 < self.alpha < 1:
            raise ValueError(f"alpha must be in (0,1), got {self.alpha}")
        if not 0 < self.beta < 1:
            raise ValueError(f"beta must be in (0,1), got {self.beta}")
        if self.p1 <= self.p0:
            raise ValueError(f"p1 must be > p0: p0={self.p0}, p1={self.p1}")

    @property
    def lower_boundary(self) -> float:
        """Log-likelihood ratio lower boundary (accept H0: models are equal)."""
        return math.log(self.beta / (1 - self.alpha))

    @property
    def upper_boundary(self) -> float:
        """Log-likelihood ratio upper boundary (accept H1: model A is better)."""
        return math.log((1 - self.beta) / self.alpha)


@dataclass
class SPRTResult:
    """Result of a sequential test at a given point in time."""
    n_observations: int
    log_likelihood_ratio: float
    decision: str           # 'continue' | 'accept_h0' | 'accept_h1'
    model_a_correct: int
    model_b_correct: int
    model_a_accuracy: float
    model_b_accuracy: float
    is_significant: bool
    winner: Optional[str]   # 'model_a' | 'model_b' | None
    p_value_estimate: float
    lower_boundary: float
    upper_boundary: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_observations": self.n_observations,
            "log_likelihood_ratio": round(self.log_likelihood_ratio, 4),
            "decision": self.decision,
            "model_a_accuracy": round(self.model_a_accuracy, 4),
            "model_b_accuracy": round(self.model_b_accuracy, 4),
            "is_significant": self.is_significant,
            "winner": self.winner,
            "p_value_estimate": round(self.p_value_estimate, 4),
        }


class SPRTModelComparison:
    """
    Sequential Probability Ratio Test for comparing two NBA prediction models.

    Usage:
        sprt = SPRTModelComparison(model_a_name="XGBoost", model_b_name="PyTorch_MLP")
        for game in games:
            result = sprt.update(
                model_a_correct=xgb_pred == actual,
                model_b_correct=mlp_pred == actual,
            )
            if result.decision != 'continue':
                print(f"Stopping: {result.winner} is better")
                break
    """

    def __init__(
        self,
        model_a_name: str = "model_a",
        model_b_name: str = "model_b",
        config: Optional[SPRTConfig] = None,
    ) -> None:
        self.model_a_name = model_a_name
        self.model_b_name = model_b_name
        self.config = config or SPRTConfig()

        # Running counts
        self._n = 0
        self._a_correct = 0
        self._b_correct = 0
        self._llr = 0.0         # cumulative log-likelihood ratio
        self.history: List[SPRTResult] = []

    def update(self, model_a_correct: bool, model_b_correct: bool) -> SPRTResult:
        """
        Update the test with one new observation (one game).

        The log-likelihood ratio accumulates after each game:
          - Model A right, Model B wrong → evidence FOR H1 (A is better)
          - Model A wrong, Model B right → evidence AGAINST H1
          - Both right or both wrong → no information

        Returns a result with the current decision.
        """
        self._n += 1
        self._a_correct += int(model_a_correct)
        self._b_correct += int(model_b_correct)

        # Update log-likelihood ratio
        # H0: both models are equally accurate (p = p0)
        # H1: model A is more accurate (p_A = p1, p_B stays at p0)
        p0 = self.config.p0
        p1 = self.config.p1

        if model_a_correct and not model_b_correct:
            # A right, B wrong: strongest evidence for H1
            llr_increment = math.log(p1 / p0) - math.log((1 - p1) / (1 - p0))
        elif not model_a_correct and model_b_correct:
            # A wrong, B right: evidence against H1
            llr_increment = math.log((1 - p1) / (1 - p0)) - math.log(p1 / p0)
        else:
            # Both right or both wrong: no discriminating information
            llr_increment = 0.0

        self._llr += llr_increment

        # Determine decision
        lower = self.config.lower_boundary
        upper = self.config.upper_boundary

        if self._llr >= upper:
            decision = "accept_h1"
            winner = self.model_a_name
            is_significant = True
        elif self._llr <= lower:
            decision = "accept_h0"
            winner = None  # models are equivalent
            is_significant = True
        else:
            decision = "continue"
            winner = None
            is_significant = False

        # Approximate p-value from LLR (valid when n is large enough)
        # P(LLR >= observed | H0) ≈ e^(-llr) for one-sided test
        p_value = min(1.0, math.exp(-abs(self._llr)))

        result = SPRTResult(
            n_observations=self._n,
            log_likelihood_ratio=self._llr,
            decision=decision,
            model_a_correct=self._a_correct,
            model_b_correct=self._b_correct,
            model_a_accuracy=self._a_correct / self._n,
            model_b_accuracy=self._b_correct / self._n,
            is_significant=is_significant,
            winner=winner,
            p_value_estimate=p_value,
            lower_boundary=lower,
            upper_boundary=upper,
        )
        self.history.append(result)
        return result

    def run_comparison(
        self,
        model_a_preds: List[int],
        model_b_preds: List[int],
        actuals: List[int],
    ) -> SPRTResult:
        """
        Run the full SPRT on pre-collected predictions.

        Args:
            model_a_preds: List of 0/1 predictions from model A
            model_b_preds: List of 0/1 predictions from model B
            actuals: List of 0/1 ground truth labels

        Returns:
            Final SPRT result after processing all observations (or at stopping point)
        """
        if len(model_a_preds) != len(model_b_preds) != len(actuals):
            raise ValueError("All prediction lists must have the same length")

        last_result = None
        for a_pred, b_pred, actual in zip(model_a_preds, model_b_preds, actuals):
            a_correct = int(a_pred) == int(actual)
            b_correct = int(b_pred) == int(actual)
            last_result = self.update(a_correct, b_correct)

            # Early stopping when decision reached
            if last_result.decision != "continue":
                logger.info(
                    "SPRT stopped at n=%d: decision=%s winner=%s LLR=%.3f",
                    self._n, last_result.decision, last_result.winner, self._llr,
                )
                break

        return last_result

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict of the current test state."""
        last = self.history[-1] if self.history else None
        return {
            "model_a": self.model_a_name,
            "model_b": self.model_b_name,
            "n_observations": self._n,
            "model_a_accuracy": round(self._a_correct / max(self._n, 1), 4),
            "model_b_accuracy": round(self._b_correct / max(self._n, 1), 4),
            "current_llr": round(self._llr, 4),
            "decision": last.decision if last else "not_started",
            "winner": last.winner if last else None,
            "is_significant": last.is_significant if last else False,
            "config": {
                "alpha": self.config.alpha,
                "beta": self.config.beta,
                "p0": self.config.p0,
                "p1": self.config.p1,
            },
        }


# ── Convenience functions ─────────────────────────────────────────────────────


def compare_models(
    model_a_name: str,
    model_b_name: str,
    model_a_preds: List[int],
    model_b_preds: List[int],
    actuals: List[int],
    alpha: float = 0.05,
    min_detectable_effect: float = 0.05,
) -> Dict[str, Any]:
    """
    Run a complete SPRT model comparison and return a results dict.

    Example:
        result = compare_models(
            "XGBoost", "PyTorch_MLP",
            xgb_predictions, mlp_predictions, actual_outcomes
        )
        print(f"Winner: {result['winner']} after {result['n_observations']} games")
    """
    config = SPRTConfig(alpha=alpha, beta=alpha, p1=0.5 + min_detectable_effect)
    sprt = SPRTModelComparison(
        model_a_name=model_a_name,
        model_b_name=model_b_name,
        config=config,
    )
    final = sprt.run_comparison(model_a_preds, model_b_preds, actuals)
    summary = sprt.summary()
    summary["final_result"] = final.to_dict() if final else {}
    return summary
