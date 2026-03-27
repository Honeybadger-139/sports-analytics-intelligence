"""
espn_fetcher.py — ESPN Unofficial API Client
=============================================

Provides a polite, retry-safe HTTP client for the ESPN unofficial NBA API.
No API key is required; ESPN exposes these endpoints publicly and they work
reliably from GCP Cloud Run (unlike stats.nba.com which blocks cloud IPs).

Design decisions:
    - Single ``EspnFetcher`` class encapsulates all HTTP concerns (session
      reuse, timeouts, retries, polite delays).
    - Returns raw ``dict`` / ``list[dict]`` rather than domain objects so
      callers (``espn_transformer``) own the mapping logic — clean separation
      of concerns.
    - Retry on HTTP 429 (rate-limited) and 503 (service unavailable) with
      exponential back-off plus jitter. Other 4xx errors are not retried
      because they indicate a caller bug (bad ID, wrong endpoint).
    - ``fetch_season_games`` de-duplicates across teams using a ``set`` of
      seen event IDs — ESPN lists the same game under both competing teams.

Logger: ``gamethread.espn_fetcher``
"""

from __future__ import annotations

import datetime
import logging
import random
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("gamethread.espn_fetcher")

# ---------------------------------------------------------------------------
# ESPN API base URLs
# ---------------------------------------------------------------------------
_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"

_URL_TEAMS = f"{_BASE}/teams?limit=40"
_URL_SCOREBOARD = f"{_BASE}/scoreboard?dates={{date}}"       # date = YYYYMMDD
_URL_SUMMARY = f"{_BASE}/summary?event={{event_id}}"
_URL_ROSTER = f"{_BASE}/teams/{{team_id}}/roster"
_URL_SCHEDULE = f"{_BASE}/teams/{{team_id}}/schedule?season={{year}}"

# Retryable HTTP status codes
_RETRYABLE_STATUSES = {429, 503}
_MAX_RETRIES = 3
_BASE_BACKOFF_SECONDS = 2.0
_REQUEST_TIMEOUT = 30  # seconds


