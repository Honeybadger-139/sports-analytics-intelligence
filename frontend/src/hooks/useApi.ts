import { useState, useEffect, useCallback } from 'react'
import type {
  SystemStatus,
  BankrollSummary,
  QualityOverview,
  MLOpsMonitoringOverview,
  MLOpsMonitoringTrend,
  RetrainPolicyResult,
  RetrainJobsResponse,
  DailyBriefResponse,
  MatchesResponse,
  TodayPredictionsResponse,
  GamePredictionResponse,
  ModelPerformanceResponse,
  GameStatsResponse,
} from '../types'

const API_BASE = '/api/v1'

async function fetchJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { signal })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export function useSystemStatus() {
  const [data, setData] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchJSON<SystemStatus>('/system/status', signal)
      setData(result)
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setError('Could not reach the API')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const ctrl = new AbortController()
    load(ctrl.signal)
    const interval = setInterval(() => load(ctrl.signal), 60_000)
    return () => {
      ctrl.abort()
      clearInterval(interval)
    }
  }, [load])

  return { data, loading, error, refresh: load }
}

export function useBankrollSummary(season = '2025-26') {
  const [data, setData] = useState<BankrollSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const ctrl = new AbortController()
    fetchJSON<{ summary: BankrollSummary }>(
      `/bets/summary?season=${encodeURIComponent(season)}`,
      ctrl.signal
    )
      .then(res => setData(res.summary))
      .catch(() => { })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [season])

  return { data, loading }
}

// ── Lab hooks ────────────────────────────────────────────────────────────────

export function useQualityOverview(season = '2025-26') {
  const [data, setData] = useState<QualityOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchJSON<QualityOverview>(
        `/quality/overview?season=${encodeURIComponent(season)}&recent_limit=50`,
        signal,
      )
      setData(result)
    } catch (err) {
      if ((err as Error).name !== 'AbortError') setError('Failed to load quality data')
    } finally {
      setLoading(false)
    }
  }, [season])

  useEffect(() => {
    const ctrl = new AbortController()
    load(ctrl.signal)
    return () => ctrl.abort()
  }, [load])

  return { data, loading, error, refresh: load }
}

export function useMLOpsMonitoring(season = '2025-26') {
  const [data, setData] = useState<MLOpsMonitoringOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchJSON<MLOpsMonitoringOverview>(
        `/mlops/monitoring?season=${encodeURIComponent(season)}`,
        signal,
      )
      setData(result)
    } catch (err) {
      if ((err as Error).name !== 'AbortError') setError('Failed to load MLOps monitoring')
    } finally {
      setLoading(false)
    }
  }, [season])

  useEffect(() => {
    const ctrl = new AbortController()
    load(ctrl.signal)
    return () => ctrl.abort()
  }, [load])

  return { data, loading, error, refresh: load }
}

export function useMLOpsMonitoringTrend(season = '2025-26', days = 14) {
  const [data, setData] = useState<MLOpsMonitoringTrend | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const ctrl = new AbortController()
    fetchJSON<MLOpsMonitoringTrend>(
      `/mlops/monitoring/trend?season=${encodeURIComponent(season)}&days=${days}`,
      ctrl.signal,
    )
      .then(setData)
      .catch(() => { })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [season, days])

  return { data, loading }
}

export function useMLOpsRetrainPolicy(season = '2025-26') {
  const [data, setData] = useState<RetrainPolicyResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchJSON<RetrainPolicyResult>(
        `/mlops/retrain/policy?season=${encodeURIComponent(season)}&dry_run=true`,
        signal,
      )
      setData(result)
    } catch (err) {
      if ((err as Error).name !== 'AbortError') setError('Failed to load retrain policy')
    } finally {
      setLoading(false)
    }
  }, [season])

  useEffect(() => {
    const ctrl = new AbortController()
    load(ctrl.signal)
    return () => ctrl.abort()
  }, [load])

  return { data, loading, error, refresh: load }
}

export function useMLOpsRetrainJobs(season = '2025-26') {
  const [data, setData] = useState<RetrainJobsResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const ctrl = new AbortController()
    fetchJSON<RetrainJobsResponse>(
      `/mlops/retrain/jobs?season=${encodeURIComponent(season)}&limit=20`,
      ctrl.signal,
    )
      .then(setData)
      .catch(() => { })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [season])

  return { data, loading }
}

// ── Pulse hooks ───────────────────────────────────────────────────────────────

