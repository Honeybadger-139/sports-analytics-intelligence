"""
espn_transformer.py — ESPN API Response → DB-Ready Rows
=========================================================

Transforms raw ESPN API payloads (as returned by ``EspnFetcher``) into
flat dictionaries whose keys match the PostgreSQL table columns defined in
``init.sql``.

Column type alignment with init.sql
-------------------------------------
- ``teams.team_id``          INTEGER  → transformer outputs ``int``
- ``players.player_id``      INTEGER  → transformer outputs ``int``
- ``matches.game_id``        VARCHAR  → transformer outputs ``str``
- ``team_game_stats.game_id`` VARCHAR → transformer outputs ``str``
- All percentage columns      DECIMAL(5,3) → ``float | None``
- All advanced metric columns DECIMAL(6,2) → ``float | None``

ESPN box-score response structure (key paths)
----------------------------------------------
- Team stats:   json["boxscore"]["teams"]  — list of 2 dicts, index 0 = away, 1 = home
  Each team dict has a ``statistics`` list of ``{name, displayValue}`` objects.
- Player stats: json["boxscore"]["players"] — parallel list (index 0 = away, 1 = home)
  Each entry has:
    - ``team.id``
    - ``statistics[0]["labels"]``   — ordered list of column names
    - ``statistics[0]["athletes"]`` — list of player rows
      Each athlete row has ``athlete.id``, ``athlete.displayName``,
      and ``statistics`` list matching the labels.
- Status:       json["header"]["competitions"][0]["status"]["type"]["completed"]
- Game date:    json["header"]["competitions"][0]["date"]
- Competitors:  json["header"]["competitions"][0]["competitors"]  — list of 2
  Each competitor has ``homeAway`` (``"home"``/``"away"``), ``team.id``,
  ``score`` (string).

Logger: ``gamethread.espn_transformer``

Season derivation
-----------------
ESPN dates are ISO-8601 with timezone offset.  We derive the NBA season string
(e.g. ``"2025-26"``) from the calendar year: October–December belong to the
season starting that year; January–June belong to the season that started the
prior year.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("gamethread.espn_transformer")

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# SCR-342: Hardcoded conference/division map
# ESPN /teams?limit=40 returns groups=null for all teams; neither the bulk
# nor the individual team endpoint exposes conference/division name strings.
# NBA conference and division assignments are stable season-to-season so a
# static map is the correct solution.
# Format: espn_team_id -> (conference, division)
# ---------------------------------------------------------------------------
_TEAM_CONFERENCE_DIVISION: dict[int, tuple[str, str]] = {
    # Eastern Conference
    1:  ("East", "Southeast"),   # Atlanta Hawks
    2:  ("East", "Atlantic"),    # Boston Celtics
    17: ("East", "Atlantic"),    # Brooklyn Nets
    30: ("East", "Southeast"),   # Charlotte Hornets
    4:  ("East", "Central"),     # Chicago Bulls
    5:  ("East", "Central"),     # Cleveland Cavaliers
    8:  ("East", "Central"),     # Detroit Pistons
    11: ("East", "Central"),     # Indiana Pacers
    14: ("East", "Southeast"),   # Miami Heat
    15: ("East", "Central"),     # Milwaukee Bucks
    18: ("East", "Atlantic"),    # New York Knicks
    19: ("East", "Southeast"),   # Orlando Magic
    20: ("East", "Atlantic"),    # Philadelphia 76ers
    28: ("East", "Atlantic"),    # Toronto Raptors
    27: ("East", "Southeast"),   # Washington Wizards
    # Western Conference
    6:  ("West", "Southwest"),   # Dallas Mavericks
    7:  ("West", "Northwest"),   # Denver Nuggets
    9:  ("West", "Pacific"),     # Golden State Warriors
    10: ("West", "Southwest"),   # Houston Rockets
    12: ("West", "Pacific"),     # LA Clippers
    13: ("West", "Pacific"),     # Los Angeles Lakers
    29: ("West", "Southwest"),   # Memphis Grizzlies
    16: ("West", "Northwest"),   # Minnesota Timberwolves
    3:  ("West", "Southwest"),   # New Orleans Pelicans
    25: ("West", "Northwest"),   # Oklahoma City Thunder
    21: ("West", "Pacific"),     # Phoenix Suns
    22: ("West", "Northwest"),   # Portland Trail Blazers
    23: ("West", "Pacific"),     # Sacramento Kings
    24: ("West", "Southwest"),   # San Antonio Spurs
    26: ("West", "Northwest"),   # Utah Jazz
}

_POSITION_MAP: dict[str, str] = {
    "point guard": "PG",
    "shooting guard": "SG",
    "small forward": "SF",
    "power forward": "PF",
    "center": "C",
    "forward": "SF",      # fallback
    "guard": "SG",        # fallback
    "forward-guard": "SG",
    "guard-forward": "SG",
    "forward-center": "PF",
    "center-forward": "C",
    "f": "SF",
    "g": "SG",
    "c": "C",
    "pg": "PG",
    "sg": "SG",
    "sf": "SF",
    "pf": "PF",
}


def _normalize_position(raw: str | None) -> str | None:
    """Return a canonical short-form position abbreviation or None."""
    if not raw:
        return None
    key = raw.strip().lower()
    return _POSITION_MAP.get(key, raw.upper()[:2] if raw else None)


def _safe_int(value: Any, default: int | None = None) -> int | None:
    """Cast to int, returning *default* on failure."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_float(value: Any, default: float | None = None) -> float | None:
    """Cast to float, returning *default* on failure."""
    if value is None:
        return default
    try:
        f = float(value)
        return f if f == f else default  # guard against NaN
    except (ValueError, TypeError):
        return default


