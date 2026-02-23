"""
Kelly Criterion Bet Sizing Module
==================================

🎓 WHAT IS THE KELLY CRITERION?
    The Kelly Criterion is a mathematical formula that tells you the
    OPTIMAL percentage of your bankroll to bet on each game.

    Formula: f* = (b*p - q) / b
    Where:
        f* = fraction of bankroll to bet
        b  = odds received (decimal odds - 1)
        p  = probability of winning (from our model)
        q  = probability of losing (1 - p)

    Example:
        Model says 60% chance Lakers win. Odds are +150 (2.50 decimal).
        f* = (1.5 * 0.60 - 0.40) / 1.5 = 0.333 → Bet 33% of bankroll

🧠 WHY KELLY CRITERION?
    - Maximizes long-term bankroll growth (geometric mean maximization)
    - Provides a mathematical framework for bet sizing
    - Accounts for both edge (probability) AND odds (payout)
    - Used by professional sports bettors, hedge funds, and poker pros

💡 INTERVIEW ANGLE:
    Junior: "I bet the same amount on every game"
    Senior: "I use the Kelly Criterion to size bets proportional to our
    model's edge relative to market odds. I also apply a fractional Kelly
    (1/4 to 1/2) to reduce variance, which is crucial because our model's
    probability estimates have uncertainty."

    Awe moment: "Kelly is the provably optimal strategy for long-term
    growth, but full Kelly has very high variance. I use quarter-Kelly
    because our probability estimates have ~3% calibration error, and
    full Kelly would overbet on those uncertain edges."

🧠 WHY FRACTIONAL KELLY?
    Full Kelly maximizes long-term growth but has HUGE variance:
    - 50% drawdowns are common with full Kelly
    - If your probabilities are even slightly miscalibrated, you overbid

    Professional bettors use 1/4 to 1/2 Kelly:
    - Quarter Kelly: 75% less variance, 50% of optimtal growth
    - Half Kelly: 50% less variance, 75% of optimal growth
"""

import logging
from typing import Dict, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Default Kelly fraction (quarter Kelly for safety)
DEFAULT_KELLY_FRACTION = 0.25

# Minimum edge to place a bet (don't bet on tiny edges)
MIN_EDGE = 0.02  # 2% minimum edge

# Maximum bet size as fraction of bankroll
MAX_BET_FRACTION = 0.10  # Never bet more than 10%


def american_to_decimal(american_odds: int) -> float:
    """
    Convert American odds to decimal odds.

    🎓 ODDS FORMATS:
        American: +150 means win $150 on $100 bet. -200 means bet $200 to win $100.
        Decimal: 2.50 means a $100 bet returns $250 (including stake).
        Implied probability from decimal: 1/decimal_odds
    """
    if american_odds > 0:
        return (american_odds / 100) + 1
    else:
        return (100 / abs(american_odds)) + 1


def decimal_to_implied_probability(decimal_odds: float) -> float:
    """Convert decimal odds to implied probability."""
    return 1 / decimal_odds


def kelly_criterion(
    model_prob: float,
    decimal_odds: float,
    kelly_fraction: float = DEFAULT_KELLY_FRACTION,
) -> Dict:
    """
    Calculate optimal bet size using Kelly Criterion.

    🎓 THE MATH:
        f* = (b*p - q) / b
        Where b = decimal_odds - 1 (net payout per unit bet)

        If f* < 0, the bet has negative expected value → DON'T BET.
        If f* > 0, we have an edge → bet f* fraction of bankroll.

    Args:
        model_prob: Our model's probability of this outcome winning
        decimal_odds: The odds being offered (decimal format)
        kelly_fraction: What fraction of Kelly to use (0.25 = quarter Kelly)

    Returns:
        Dict with bet recommendation
    """
    # Calculate implied probability from odds
    implied_prob = decimal_to_implied_probability(decimal_odds)

    # Net odds (b in Kelly formula)
    b = decimal_odds - 1

    # Kelly formula
    p = model_prob
    q = 1 - p
    full_kelly = (b * p - q) / b if b > 0 else 0

    # Apply fractional Kelly
    fractional_kelly = full_kelly * kelly_fraction

    # Calculate edge: how much better is our probability vs the market
    edge = model_prob - implied_prob

    # Determine recommendation
    if edge < MIN_EDGE:
        recommendation = "NO_BET"
        reason = f"Edge too small ({edge:.1%} < {MIN_EDGE:.1%})"
        bet_fraction = 0
    elif fractional_kelly <= 0:
        recommendation = "NO_BET"
        reason = "Negative expected value — the odds don't compensate for the risk"
        bet_fraction = 0
    else:
        bet_fraction = min(fractional_kelly, MAX_BET_FRACTION)
        recommendation = "BET"
        reason = f"Edge: {edge:.1%}, Kelly fraction: {bet_fraction:.1%}"

    return {
        "recommendation": recommendation,
        "reason": reason,
        "model_probability": round(model_prob, 4),
        "implied_probability": round(implied_prob, 4),
        "edge": round(edge, 4),
        "full_kelly_fraction": round(max(0, full_kelly), 4),
        "recommended_fraction": round(bet_fraction, 4),
        "kelly_type": f"{kelly_fraction:.0%} Kelly",
        "decimal_odds": decimal_odds,
    }


def calculate_bet_amount(
    bankroll: float,
    model_prob: float,
    decimal_odds: float,
    kelly_fraction: float = DEFAULT_KELLY_FRACTION,
) -> Dict:
    """
    Calculate the actual dollar amount to bet.

    Args:
        bankroll: Current bankroll amount
        model_prob: Model's probability
        decimal_odds: Odds offered
        kelly_fraction: Fraction of Kelly to use

    Returns:
        Dict with bet sizing recommendation including dollar amount
    """
    kelly_result = kelly_criterion(model_prob, decimal_odds, kelly_fraction)

    if kelly_result["recommendation"] == "BET":
        bet_amount = round(bankroll * kelly_result["recommended_fraction"], 2)
        potential_profit = round(bet_amount * (decimal_odds - 1), 2)
        expected_value = round(
            bet_amount * decimal_odds * model_prob - bet_amount, 2
        )
    else:
        bet_amount = 0
        potential_profit = 0
        expected_value = 0

    return {
        **kelly_result,
        "bankroll": bankroll,
        "bet_amount": bet_amount,
        "potential_profit": potential_profit,
        "potential_return": round(bet_amount * decimal_odds, 2),
        "expected_value": expected_value,
    }
