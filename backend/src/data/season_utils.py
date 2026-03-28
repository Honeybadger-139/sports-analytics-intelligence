from __future__ import annotations

import re
from typing import Any, List, Optional

from sqlalchemy import text


def expand_season_aliases(season: Optional[str]) -> List[str]:
    """
    Expand season input into common aliases used across data providers.

    Examples:
      2025-26    -> 2025-26, 2025-2026, 2025/26, 2025, 2026
      2025-2026  -> 2025-26, 2025-2026, 2025/26, 2025, 2026
      2026       -> 2025-26, 2025-2026, 2025/26, 2025, 2026
    """
    if season is None:
        return []

    raw = str(season).strip()
    if not raw:
        return []

    aliases: list[str] = []
    seen: set[str] = set()

    def _push(value: str) -> None:
        v = value.strip()
        if not v or v in seen:
            return
        seen.add(v)
        aliases.append(v)

    _push(raw)

    match_short = re.fullmatch(r"(\d{4})[-/](\d{2})", raw)
    match_long = re.fullmatch(r"(\d{4})[-/](\d{4})", raw)
    match_year = re.fullmatch(r"(\d{4})", raw)

    if match_short:
        start = int(match_short.group(1))
        end = 2000 + int(match_short.group(2))
        _push(f"{start}-{end % 100:02d}")
        _push(f"{start}-{end}")
        _push(f"{start}/{end % 100:02d}")
        _push(str(start))
        _push(str(end))
        return aliases

    if match_long:
        start = int(match_long.group(1))
        end = int(match_long.group(2))
        _push(f"{start}-{end % 100:02d}")
        _push(f"{start}-{end}")
        _push(f"{start}/{end % 100:02d}")
        _push(str(start))
        _push(str(end))
        return aliases

    if match_year:
        end = int(match_year.group(1))
        start = end - 1
        _push(f"{start}-{end % 100:02d}")
        _push(f"{start}-{end}")
        _push(f"{start}/{end % 100:02d}")
        _push(str(start))
        _push(str(end))

    return aliases


def latest_completed_season(db_session: Any) -> Optional[str]:
    """Return the most recent season that has at least one completed game."""
    row = db_session.execute(
        text(
            """
            SELECT m.season
            FROM matches m
            WHERE m.is_completed = TRUE
              AND m.season IS NOT NULL
              AND m.season <> ''
            GROUP BY m.season
            ORDER BY MAX(m.game_date) DESC, COUNT(*) DESC
            LIMIT 1
            """
        )
    ).fetchone()
    return str(row[0]) if row and row[0] else None
