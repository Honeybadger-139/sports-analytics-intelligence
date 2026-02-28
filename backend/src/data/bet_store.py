"""
Bankroll ledger persistence utilities for bets table.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session


OPEN_BET_RESULTS = {"pending", None}
SETTLED_BET_RESULTS = {"win", "loss", "push"}


def is_missing_bets_table_error(exc: Exception) -> bool:
    """Detect missing-table errors for bets relation."""
    message = str(exc).lower()
    return "bets" in message and ("does not exist" in message or "undefinedtable" in message)


def ensure_bets_table(db: Session) -> None:
    """Create bets table/indexes if absent (legacy volume guardrail)."""
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS bets (
                id SERIAL PRIMARY KEY,
                game_id VARCHAR(20) REFERENCES matches(game_id),
                bet_type VARCHAR(50) NOT NULL,
                selection VARCHAR(100) NOT NULL,
                odds DECIMAL(8,4) NOT NULL,
                stake DECIMAL(10,2) NOT NULL,
                kelly_fraction DECIMAL(5,4),
                model_probability DECIMAL(5,4),
                result VARCHAR(20),
                pnl DECIMAL(10,2),
                placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                settled_at TIMESTAMP
            )
            """
        )
    )
    db.execute(text("CREATE INDEX IF NOT EXISTS idx_bets_game ON bets(game_id)"))
    db.execute(text("CREATE INDEX IF NOT EXISTS idx_bets_result ON bets(result)"))
    db.commit()


def _normalize_decimal(value: Optional[Decimal]) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _serialize_bet_row(row) -> Dict:
    data = dict(row._mapping)
    for key in ("odds", "stake", "kelly_fraction", "model_probability", "pnl"):
        if key in data:
            data[key] = _normalize_decimal(data.get(key))
    for key in ("placed_at", "settled_at", "game_date"):
        if key in data and data.get(key) is not None:
            data[key] = data[key].isoformat()
    return data


def create_bet(
    db: Session,
    *,
    game_id: str,
    bet_type: str,
    selection: str,
    odds: float,
    stake: float,
    kelly_fraction: Optional[float] = None,
    model_probability: Optional[float] = None,
    placed_at: Optional[datetime] = None,
) -> Dict:
    """
    Create one bet ledger row with `pending` status.
    """
    placed_at = placed_at or datetime.utcnow()
    attempts = 0

    while attempts < 2:
        try:
            row = db.execute(
                text(
                    """
                    INSERT INTO bets (
                        game_id, bet_type, selection, odds, stake,
                        kelly_fraction, model_probability, result, placed_at
                    )
                    VALUES (
                        :game_id, :bet_type, :selection, :odds, :stake,
                        :kelly_fraction, :model_probability, 'pending', :placed_at
                    )
                    RETURNING
                        id, game_id, bet_type, selection, odds, stake,
                        kelly_fraction, model_probability, result, pnl,
                        placed_at, settled_at
                    """
                ),
                {
                    "game_id": game_id,
                    "bet_type": bet_type,
                    "selection": selection,
                    "odds": odds,
                    "stake": stake,
                    "kelly_fraction": kelly_fraction,
                    "model_probability": model_probability,
                    "placed_at": placed_at,
                },
            ).fetchone()
            db.commit()
            return _serialize_bet_row(row)
        except Exception as exc:
            db.rollback()
            if attempts == 0 and is_missing_bets_table_error(exc):
                ensure_bets_table(db)
                attempts += 1
                continue
            raise

    raise RuntimeError("failed to create bet")


def list_bets(
    db: Session,
    *,
    season: Optional[str] = None,
    result: Optional[str] = None,
    limit: int = 50,
) -> List[Dict]:
    """
    List bets with optional season/result filters.
    """
    filters = []
    params: Dict[str, object] = {"limit": limit}

    if season:
        filters.append("m.season = :season")
        params["season"] = season

    if result:
        if result == "open":
            filters.append("(b.result IS NULL OR b.result = 'pending')")
        elif result == "settled":
            filters.append("b.result IN ('win', 'loss', 'push')")
        else:
            filters.append("b.result = :result")
            params["result"] = result

    where_sql = ""
    if filters:
        where_sql = "WHERE " + " AND ".join(filters)

    rows = db.execute(
        text(
            f"""
            SELECT
                b.id, b.game_id, b.bet_type, b.selection, b.odds, b.stake,
                b.kelly_fraction, b.model_probability, b.result, b.pnl,
                b.placed_at, b.settled_at,
                m.season, m.game_date,
                ht.abbreviation AS home_team,
                at.abbreviation AS away_team
            FROM bets b
            JOIN matches m ON b.game_id = m.game_id
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            {where_sql}
            ORDER BY b.placed_at DESC, b.id DESC
            LIMIT :limit
            """
        ),
        params,
    ).fetchall()
    return [_serialize_bet_row(row) for row in rows]