export function useDailyBrief(season = '2025-26', briefDate?: string) {
  const [data, setData] = useState<DailyBriefResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [disabled, setDisabled] = useState(false)

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    try {
      const dateParam = briefDate ? `&date=${briefDate}` : ''
      const result = await fetchJSON<DailyBriefResponse>(
        `/intelligence/brief?season=${encodeURIComponent(season)}${dateParam}`,
        signal,
      )
      setData(result)
    } catch (err) {
      if ((err as Error).name === 'AbortError') return
      const msg = (err as Error).message ?? ''
      if (msg.includes('503')) {
        setDisabled(true)
        setError('Intelligence layer is disabled (INTELLIGENCE_ENABLED=false)')
      } else {
        setError('Failed to load daily brief')
      }
    } finally {
      setLoading(false)
    }
  }, [season, briefDate])

  useEffect(() => {
    const ctrl = new AbortController()
    load(ctrl.signal)
    return () => ctrl.abort()
  }, [load])

  return { data, loading, error, disabled, refresh: load }
}

export function useTodaysPredictions() {
  const [data, setData] = useState<TodayPredictionsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchJSON<TodayPredictionsResponse>('/predictions/today?persist=false', signal)
      setData(result)
    } catch (err) {
      if ((err as Error).name !== 'AbortError') setError('Failed to load predictions')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const ctrl = new AbortController()
    load(ctrl.signal)
    return () => ctrl.abort()
  }, [load])

  return { data, loading, error, refresh: load }
}

export function useMatches(
  season = '2025-26',
  limit = 20,
  teamSearch?: string,
  date?: string,
  dateFrom?: string,
  dateTo?: string,
) {
  const [data, setData] = useState<MatchesResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const ctrl = new AbortController()
    let url = `/matches?season=${encodeURIComponent(season)}&limit=${limit}`
    if (teamSearch) url += `&team_search=${encodeURIComponent(teamSearch)}`
    if (date) url += `&date=${encodeURIComponent(date)}`
    if (dateFrom) url += `&date_from=${encodeURIComponent(dateFrom)}`
    if (dateTo) url += `&date_to=${encodeURIComponent(dateTo)}`
    fetchJSON<MatchesResponse>(url, ctrl.signal)
      .then(setData)
      .catch(() => { })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [season, limit, teamSearch, date, dateFrom, dateTo])

  return { data, loading }
}

export function useGameStats(gameId: string | null) {
  const [data, setData] = useState<GameStatsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!gameId) { setData(null); return }
    const ctrl = new AbortController()
    setLoading(true)
    setError(null)
    fetchJSON<GameStatsResponse>(`/matches/${gameId}/stats`, ctrl.signal)
      .then(setData)
      .catch(err => {
        if ((err as Error).name !== 'AbortError') setError('Failed to load game stats')
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [gameId])

  return { data, loading, error }
}

// ── Arena hooks ───────────────────────────────────────────────────────────────

export function useGamePrediction(gameId: string | null) {
  const [data, setData] = useState<GamePredictionResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!gameId) {
      setData(null)
      setError(null)
      setLoading(false)
      return
    }
    const ctrl = new AbortController()
    setLoading(true)
    setData(null)
    setError(null)
    fetchJSON<GamePredictionResponse>(`/predictions/game/${gameId}`, ctrl.signal)
      .then(setData)
      .catch(err => {
        if ((err as Error).name !== 'AbortError') {
          setData(null)
          setError('Failed to load prediction')
        }
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [gameId])

  return { data, loading, error }
}

export function useModelPerformance(season = '2025-26') {
  const [data, setData] = useState<ModelPerformanceResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchJSON<ModelPerformanceResponse>(
        `/predictions/performance?season=${encodeURIComponent(season)}`,
        signal,
      )
      setData(result)
    } catch (err) {
      if ((err as Error).name !== 'AbortError') setError('Failed to load model performance')
    } finally {
      setLoading(false)
    }
  }, [season])

  useEffect(() => {
    const ctrl = new AbortController()
    load(ctrl.signal)
    return () => ctrl.abort()
  }, [load])

  return { data, loading, error, refresh: load }
}

// ── Deep Dive hooks ──────────────────────────────────────────────────────────

import type {
  PlayersListResponse,
  PlayerGameLogEntry,
  PlayerGameLogResponse,
  TeamGameLogEntry,
  TeamGameLogResponse,
} from '../types'

