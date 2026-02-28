"""
Tests for bet ledger persistence utilities.
"""

from datetime import datetime
from decimal import Decimal

from src.data import bet_store


class _Result:
    def __init__(self, *, fetchone_value=None):
        self._fetchone_value = fetchone_value

    def fetchone(self):
        return self._fetchone_value


class _Row:
    def __init__(self, mapping):
        self._mapping = mapping


class _SettleSelectRow:
    def __init__(self, stake, odds, result):
        self.stake = stake
        self.odds = odds
        self.result = result


class _SummaryRow:
    def __init__(
        self,
        *,
        total_bets,
        settled_bets,
        open_bets,
        total_stake,
        settled_stake,
        total_pnl,
    ):
        self.total_bets = total_bets
        self.settled_bets = settled_bets
        self.open_bets = open_bets
        self.total_stake = total_stake
        self.settled_stake = settled_stake
        self.total_pnl = total_pnl


class _CreateSession:
    def __init__(self):
        self.insert_attempts = 0
        self.commits = 0
        self.rollbacks = 0
        self.queries = []

    def execute(self, query, _params=None):
        q = str(query)
        self.queries.append(q)
        if "INSERT INTO bets" in q:
            self.insert_attempts += 1
            if self.insert_attempts == 1:
                raise RuntimeError('relation "bets" does not exist')
            row = _Row(
                {
                    "id": 101,
                    "game_id": "001",
                    "bet_type": "match_winner",
                    "selection": "LAL",
                    "odds": Decimal("1.9100"),
                    "stake": Decimal("50.00"),
                    "kelly_fraction": Decimal("0.2500"),
                    "model_probability": Decimal("0.5700"),
                    "result": "pending",
                    "pnl": None,
                    "placed_at": datetime(2026, 2, 28, 10, 0, 0),
                    "settled_at": None,
                }
            )
            return _Result(fetchone_value=row)
        return _Result(fetchone_value=None)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _SettleSession:
    def __init__(self):
        self.commits = 0

    def execute(self, query, params=None):
        q = str(query)
        if "SELECT stake, odds, result" in q:
            return _Result(
                fetchone_value=_SettleSelectRow(
                    stake=Decimal("50.00"),
                    odds=Decimal("2.5000"),
                    result="pending",
                )
            )
        if "UPDATE bets" in q:
            row = _Row(
                {
                    "id": params["bet_id"],
                    "game_id": "001",
                    "bet_type": "match_winner",
                    "selection": "LAL",
                    "odds": Decimal("2.5000"),
                    "stake": Decimal("50.00"),
                    "kelly_fraction": Decimal("0.2500"),
                    "model_probability": Decimal("0.6000"),
                    "result": params["result"],
                    "pnl": params["pnl"],
                    "placed_at": datetime(2026, 2, 28, 10, 0, 0),
                    "settled_at": params["settled_at"],
                }
            )
            return _Result(fetchone_value=row)
        return _Result(fetchone_value=None)

    def commit(self):
        self.commits += 1


class _SummarySession:
    def execute(self, _query, _params=None):
        return _Result(
            fetchone_value=_SummaryRow(
                total_bets=10,
                settled_bets=7,
                open_bets=3,
                total_stake=Decimal("1000.00"),
                settled_stake=Decimal("700.00"),
                total_pnl=Decimal("84.50"),
            )
        )


def test_create_bet_bootstraps_missing_table():
    db = _CreateSession()
    item = bet_store.create_bet(
        db,
        game_id="001",
        bet_type="match_winner",
        selection="LAL",
        odds=1.91,
        stake=50.0,
        kelly_fraction=0.25,
        model_probability=0.57,
    )
    assert item["id"] == 101
    assert item["result"] == "pending"
    assert db.insert_attempts == 2
    assert db.rollbacks == 1
    assert db.commits >= 2
    assert "CREATE TABLE IF NOT EXISTS bets" in "\n".join(db.queries)


def test_settle_bet_calculates_win_pnl():
    db = _SettleSession()
    settled = bet_store.settle_bet(db, bet_id=12, result="win")
    assert settled["result"] == "win"
    assert settled["pnl"] == 75.0  # 50 * (2.5 - 1)
    assert db.commits == 1


def test_get_bets_summary_computes_roi_and_bankroll():
    db = _SummarySession()
    summary = bet_store.get_bets_summary(db, season="2025-26", initial_bankroll=1000.0)
    assert summary["settled_bets"] == 7
    assert summary["total_pnl"] == 84.5
    assert summary["roi"] == 0.1207
    assert summary["current_bankroll"] == 1084.5