def _parse_minutes(raw: str | None) -> float | None:
    """
    Parse ESPN minutes string (``"32:14"`` or ``"32.23"``) into decimal minutes.

    Returns ``None`` if the string is absent or cannot be parsed.
    """
    if not raw:
        return None
    raw = raw.strip()
    if ":" in raw:
        parts = raw.split(":")
        try:
            return float(parts[0]) + float(parts[1]) / 60.0
        except (ValueError, IndexError):
            return None
    return _safe_float(raw)


def _stat_map(statistics: list[dict]) -> dict[str, str]:
    """
    Convert ESPN ``statistics`` list of ``{name, displayValue}`` into a
    plain ``{name: displayValue}`` dict for convenient key-based lookup.
    """
    return {entry.get("name", ""): entry.get("displayValue", "") for entry in statistics}


def _split_stat(raw: str | None) -> tuple[float, float]:
    """
    Parse ESPN compound stat strings like ``"39-85"`` (made-attempted) into
    ``(made, attempted)`` floats.

    ESPN encodes FG/3PT/FT lines as ``"made-attempted"`` in team box scores.
    Returns ``(0.0, 0.0)`` when the value is absent or malformed.
    """
    if not raw:
        return 0.0, 0.0
    s = str(raw).strip()
    if "-" in s:
        parts = s.split("-", 1)
        return _safe_float(parts[0], 0.0), _safe_float(parts[1], 0.0)  # type: ignore[return-value]
    return _safe_float(s, 0.0), 0.0  # type: ignore[return-value]


def _nba_season_from_date(dt: datetime) -> str:
    """
    Derive NBA season string (e.g. ``"2025-26"``) from a datetime.

    The NBA season starts in October.  Games in Oct-Dec of year Y belong to
    season ``"Y-(Y+1)[2:]"``.  Games in Jan-Jun of year Y belong to season
    ``"(Y-1)-Y[2:]"``.
    """
    year = dt.year
    month = dt.month
    if month >= 10:
        start = year
    else:
        start = year - 1
    end = (start + 1) % 100  # last two digits
    return f"{start}-{end:02d}"


def _parse_game_date(raw_date: str) -> datetime | None:
    """
    Parse an ESPN ISO-8601 date string into a timezone-aware datetime.

    Handles both ``Z`` suffix and ``+HH:MM`` offset formats.
    Returns ``None`` on parse failure.
    """
    if not raw_date:
        return None
    # Normalise "Z" → "+00:00" for fromisoformat (Python < 3.11 compat)
    normalised = raw_date.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalised)
    except ValueError:
        logger.warning("[espn_transformer] Could not parse date string: %r", raw_date)
        return None


# ---------------------------------------------------------------------------
# Public transform functions
# ---------------------------------------------------------------------------


def transform_teams(raw_teams: list[dict]) -> list[dict]:
    """
    Transform raw ESPN teams list into rows for the ``teams`` table.

    Parameters
    ----------
    raw_teams:
        Output of ``EspnFetcher.fetch_teams()`` — list of ESPN team objects.

    Returns
    -------
    list[dict]
        Each dict matches ``teams`` table columns:
        ``team_id``, ``abbreviation``, ``full_name``, ``city``,
        ``conference``, ``division``.

    Notes
    -----
    ``team_id`` is the ESPN integer team ID.  The ``id`` field in the DB
    column is a SERIAL surrogate key; ``team_id`` is the natural business key.
    """
    rows: list[dict] = []
    for team in raw_teams:
        team_id = _safe_int(team.get("id"))
        if team_id is None:
            logger.warning("[espn_transformer] transform_teams: team missing id, skipping %r", team)
            continue

        abbreviation = (team.get("abbreviation") or "").strip() or None
        display_name = (team.get("displayName") or "").strip() or None
        location = (team.get("location") or "").strip() or None

        # SCR-342: ESPN bulk teams endpoint returns groups=null for all teams;
        # neither the bulk nor individual endpoint exposes conference/division
        # name strings. Use the hardcoded static map instead.
        conf_div = _TEAM_CONFERENCE_DIVISION.get(team_id)
        conference: str | None = conf_div[0] if conf_div else None
        division: str | None = conf_div[1] if conf_div else None
        if conf_div is None:
            logger.warning(
                "[espn_transformer] transform_teams: team_id=%d not in conference map", team_id
            )

        rows.append(
            {
                "team_id": team_id,
                "abbreviation": abbreviation,
                "full_name": display_name,
                "city": location,
                "conference": conference,
                "division": division,
            }
        )

    logger.info("[espn_transformer] transform_teams: %d team row(s) produced", len(rows))
    return rows