export function usePlayers(search: string, team?: string, limit = 50) {
  const [data, setData] = useState<PlayersListResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const normalizedSearch = search.trim().replace(/\s+/g, ' ')

  useEffect(() => {
    const hasSearch = normalizedSearch.length >= 2
    if (!hasSearch && !team) { setData(null); setLoading(false); return }
    const ctrl = new AbortController()
    setLoading(true)
    let url = `/players?limit=${limit}`
    if (hasSearch) url += `&search=${encodeURIComponent(normalizedSearch)}`
    if (team) url += `&team=${encodeURIComponent(team)}`
    fetchJSON<PlayersListResponse>(url, ctrl.signal)
      .then(setData)
      .catch(() => { })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [normalizedSearch, team, limit])

  return { data, loading }
}

export interface PlayerGameStatsFilters {
  limit?: number
  opponent?: string
  dateFrom?: string
  dateTo?: string
}

export function usePlayerGameStats(
  playerId: number | null,
  seasons: string[] = ['2025-26'],
  filters: PlayerGameStatsFilters = {},
) {
  const [data, setData] = useState<PlayerGameLogResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const limit = filters.limit ?? 50
  const opponent = filters.opponent?.trim()
  const dateFrom = filters.dateFrom
  const dateTo = filters.dateTo

  useEffect(() => {
    if (!playerId) { setData(null); return }
    if (!seasons.length) { setData(null); return }
    const ctrl = new AbortController()
    setLoading(true)
    setError(null)
    Promise.all(
      seasons.map(async (seasonValue) => {
        let url = `/players/${playerId}/game-stats?season=${encodeURIComponent(seasonValue)}&limit=${limit}`
        if (opponent) url += `&opponent=${encodeURIComponent(opponent)}`
        if (dateFrom) url += `&date_from=${encodeURIComponent(dateFrom)}`
        if (dateTo) url += `&date_to=${encodeURIComponent(dateTo)}`
        return fetchJSON<PlayerGameLogResponse>(url, ctrl.signal)
      }),
    )
      .then((responses) => {
        if (!responses.length) {
          setData(null)
          return
        }

        const games = responses
          .flatMap(r => r.games)
          .sort((a, b) => String(b.game_date).localeCompare(String(a.game_date)))

        const averages = (() => {
          if (!games.length) return {}
          const keys: Array<keyof PlayerGameLogEntry> = ['points', 'rebounds', 'assists', 'steals', 'blocks', 'turnovers']
          const round1 = (value: number) => Math.round(value * 10) / 10
          const acc: Record<string, number> = { games_played: games.length }
          for (const key of keys) {
            const sum = games.reduce((total, g) => total + Number(g[key] ?? 0), 0)
            acc[String(key)] = round1(sum / games.length)
          }
          return acc
        })()

        setData({
          player: responses[0].player,
          season: seasons.length === 1 ? seasons[0] : seasons.join(','),
          averages,
          games,
        })
      })
      .catch(err => {
        if ((err as Error).name !== 'AbortError') setError('Failed to load player stats')
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [playerId, seasons, limit, opponent, dateFrom, dateTo])

  return { data, loading, error }
}

export function useTeamGameStats(abbreviation: string | null, seasons: string[] = ['2025-26'], limit = 50) {
  const [data, setData] = useState<TeamGameLogResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!abbreviation) { setData(null); return }
    if (!seasons.length) { setData(null); return }
    const ctrl = new AbortController()
    setLoading(true)
    setError(null)
    Promise.all(
      seasons.map((seasonValue) =>
        fetchJSON<TeamGameLogResponse>(
          `/teams/${encodeURIComponent(abbreviation)}/game-stats?season=${encodeURIComponent(seasonValue)}&limit=${limit}`,
          ctrl.signal,
        ),
      ),
    )
      .then((responses) => {
        if (!responses.length) {
          setData(null)
          return
        }

        const games = responses
          .flatMap(r => r.games)
          .sort((a, b) => String(b.game_date).localeCompare(String(a.game_date)))

        const wins = games.filter(g => g.result === 'W').length
        const losses = games.filter(g => g.result === 'L').length

        setData({
          team: responses[0].team,
          season: seasons.length === 1 ? seasons[0] : seasons.join(','),
          record: { wins, losses, games: games.length },
          games: games as TeamGameLogEntry[],
        })
      })
      .catch(err => {
        if ((err as Error).name !== 'AbortError') setError('Failed to load team stats')
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [abbreviation, seasons, limit])

  return { data, loading, error }
}

export function useTeamsList() {
  const [data, setData] = useState<{ teams: Array<{ team_id: number; abbreviation: string; full_name: string; city: string }>; count: number } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const ctrl = new AbortController()
    fetchJSON<typeof data>('/teams', ctrl.signal)
      .then(setData)
      .catch(() => { })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [])

  return { data, loading }
}

export { fetchJSON }