def _get_bet_for_settlement(db: Session, bet_id: int) -> Optional[Tuple[Decimal, Decimal, Optional[str]]]:
    row = db.execute(
        text(
            """
            SELECT stake, odds, result
            FROM bets
            WHERE id = :bet_id
            """
        ),
        {"bet_id": bet_id},
    ).fetchone()
    if not row:
        return None
    return row.stake, row.odds, row.result


def _calculate_pnl(*, result: str, stake: Decimal, odds: Decimal) -> Decimal:
    if result == "win":
        return stake * (odds - Decimal("1"))
    if result == "loss":
        return -stake
    return Decimal("0")


def settle_bet(
    db: Session,
    *,
    bet_id: int,
    result: str,
    settled_at: Optional[datetime] = None,
) -> Dict:
    """
    Settle a bet with `win/loss/push` and compute deterministic PnL.
    """
    result = result.lower().strip()
    if result not in SETTLED_BET_RESULTS:
        raise ValueError(f"invalid result: {result}")

    found = _get_bet_for_settlement(db, bet_id)
    if not found:
        raise LookupError(f"bet {bet_id} not found")

    stake, odds, current_result = found
    if current_result in SETTLED_BET_RESULTS:
        raise RuntimeError(f"bet {bet_id} already settled")

    settled_at = settled_at or datetime.utcnow()
    pnl = _calculate_pnl(result=result, stake=stake, odds=odds)

    row = db.execute(
        text(
            """
            UPDATE bets
            SET result = :result,
                pnl = :pnl,
                settled_at = :settled_at
            WHERE id = :bet_id
            RETURNING
                id, game_id, bet_type, selection, odds, stake,
                kelly_fraction, model_probability, result, pnl,
                placed_at, settled_at
            """
        ),
        {"bet_id": bet_id, "result": result, "pnl": pnl, "settled_at": settled_at},
    ).fetchone()
    db.commit()
    return _serialize_bet_row(row)


def get_bets_summary(
    db: Session,
    *,
    season: Optional[str] = None,
    initial_bankroll: float = 1000.0,
) -> Dict:
    """
    Aggregate bankroll ledger KPIs from bets table.
    """
    filters = []
    params: Dict[str, object] = {"initial_bankroll": initial_bankroll}
    if season:
        filters.append("m.season = :season")
        params["season"] = season

    where_sql = ""
    if filters:
        where_sql = "WHERE " + " AND ".join(filters)

    row = db.execute(
        text(
            f"""
            SELECT
                COUNT(*) AS total_bets,
                SUM(CASE WHEN b.result IN ('win', 'loss', 'push') THEN 1 ELSE 0 END) AS settled_bets,
                SUM(CASE WHEN b.result IS NULL OR b.result = 'pending' THEN 1 ELSE 0 END) AS open_bets,
                COALESCE(SUM(b.stake), 0) AS total_stake,
                COALESCE(SUM(CASE WHEN b.result IN ('win', 'loss', 'push') THEN b.stake ELSE 0 END), 0) AS settled_stake,
                COALESCE(SUM(COALESCE(b.pnl, 0)), 0) AS total_pnl
            FROM bets b
            JOIN matches m ON b.game_id = m.game_id
            {where_sql}
            """
        ),
        params,
    ).fetchone()

    total_bets = int(row.total_bets or 0)
    settled_bets = int(row.settled_bets or 0)
    open_bets = int(row.open_bets or 0)
    total_stake = _normalize_decimal(row.total_stake) or 0.0
    settled_stake = _normalize_decimal(row.settled_stake) or 0.0
    total_pnl = _normalize_decimal(row.total_pnl) or 0.0
    roi = round(total_pnl / settled_stake, 4) if settled_stake > 0 else 0.0

    return {
        "season": season,
        "initial_bankroll": float(initial_bankroll),
        "current_bankroll": round(float(initial_bankroll) + total_pnl, 2),
        "total_bets": total_bets,
        "settled_bets": settled_bets,
        "open_bets": open_bets,
        "total_stake": round(total_stake, 2),
        "settled_stake": round(settled_stake, 2),
        "total_pnl": round(total_pnl, 2),
        "roi": roi,
    }