def transform_game(raw_event: dict) -> dict | None:
    """
    Transform a raw ESPN event object into a row for the ``matches`` table.

    Filters out non-regular-season / All-Star events.  Returns ``None`` if
    the event is not a real game (e.g. All-Star, skills challenge).

    Parameters
    ----------
    raw_event:
        A single event dict from ``EspnFetcher.fetch_scoreboard`` or
        ``EspnFetcher.fetch_season_games``.

    Returns
    -------
    dict | None
        Matches ``matches`` table columns, or ``None`` to signal the caller
        should skip this event.

    Column mapping
    --------------
    ``game_id``        → ESPN event id (string, VARCHAR in DB)
    ``game_date``      → date portion of competition start time (UTC)
    ``season``         → derived NBA season string (e.g. ``"2025-26"``)
    ``home_team_id``   → ESPN integer team id
    ``away_team_id``   → ESPN integer team id
    ``home_score``     → int or None if not completed
    ``away_score``     → int or None if not completed
    ``winner_team_id`` → ESPN integer team id of winning side, or None
    ``is_completed``   → bool
    """
    event_id = str(raw_event.get("id") or "").strip()
    if not event_id:
        logger.debug("[espn_transformer] transform_game: event missing id, skipping")
        return None

    # Competitions is always a list; we use the first entry
    competitions: list[dict] = raw_event.get("competitions") or []
    if not competitions:
        logger.debug(
            "[espn_transformer] transform_game: event %s has no competitions", event_id
        )
        return None
    comp = competitions[0]

    # Filter non-real games: ESPN uses ``type.abbreviation`` such as
    # "STD" for standard / regular season, "POST" for playoff.
    # All-Star events often have type "ASG", "ALLSTAR", "EXH", etc.
    comp_type_abbr = (
        (comp.get("type") or {}).get("abbreviation") or ""
    ).upper()
    if comp_type_abbr in {"ASG", "ALLSTAR", "ASW", "EXH", "PRE"}:
        logger.debug(
            "[espn_transformer] transform_game: skipping non-regular event %s (type=%s)",
            event_id,
            comp_type_abbr,
        )
        return None

    # Status
    status_block = (comp.get("status") or {}).get("type") or {}
    is_completed: bool = bool(status_block.get("completed", False))

    # Date
    raw_date = comp.get("date") or raw_event.get("date") or ""
    dt = _parse_game_date(raw_date)
    if dt is None:
        logger.warning(
            "[espn_transformer] transform_game: cannot parse date for event %s", event_id
        )
        return None
    game_date = dt.date()
    season = _nba_season_from_date(dt)

    # Competitors — ESPN guarantees exactly 2 per competition
    competitors: list[dict] = comp.get("competitors") or []
    home_team_id: int | None = None
    away_team_id: int | None = None
    home_score: int | None = None
    away_score: int | None = None

    for competitor in competitors:
        home_away = (competitor.get("homeAway") or "").lower()
        tid = _safe_int((competitor.get("team") or {}).get("id"))
        # ESPN schedule API returns score as dict {'value': 116.0, 'displayValue': '116'};
        # game summary API returns a plain string '116'.  Handle both.
        score_raw = competitor.get("score")
        if isinstance(score_raw, dict):
            score = _safe_int(score_raw.get("displayValue") or score_raw.get("value"))
        else:
            score = _safe_int(score_raw)
        if home_away == "home":
            home_team_id = tid
            home_score = score if is_completed else None
        elif home_away == "away":
            away_team_id = tid
            away_score = score if is_completed else None

    if home_team_id is None or away_team_id is None:
        logger.warning(
            "[espn_transformer] transform_game: could not resolve both team IDs for event %s",
            event_id,
        )
        return None

    # Winner
    winner_team_id: int | None = None
    if is_completed and home_score is not None and away_score is not None:
        if home_score > away_score:
            winner_team_id = home_team_id
        elif away_score > home_score:
            winner_team_id = away_team_id
        # Ties should not occur in NBA but leave winner as None if equal

    return {
        "game_id": event_id,
        "game_date": game_date,
        "season": season,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "home_score": home_score,
        "away_score": away_score,
        "winner_team_id": winner_team_id,
        "is_completed": is_completed,
    }


