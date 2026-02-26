"""
Tests for the Kelly Criterion bet sizing module.

These tests verify the core mathematical logic without needing
a database or API connection — pure unit tests.
"""
import pytest
from src.models.bet_sizing import (
    american_to_decimal,
    decimal_to_implied_probability,
    kelly_criterion,
    calculate_bet_amount,
)


class TestOddsConversion:
    """Tests for odds format conversion."""

    def test_positive_american_to_decimal(self):
        """Plus odds: +150 → 2.50"""
        assert american_to_decimal(150) == 2.50

    def test_negative_american_to_decimal(self):
        """Minus odds: -200 → 1.50"""
        assert american_to_decimal(-200) == 1.50

    def test_even_odds(self):
        """+100 → 2.00 (even money)"""
        assert american_to_decimal(100) == 2.00

    def test_heavy_favorite(self):
        """-500 → 1.20"""
        assert american_to_decimal(-500) == 1.20

    def test_decimal_to_probability(self):
        """2.00 → 50% implied probability"""
        assert decimal_to_implied_probability(2.0) == 0.5

    def test_decimal_to_probability_favorite(self):
        """1.50 → 66.7% implied"""
        result = decimal_to_implied_probability(1.5)
        assert abs(result - 0.6667) < 0.001


class TestKellyCriterion:
    """Tests for the Kelly Criterion calculation."""

    def test_positive_edge_returns_bet(self, sample_kelly_inputs):
        """When we have an edge, Kelly says BET."""
        result = kelly_criterion(**sample_kelly_inputs["high_edge"])
        assert result["recommendation"] == "BET"
        assert result["edge"] > 0
        assert result["recommended_fraction"] > 0

    def test_no_edge_returns_no_bet(self, sample_kelly_inputs):
        """When model prob < implied prob, don't bet."""
        result = kelly_criterion(**sample_kelly_inputs["no_edge"])
        assert result["recommendation"] == "NO_BET"
        assert result["recommended_fraction"] == 0

    def test_negative_ev_returns_no_bet(self, sample_kelly_inputs):
        """Strong negative EV → definitely no bet."""
        result = kelly_criterion(**sample_kelly_inputs["negative_ev"])
        assert result["recommendation"] == "NO_BET"

    def test_max_bet_fraction_capped(self, sample_kelly_inputs):
        """Even with huge edge, bet should be capped at MAX_BET_FRACTION."""
        result = kelly_criterion(**sample_kelly_inputs["huge_edge"])
        assert result["recommended_fraction"] <= 0.10

    def test_kelly_fraction_reduces_bet(self):
        """Quarter Kelly should give ~25% of full Kelly."""
        full = kelly_criterion(0.65, 2.0, kelly_fraction=1.0)
        quarter = kelly_criterion(0.65, 2.0, kelly_fraction=0.25)
        if full["full_kelly_fraction"] > 0:
            assert quarter["recommended_fraction"] < full["recommended_fraction"]

    def test_result_contains_required_fields(self, sample_kelly_inputs):
        """Verify all expected keys are in the result dict."""
        result = kelly_criterion(**sample_kelly_inputs["high_edge"])
        required_keys = [
            "recommendation", "reason", "model_probability",
            "implied_probability", "edge", "full_kelly_fraction",
            "recommended_fraction", "kelly_type", "decimal_odds",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"


class TestBetAmountCalculation:
    """Tests for dollar-amount bet sizing."""

    def test_bet_amount_with_edge(self):
        """Should return positive bet amount when there's an edge."""
        result = calculate_bet_amount(
            bankroll=1000, model_prob=0.65, decimal_odds=2.0
        )
        assert result["bet_amount"] > 0
        assert result["bankroll"] == 1000

    def test_no_bet_returns_zero_amount(self):
        """Should return $0 bet when no edge."""
        result = calculate_bet_amount(
            bankroll=1000, model_prob=0.40, decimal_odds=2.0
        )
        assert result["bet_amount"] == 0
        assert result["potential_profit"] == 0

    def test_potential_profit_calculation(self):
        """Profit = bet_amount * (odds - 1)."""
        result = calculate_bet_amount(
            bankroll=1000, model_prob=0.65, decimal_odds=2.0
        )
        if result["bet_amount"] > 0:
            expected_profit = round(result["bet_amount"] * (2.0 - 1), 2)
            assert result["potential_profit"] == expected_profit

    def test_expected_value_positive(self):
        """When we bet with an edge, EV should be positive."""
        result = calculate_bet_amount(
            bankroll=1000, model_prob=0.65, decimal_odds=2.0
        )
        if result["recommendation"] == "BET":
            assert result["expected_value"] > 0