class EspnFetcher:
    """
    Polite ESPN unofficial API client with retry logic.

    Parameters
    ----------
    delay_between_requests:
        Minimum seconds to sleep between successive HTTP calls.  Actual sleep
        adds ±20 % jitter so requests look organic, not robotic.

    Example
    -------
    >>> fetcher = EspnFetcher(delay_between_requests=1.0)
    >>> teams = fetcher.fetch_teams()
    >>> scoreboard = fetcher.fetch_scoreboard(datetime.date(2025, 1, 15))
    """

    def __init__(self, delay_between_requests: float = 1.0) -> None:
        self._delay = delay_between_requests
        self._session = self._build_session()
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_teams(self) -> list[dict]:
        """
        Return all 30 NBA teams with ESPN IDs and metadata.

        Returns
        -------
        list[dict]
            Raw ESPN team objects from ``sports[0].leagues[0].teams[*].team``.
            Each dict contains at minimum: ``id``, ``abbreviation``,
            ``displayName``, ``location``, and nested ``groups`` for
            conference / division when available.
        """
        logger.info("[espn_fetcher] fetch_teams → %s", _URL_TEAMS)
        data = self._get(_URL_TEAMS)
        try:
            entries = data["sports"][0]["leagues"][0]["teams"]
            teams = [entry["team"] for entry in entries]
            logger.info("[espn_fetcher] fetch_teams: received %d teams", len(teams))
            return teams
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("[espn_fetcher] fetch_teams: unexpected response shape — %s", exc)
            return []

    def fetch_scoreboard(self, date: datetime.date) -> list[dict]:
        """
        Return all NBA events scheduled on *date*.

        Parameters
        ----------
        date:
            The calendar date to query.

        Returns
        -------
        list[dict]
            Raw ESPN ``events`` array.  Each event contains competition
            details, team participants, scores, and status.
        """
        date_str = date.strftime("%Y%m%d")
        url = _URL_SCOREBOARD.format(date=date_str)
        logger.info("[espn_fetcher] fetch_scoreboard(%s) → %s", date.isoformat(), url)
        data = self._get(url)
        try:
            events = data.get("events", [])
            logger.info(
                "[espn_fetcher] fetch_scoreboard(%s): %d event(s)",
                date.isoformat(),
                len(events),
            )
            return events
        except (KeyError, TypeError) as exc:
            logger.error("[espn_fetcher] fetch_scoreboard: unexpected response — %s", exc)
            return []

    def fetch_game_summary(self, espn_game_id: str) -> dict:
        """
        Return the full box score summary for a single game.

        Parameters
        ----------
        espn_game_id:
            The ESPN event ID (string), e.g. ``"401585063"``.

        Returns
        -------
        dict
            Raw ESPN summary payload.  Key sub-trees used downstream:
            ``boxscore.teams``, ``boxscore.players``,
            ``header.competitions[0].status``.  Returns ``{}`` on failure.
        """
        url = _URL_SUMMARY.format(event_id=espn_game_id)
        logger.info("[espn_fetcher] fetch_game_summary(%s) → %s", espn_game_id, url)
        try:
            return self._get(url)
        except Exception as exc:
            logger.error(
                "[espn_fetcher] fetch_game_summary(%s) failed: %s", espn_game_id, exc
            )
            return {}

    def fetch_team_roster(self, espn_team_id: str) -> list[dict]:
        """
        Return the current roster for a team.

        Parameters
        ----------
        espn_team_id:
            ESPN team ID as a string, e.g. ``"13"`` (Miami Heat).

        Returns
        -------
        list[dict]
            Flat list of athlete objects.  Each dict contains ``id``,
            ``displayName``, ``position``, and ``active`` status.
            Returns ``[]`` on failure.
        """
        url = _URL_ROSTER.format(team_id=espn_team_id)
        logger.info("[espn_fetcher] fetch_team_roster(team=%s) → %s", espn_team_id, url)
        data = self._get(url)
        try:
            # ESPN roster endpoint returns a flat list of athlete objects directly
            # under the "athletes" key (not grouped by position with "items").
            raw_athletes = data.get("athletes", [])
            athletes: list[dict] = []
            for entry in raw_athletes:
                if isinstance(entry, dict):
                    # Flat athlete object (current ESPN shape)
                    if "id" in entry:
                        athletes.append(entry)
                    else:
                        # Legacy grouped shape: {"position": "guards", "items": [...]}
                        for item in entry.get("items", []):
                            athletes.append(item)
            logger.info(
                "[espn_fetcher] fetch_team_roster(team=%s): %d player(s)",
                espn_team_id,
                len(athletes),
            )
            return athletes
        except (KeyError, TypeError) as exc:
            logger.error(
                "[espn_fetcher] fetch_team_roster(team=%s): unexpected shape — %s",
                espn_team_id,
                exc,
            )
            return []

    def fetch_team_schedule(self, espn_team_id: str, season_year: int) -> list[dict]:
        """
        Return every game in a team's schedule for the given season.

        Parameters
        ----------
        espn_team_id:
            ESPN team ID as a string.
        season_year:
            The *ending* year of the season, e.g. ``2025`` for 2024-25,
            ``2026`` for 2025-26.

        Returns
        -------
        list[dict]
            Raw ESPN event objects from ``events`` array.
        """
        url = _URL_SCHEDULE.format(team_id=espn_team_id, year=season_year)
        logger.info(
            "[espn_fetcher] fetch_team_schedule(team=%s, season=%d) → %s",
            espn_team_id,
            season_year,
            url,
        )
        data = self._get(url)
        try:
            events = data.get("events", [])
            logger.info(
                "[espn_fetcher] fetch_team_schedule(team=%s, season=%d): %d event(s)",
                espn_team_id,
                season_year,
                len(events),
            )
            return events
        except (KeyError, TypeError) as exc:
            logger.error(
                "[espn_fetcher] fetch_team_schedule(team=%s): unexpected shape — %s",
                espn_team_id,
                exc,
            )
            return []

    def fetch_season_games(self, season_year: int) -> list[dict]:
        """
        Return all unique games across every NBA team for a full season.

        Iterates over all 30 teams, calls ``fetch_team_schedule`` for each,
        and de-duplicates events by ESPN event ID — ESPN lists each game
        under both the home and away team.

        Parameters
        ----------
        season_year:
            Ending year of the NBA season (e.g. ``2026`` for 2025-26).

        Returns
        -------
        list[dict]
            De-duplicated list of raw ESPN event objects, suitable for
            passing to ``espn_transformer.transform_game``.
        """
        logger.info(
            "[espn_fetcher] fetch_season_games(season=%d): fetching teams first", season_year
        )
        raw_teams = self.fetch_teams()
        if not raw_teams:
            logger.error("[espn_fetcher] fetch_season_games: no teams returned, aborting")
            return []

        seen_event_ids: set[str] = set()
        all_events: list[dict] = []

        for team in raw_teams:
            team_id = str(team.get("id", ""))
            team_abbr = team.get("abbreviation", team_id)
            if not team_id:
                logger.warning("[espn_fetcher] fetch_season_games: team missing id, skipping")
                continue

            events = self.fetch_team_schedule(team_id, season_year)
            new_count = 0
            for event in events:
                event_id = str(event.get("id", ""))
                if not event_id or event_id in seen_event_ids:
                    continue
                seen_event_ids.add(event_id)
                all_events.append(event)
                new_count += 1

            logger.info(
                "[espn_fetcher] fetch_season_games: team %s contributed %d new event(s) "
                "(%d total unique so far)",
                team_abbr,
                new_count,
                len(all_events),
            )

        logger.info(
            "[espn_fetcher] fetch_season_games(season=%d): %d unique game(s) total",
            season_year,
            len(all_events),
        )
        return all_events

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_session(self) -> requests.Session:
        """
        Create a requests Session with connection-level retry for transient
        network errors (connection reset, read timeout).  HTTP-level retries
        (429, 503) are handled manually in ``_get`` to allow back-off sleeps.
        """
        session = requests.Session()
        # Retry on connection/read errors at the transport layer only;
        # HTTP error codes are handled in _get with proper sleep.
        adapter = HTTPAdapter(
            max_retries=Retry(
                total=2,
                backoff_factor=0.5,
                status_forcelist=[],  # We handle HTTP codes ourselves
                allowed_methods=["GET"],
            )
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (compatible; SportsAnalyticsPlatform/1.0; "
                    "+https://github.com/your-org/sports-analytics)"
                ),
                "Accept": "application/json",
            }
        )
        return session

    def _polite_sleep(self) -> None:
        """Sleep to respect the configured delay between requests."""
        elapsed = time.monotonic() - self._last_request_time
        base = self._delay
        jitter = random.uniform(-0.2 * base, 0.2 * base)
        target = max(0.0, base + jitter)
        remaining = target - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _get(self, url: str) -> dict[str, Any]:
        """
        Execute a GET request with polite delays and retry logic.

        Retries on HTTP 429 and 503 up to ``_MAX_RETRIES`` times using
        exponential back-off with jitter.  Raises ``requests.HTTPError``
        for any non-retryable 4xx/5xx after all attempts are exhausted.

        Parameters
        ----------
        url:
            Fully-qualified ESPN endpoint URL.

        Returns
        -------
        dict
            Parsed JSON response body.

        Raises
        ------
        requests.HTTPError
            If the request ultimately fails after retries.
        requests.Timeout
            If the request exceeds ``_REQUEST_TIMEOUT`` seconds.
        """
        last_exc: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            self._polite_sleep()
            try:
                response = self._session.get(url, timeout=_REQUEST_TIMEOUT)
                self._last_request_time = time.monotonic()

                if response.status_code in _RETRYABLE_STATUSES:
                    wait = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)) + random.uniform(0, 1)
                    logger.warning(
                        "[espn_fetcher] HTTP %d for %s (attempt %d/%d) — retrying in %.1fs",
                        response.status_code,
                        url,
                        attempt,
                        _MAX_RETRIES,
                        wait,
                    )
                    time.sleep(wait)
                    last_exc = requests.HTTPError(
                        f"HTTP {response.status_code}", response=response
                    )
                    continue

                response.raise_for_status()
                return response.json()

            except requests.Timeout as exc:
                wait = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "[espn_fetcher] Timeout for %s (attempt %d/%d) — retrying in %.1fs",
                    url,
                    attempt,
                    _MAX_RETRIES,
                    wait,
                )
                time.sleep(wait)
                last_exc = exc

            except requests.HTTPError as exc:
                # Non-retryable HTTP error (e.g. 404) — fail fast
                logger.error("[espn_fetcher] HTTP error for %s: %s", url, exc)
                raise

            except requests.RequestException as exc:
                wait = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "[espn_fetcher] Request error for %s (attempt %d/%d): %s — retrying in %.1fs",
                    url,
                    attempt,
                    _MAX_RETRIES,
                    exc,
                    wait,
                )
                time.sleep(wait)
                last_exc = exc

        logger.error(
            "[espn_fetcher] All %d attempts failed for %s: %s",
            _MAX_RETRIES,
            url,
            last_exc,
        )
        raise last_exc or RuntimeError(f"All retries exhausted for {url}")