def transform_team_game_stats(raw_summary: dict, game_id: str) -> list[dict]:
    """
    Transform a raw ESPN game summary into two rows for ``team_game_stats``.

    Computes advanced metrics from raw counting stats using industry-standard
    formulas:

    - possessions ≈ FGA - OREB + TOV + 0.44 * FTA
    - offensive_rating = 100 * PTS / possessions
    - defensive_rating = 100 * opp_PTS / opp_possessions
    - net_rating = offensive_rating - defensive_rating
    - pace = 48 * ((team_poss + opp_poss) / 2) / minutes_played * 5
    - efg_pct = (FGM + 0.5 * FG3M) / FGA
    - ts_pct = PTS / (2 * (FGA + 0.44 * FTA))

    Parameters
    ----------
    raw_summary:
        Full ESPN game summary dict from ``EspnFetcher.fetch_game_summary``.
    game_id:
        The ESPN event ID string — used as the FK to ``matches.game_id``.

    Returns
    -------
    list[dict]
        0, 1, or 2 dicts matching ``team_game_stats`` columns.
        Returns ``[]`` if the boxscore is unavailable.

    ESPN stat name keys (``statistics[*].name``)
    ---------------------------------------------
    fieldGoalsMade, fieldGoalsAttempted, fieldGoalPct,
    threePointFieldGoalsMade, threePointFieldGoalsAttempted, threePointFieldGoalPct,
    freeThrowsMade, freeThrowsAttempted, freeThrowPct,
    offensiveRebounds, defensiveRebounds, rebounds,
    assists, steals, blocks, turnovers, points
    """
    boxscore = raw_summary.get("boxscore") or {}
    teams_data: list[dict] = boxscore.get("teams") or []

    # Build team_id → points lookup from the game header (competitor scores).
    # The team boxscore statistics list does NOT include a "points" key;
    # scores are only available from the header competitions block.
    header_scores: dict[int, float] = {}
    header_comps_list = (raw_summary.get("header") or {}).get("competitions") or []
    if header_comps_list:
        for _c in (header_comps_list[0].get("competitors") or []):
            _tid = _safe_int((_c.get("team") or {}).get("id"))
            # header competitor score is a plain string e.g. '116'
            _score = _safe_float(_c.get("score"))
            if _tid is not None and _score is not None:
                header_scores[_tid] = _score

    if len(teams_data) < 2:
        logger.warning(
            "[espn_transformer] transform_team_game_stats: game %s has %d team entries (need 2)",
            game_id,
            len(teams_data),
        )
        return []

    # ESPN: index 0 = away, index 1 = home
    # We process both to derive opponent stats for advanced metrics
    raw_stats: list[dict[str, str]] = []
    team_ids: list[int | None] = []

    for entry in teams_data:
        statistics: list[dict] = entry.get("statistics") or []
        sm = _stat_map(statistics)
        raw_stats.append(sm)
        team_ids.append(_safe_int((entry.get("team") or {}).get("id")))

    rows: list[dict] = []
    for i in range(2):
        j = 1 - i  # opponent index
        sm = raw_stats[i]
        opp_sm = raw_stats[j]
        team_id = team_ids[i]

        if team_id is None:
            logger.warning(
                "[espn_transformer] transform_team_game_stats: game %s team[%d] missing id",
                game_id,
                i,
            )
            continue

        # Raw counting stats.
        # ESPN team boxscore uses compound keys for shooting lines:
        #   "fieldGoalsMade-fieldGoalsAttempted" → "39-85"
        #   "threePointFieldGoalsMade-threePointFieldGoalsAttempted" → "16-41"
        #   "freeThrowsMade-freeThrowsAttempted" → "23-30"
        # Rebounds use "totalRebounds" (not "rebounds").
        # Points are NOT in the statistics list — sourced from header competitor scores.
        fgm, fga = _split_stat(sm.get("fieldGoalsMade-fieldGoalsAttempted"))
        fg3m, fg3a = _split_stat(sm.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted"))
        ftm, fta = _split_stat(sm.get("freeThrowsMade-freeThrowsAttempted"))
        oreb = _safe_float(sm.get("offensiveRebounds"), 0.0)
        dreb = _safe_float(sm.get("defensiveRebounds"), 0.0)
        reb = _safe_float(sm.get("totalRebounds")) or (oreb + dreb)
        ast = _safe_float(sm.get("assists"), 0.0)
        stl = _safe_float(sm.get("steals"), 0.0)
        blk = _safe_float(sm.get("blocks"), 0.0)
        tov = _safe_float(sm.get("turnovers"), 0.0)
        # Points from header competitor score lookup (not in statistics list)
        pts = header_scores.get(team_id, 0.0) if team_id is not None else 0.0

        # Opponent counting stats (for defensive rating).
        # Also uses the ESPN compound stat key format.
        _, opp_fga = _split_stat(opp_sm.get("fieldGoalsMade-fieldGoalsAttempted"))
        _, opp_fta = _split_stat(opp_sm.get("freeThrowsMade-freeThrowsAttempted"))
        opp_oreb = _safe_float(opp_sm.get("offensiveRebounds"), 0.0)
        opp_tov = _safe_float(opp_sm.get("turnovers"), 0.0)
        opp_pts = header_scores.get(team_ids[j], 0.0) if team_ids[j] is not None else 0.0

        # Percentages (prefer ESPN's computed value; fall back to manual).
        # ESPN provides percentages as 0-100 integers (e.g. "45" for 45%).
        # DB columns are DECIMAL(5,3) storing 0-1 (e.g. 0.450 for 45%), so divide by 100.
        def _pct(made: float | None, attempted: float | None, espn_val: str | None) -> float | None:
            val = _safe_float(espn_val)
            if val is not None:
                return round(val / 100.0, 3)
            if made is not None and attempted and attempted > 0:
                return round(made / attempted, 3)
            return None

        fg_pct = _pct(fgm, fga, sm.get("fieldGoalPct"))
        fg3_pct = _pct(fg3m, fg3a, sm.get("threePointFieldGoalPct"))
        ft_pct = _pct(ftm, fta, sm.get("freeThrowPct"))

        # Advanced metrics
        possessions: float | None = None
        opp_possessions: float | None = None
        offensive_rating: float | None = None
        defensive_rating: float | None = None
        net_rating: float | None = None
        pace: float | None = None
        efg_pct: float | None = None
        ts_pct: float | None = None

        if fga is not None and oreb is not None and tov is not None and fta is not None:
            possessions = fga - oreb + tov + 0.44 * fta

        if opp_fga is not None and opp_oreb is not None and opp_tov is not None and opp_fta is not None:
            opp_possessions = opp_fga - opp_oreb + opp_tov + 0.44 * opp_fta

        if possessions and possessions > 0 and pts is not None:
            offensive_rating = round(100.0 * pts / possessions, 2)

        if opp_possessions and opp_possessions > 0 and opp_pts is not None:
            defensive_rating = round(100.0 * opp_pts / opp_possessions, 2)

        if offensive_rating is not None and defensive_rating is not None:
            net_rating = round(offensive_rating - defensive_rating, 2)

        # Pace: normalize to 48 regulation minutes; 5 players per team on court
        # minutes_played is per-player total (5 * 48 = 240 for a full game)
        if possessions is not None and opp_possessions is not None:
            # Use 48 minutes as reference (240 player-minutes for full game)
            total_poss = possessions + opp_possessions
            if total_poss > 0:
                pace = round(48.0 * (total_poss / 2.0) / 48.0, 2)

        if fga is not None and fga > 0 and fgm is not None and fg3m is not None:
            efg_pct = round((fgm + 0.5 * fg3m) / fga, 3)

        ts_denom = 2.0 * ((fga or 0) + 0.44 * (fta or 0))
        if ts_denom > 0 and pts is not None:
            ts_pct = round(pts / ts_denom, 3)

        rows.append(
            {
                "game_id": game_id,
                "team_id": team_id,
                "opponent_team_id": team_ids[j],
                "points": _safe_int(pts),          # from header_scores (not in stat map)
                "rebounds": _safe_int(reb),
                "assists": _safe_int(sm.get("assists")),
                "steals": _safe_int(sm.get("steals")),
                "blocks": _safe_int(sm.get("blocks")),
                "turnovers": _safe_int(sm.get("turnovers")),
                "field_goal_pct": fg_pct,
                "three_point_pct": fg3_pct,
                "free_throw_pct": ft_pct,
                # Extended counting stats (not in init.sql but useful for downstream)
                "field_goals_made": _safe_int(fgm),
                "field_goals_attempted": _safe_int(fga),
                "three_points_made": _safe_int(fg3m),
                "three_points_attempted": _safe_int(fg3a),
                "free_throws_made": _safe_int(ftm),
                "free_throws_attempted": _safe_int(fta),
                "offensive_rebounds": _safe_int(oreb),
                "defensive_rebounds": _safe_int(dreb),
                # Advanced metrics
                "offensive_rating": offensive_rating,
                "defensive_rating": defensive_rating,
                "net_rating": net_rating,
                "pace": pace,
                "effective_fg_pct": efg_pct,
                "true_shooting_pct": ts_pct,
            }
        )

    logger.info(
        "[espn_transformer] transform_team_game_stats: game %s → %d row(s)", game_id, len(rows)
    )
    return rows


def transform_players(raw_roster: list[dict], espn_team_id: str) -> list[dict]:
    """
    Transform a raw ESPN roster into rows for the ``players`` table.

    Parameters
    ----------
    raw_roster:
        Output of ``EspnFetcher.fetch_team_roster`` — flat list of ESPN
        athlete objects.
    espn_team_id:
        ESPN integer team ID as a string.  Stored as ``team_id`` (int FK).

    Returns
    -------
    list[dict]
        Each dict matches ``players`` table columns:
        ``player_id``, ``full_name``, ``team_id``, ``position``, ``is_active``.
    """
    team_id = _safe_int(espn_team_id)
    if team_id is None:
        logger.error(
            "[espn_transformer] transform_players: invalid espn_team_id=%r", espn_team_id
        )
        return []

    rows: list[dict] = []
    for athlete in raw_roster:
        player_id = _safe_int(athlete.get("id"))
        if player_id is None:
            logger.debug(
                "[espn_transformer] transform_players: athlete missing id, skipping %r",
                athlete.get("displayName"),
            )
            continue

        full_name = (athlete.get("displayName") or athlete.get("fullName") or "").strip() or None
        raw_pos = (athlete.get("position") or {}).get("name") or (
            athlete.get("position") or {}).get("abbreviation")
        position = _normalize_position(raw_pos)
        # ESPN marks active/inactive via status.name (e.g. "Active", "Injured",
        # "Out"). status.type is a string ("active"), not a nested dict.
        status_obj = athlete.get("status") or {}
        status_name: str = ""
        if isinstance(status_obj, dict):
            # Use the human-readable "name" field on the status object
            status_name = (status_obj.get("name") or "").strip().lower()
        is_active: bool = status_name in ("active", "") or status_name == "active"

        rows.append(
            {
                "player_id": player_id,
                "full_name": full_name,
                "team_id": team_id,
                "position": position,
                "is_active": is_active,
            }
        )

    logger.info(
        "[espn_transformer] transform_players: team %s → %d player row(s)",
        espn_team_id,
        len(rows),
    )
    return rows


def transform_player_game_stats(raw_summary: dict, game_id: str) -> list[dict]:
    """
    Transform raw ESPN game summary into per-player rows for ``player_game_stats``.

    ESPN player stats are encoded as parallel arrays: a ``labels`` list
    defines column order, and each athlete's ``statistics`` list holds values
    at the same indices.

    Fantasy points formula (ESPN standard):
        PTS*1 + REB*1.2 + AST*1.5 + BLK*3 + STL*3 + TOV*(-1)

    Parameters
    ----------
    raw_summary:
        Full ESPN game summary dict from ``EspnFetcher.fetch_game_summary``.
    game_id:
        ESPN event ID string — FK to ``matches.game_id``.

    Returns
    -------
    list[dict]
        One dict per player who participated, matching ``player_game_stats``
        columns.  Players with DNP (did not play) are excluded.
    """
    boxscore = raw_summary.get("boxscore") or {}
    players_data: list[dict] = boxscore.get("players") or []

    # Build a team_id → opponent_team_id mapping from the two teams in the boxscore.
    # ESPN always returns exactly 2 team entries (away, home).
    _all_team_ids: list[int] = [
        tid
        for entry in players_data
        if (tid := _safe_int((entry.get("team") or {}).get("id"))) is not None
    ]
    _opponent_map: dict[int, int | None] = {}
    if len(_all_team_ids) == 2:
        _opponent_map[_all_team_ids[0]] = _all_team_ids[1]
        _opponent_map[_all_team_ids[1]] = _all_team_ids[0]

    rows: list[dict] = []

    for team_entry in players_data:
        team_id = _safe_int((team_entry.get("team") or {}).get("id"))
        if team_id is None:
            logger.warning(
                "[espn_transformer] transform_player_game_stats: game %s team entry missing id",
                game_id,
            )
            continue

        statistics_groups: list[dict] = team_entry.get("statistics") or []
        if not statistics_groups:
            logger.debug(
                "[espn_transformer] transform_player_game_stats: game %s team %d no stats groups",
                game_id,
                team_id,
            )
            continue

        # ESPN wraps all player stats in a single statistics group (index 0)
        stat_group = statistics_groups[0]
        labels: list[str] = stat_group.get("labels") or []
        athletes: list[dict] = stat_group.get("athletes") or []

        # Build a label→index lookup for fast access
        label_index: dict[str, int] = {lbl: idx for idx, lbl in enumerate(labels)}

        def _get_stat(stat_values: list[str], key: str) -> str | None:
            idx = label_index.get(key)
            if idx is None or idx >= len(stat_values):
                return None
            return stat_values[idx]

        for athlete_entry in athletes:
            athlete = athlete_entry.get("athlete") or {}
            player_id = _safe_int(athlete.get("id"))
            if player_id is None:
                continue

            # ESPN uses "stats" key for the per-athlete stat array (parallel to labels).
            # The "statistics" key (a list of groups) exists at the team level, not here.
            stat_values: list[str] = athlete_entry.get("stats") or athlete_entry.get("statistics") or []

            # SCR-344: DNP players have stats=[] (empty array). When stat_values is
            # empty, minutes_raw resolves to None → minutes is None, so the 0.0
            # guard below never fires and a fully-null row gets inserted.
            # Skip immediately on empty stats — no data to store.
            if not stat_values:
                continue

            # DNP check — minutes will be "0:00" or absent
            minutes_raw = _get_stat(stat_values, "min") or _get_stat(stat_values, "MIN")
            minutes = _parse_minutes(minutes_raw)
            if minutes is not None and minutes == 0.0:
                # Player suited up but did not play — skip
                continue

            # Retrieve individual stats by label
            # ESPN label names vary slightly by endpoint; we try common variants
            def _s(key: str, *aliases: str) -> str | None:
                for k in (key, *aliases):
                    v = _get_stat(stat_values, k)
                    if v is not None:
                        return v
                return None

            pts = _safe_int(_s("pts", "PTS", "points"))
            reb = _safe_int(_s("reb", "REB", "rebounds"))
            ast = _safe_int(_s("ast", "AST", "assists"))
            stl = _safe_int(_s("stl", "STL", "steals"))
            blk = _safe_int(_s("blk", "BLK", "blocks"))
            tov = _safe_int(_s("to", "TO", "turnover", "turnovers"))
            pf = _safe_int(_s("pf", "PF", "fouls"))
            plus_minus = _safe_int(_s("+/-", "plusMinus", "plus_minus")) or 0

            # Shooting lines — "3-5" format means made-attempted
            def _split_shooting(raw: str | None) -> tuple[int | None, int | None]:
                if not raw or "-" not in raw:
                    return None, None
                parts = raw.split("-", 1)
                return _safe_int(parts[0]), _safe_int(parts[1])

            fg_raw = _s("fg", "FG", "fieldGoals")
            fg3_raw = _s("3pt", "3PT", "threePoint")
            ft_raw = _s("ft", "FT", "freeThrows")

            fgm, fga = _split_shooting(fg_raw)
            fg3m, fg3a = _split_shooting(fg3_raw)
            ftm, fta = _split_shooting(ft_raw)

            # Percentages — compute manually from made/attempted.
            # Returns 0.0 (not None) when attempted == 0 so ML feature vectors
            # are never NULL.
            def _shooting_pct(made: int | None, attempted: int | None) -> float:
                if made is None or attempted is None or attempted == 0:
                    return 0.0
                return round(made / attempted, 3)

            fg_pct = _shooting_pct(fgm, fga)
            fg3_pct = _shooting_pct(fg3m, fg3a)
            ft_pct = _shooting_pct(ftm, fta)

            # ESPN fantasy points formula — always compute (stats already defaulted to 0)
            fantasy_points: float = round(
                (pts or 0) * 1.0
                + (reb or 0) * 1.2
                + (ast or 0) * 1.5
                + (blk or 0) * 3.0
                + (stl or 0) * 3.0
                + (tov or 0) * -1.0,
                2,
            )

            rows.append(
                {
                    "game_id": game_id,
                    "player_id": player_id,
                    "team_id": team_id,
                    "opponent_team_id": _opponent_map.get(team_id) if team_id is not None else None,
                    "minutes": minutes,
                    "points": pts if pts is not None else 0,
                    "rebounds": reb if reb is not None else 0,
                    "assists": ast if ast is not None else 0,
                    "steals": stl if stl is not None else 0,
                    "blocks": blk if blk is not None else 0,
                    "turnovers": tov if tov is not None else 0,
                    "personal_fouls": pf if pf is not None else 0,
                    "field_goals_made": fgm if fgm is not None else 0,
                    "field_goals_attempted": fga if fga is not None else 0,
                    "field_goal_pct": fg_pct,
                    "three_points_made": fg3m if fg3m is not None else 0,
                    "three_points_attempted": fg3a if fg3a is not None else 0,
                    "three_point_pct": fg3_pct,
                    "free_throws_made": ftm if ftm is not None else 0,
                    "free_throws_attempted": fta if fta is not None else 0,
                    "free_throw_pct": ft_pct,
                    "plus_minus": plus_minus,
                    "fantasy_points": fantasy_points,
                    "match_played": minutes is not None and minutes > 0,
                }
            )

    logger.info(
        "[espn_transformer] transform_player_game_stats: game %s → %d player row(s)",
        game_id,
        len(rows),
    )
    return rows


def compute_player_season_stats(season: str, db_session) -> list[dict]:
    """
    Aggregate ``player_game_stats`` into season-level rows for
    ``player_season_stats``.

    Reads all completed-game player stats for *season* from the DB session
    and computes averages, totals, and win/loss record per player.

    Parameters
    ----------
    season:
        NBA season string, e.g. ``"2025-26"``.
    db_session:
        An active SQLAlchemy ``Session`` or connection with access to
        ``player_game_stats``, ``matches``, and ``players``.

    Returns
    -------
    list[dict]
        Each dict matches ``player_season_stats`` columns:
        ``player_id``, ``season``, ``team_id``, ``games_played``,
        ``wins``, ``losses``, ``win_pct``,
        ``minutes`` (avg), ``points`` (avg), ``rebounds`` (avg),
        ``assists`` (avg), ``steals`` (avg), ``blocks`` (avg),
        ``turnovers`` (avg), ``field_goal_pct``, ``three_point_pct``,
        ``free_throw_pct``, ``plus_minus`` (sum), ``fantasy_points`` (sum).

    Notes
    -----
    This function intentionally avoids Pandas to remain lightweight and
    cloud-job friendly.  It uses raw SQL via the provided session.
    """
    from sqlalchemy import text

    query = text(
        """
        SELECT
            pgs.player_id,
            pgs.team_id,
            COUNT(*)                                           AS games_played,
            SUM(CASE WHEN m.winner_team_id = pgs.team_id THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN m.winner_team_id != pgs.team_id AND m.winner_team_id IS NOT NULL
                     THEN 1 ELSE 0 END)                        AS losses,
            AVG(pgs.minutes)                                   AS avg_minutes,
            AVG(pgs.points)                                    AS avg_points,
            AVG(pgs.rebounds)                                  AS avg_rebounds,
            AVG(pgs.assists)                                   AS avg_assists,
            AVG(pgs.steals)                                    AS avg_steals,
            AVG(pgs.blocks)                                    AS avg_blocks,
            AVG(pgs.turnovers)                                 AS avg_turnovers,
            SUM(pgs.field_goals_made)::float /
                NULLIF(SUM(pgs.field_goals_attempted), 0)      AS field_goal_pct,
            SUM(pgs.three_points_made)::float /
                NULLIF(SUM(pgs.three_points_attempted), 0)     AS three_point_pct,
            SUM(pgs.free_throws_made)::float /
                NULLIF(SUM(pgs.free_throws_attempted), 0)      AS free_throw_pct,
            SUM(pgs.plus_minus)                                AS plus_minus,
            SUM(pgs.fantasy_points)                            AS fantasy_points
        FROM player_game_stats pgs
        JOIN matches m ON m.game_id = pgs.game_id
        WHERE m.season = :season
          AND m.is_completed = TRUE
        GROUP BY pgs.player_id, pgs.team_id
        ORDER BY pgs.player_id
        """
    )

    try:
        result = db_session.execute(query, {"season": season})
        rows_raw = result.fetchall()
    except Exception as exc:
        logger.error(
            "[espn_transformer] compute_player_season_stats: query failed for season %s: %s",
            season,
            exc,
        )
        return []

    rows: list[dict] = []
    for row in rows_raw:
        mapping = dict(row._mapping)
        games_played = int(mapping.get("games_played") or 0)
        wins = int(mapping.get("wins") or 0)
        losses = int(mapping.get("losses") or 0)
        win_pct = round(wins / games_played, 3) if games_played > 0 else None

        def _avg(val: Any) -> float | None:
            f = _safe_float(val)
            return round(f, 2) if f is not None else None

        def _pct(val: Any) -> float | None:
            f = _safe_float(val)
            return round(f, 3) if f is not None else None

        rows.append(
            {
                "player_id": int(mapping["player_id"]),
                "season": season,
                "team_id": int(mapping["team_id"]),
                "games_played": games_played,
                "wins": wins,
                "losses": losses,
                "win_pct": win_pct,
                "minutes": _avg(mapping.get("avg_minutes")),
                "points": _avg(mapping.get("avg_points")),
                "rebounds": _avg(mapping.get("avg_rebounds")),
                "assists": _avg(mapping.get("avg_assists")),
                "steals": _avg(mapping.get("avg_steals")),
                "blocks": _avg(mapping.get("avg_blocks")),
                "turnovers": _avg(mapping.get("avg_turnovers")),
                "field_goal_pct": _pct(mapping.get("field_goal_pct")),
                "three_point_pct": _pct(mapping.get("three_point_pct")),
                "free_throw_pct": _pct(mapping.get("free_throw_pct")),
                "plus_minus": _safe_float(mapping.get("plus_minus")),
                "fantasy_points": _safe_float(mapping.get("fantasy_points")),
            }
        )

    logger.info(
        "[espn_transformer] compute_player_season_stats: season %s → %d player row(s)",
        season,
        len(rows),
    )
    return rows
