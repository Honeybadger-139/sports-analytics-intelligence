import { useQuery } from '@tanstack/react-query'
import { getApiBase } from '../config/api'
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
  PlayersListResponse,
  PlayerGameLogEntry,
  PlayerGameLogResponse,
  TeamGameLogEntry,
  TeamGameLogResponse,
} from '../types'

const API_BASE = getApiBase()

async function fetchJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { signal })
  if (!res.ok) {
    let detail = ''
    try {
      const payload = await res.json()
      if (typeof payload?.detail === 'string') detail = payload.detail
      else if (payload?.detail != null) detail = JSON.stringify(payload.detail)
      else detail = JSON.stringify(payload)
    } catch {
      try {
        detail = (await res.text()).trim()
      } catch {
        detail = ''
      }
    }
    throw new Error(detail ? `HTTP ${res.status}: ${detail}` : `HTTP ${res.status}`)
  }
  return res.json()
}

function useRefreshableQuery<T>(options: {
  queryKey: unknown[]
  path: string
  enabled?: boolean
  staleTime?: number
  refetchInterval?: number
  errorMessage?: string
}) {
  const query = useQuery({
    queryKey: options.queryKey,
    queryFn: ({ signal }) => fetchJSON<T>(options.path, signal),
    enabled: options.enabled,
    staleTime: options.staleTime,
    refetchInterval: options.refetchInterval,
  })

  return {
    data: (query.data ?? null) as T | null,
    loading: query.isLoading,
    error: query.isError
      ? (() => {
        const base = options.errorMessage ?? 'Request failed'
        const detail = query.error instanceof Error ? query.error.message : ''
        return detail ? `${base} (${detail})` : base
      })()
      : null,
    refresh: () => {
      void query.refetch()
    },
    disabled: false,
  }
}

export function useSystemStatus() {
  return useRefreshableQuery<SystemStatus>({
    queryKey: ['system-status'],
    path: '/system/status',
    refetchInterval: 60_000,
    staleTime: 30_000,
    errorMessage: 'Could not reach the API',
  })
}

export function useBankrollSummary(season = '2025-26') {
  const query = useQuery({
    queryKey: ['bankroll-summary', season],
    queryFn: ({ signal }) => fetchJSON<{ summary: BankrollSummary }>(`/bets/summary?season=${encodeURIComponent(season)}`, signal),
    staleTime: 60_000,
  })

  return { data: query.data?.summary ?? null, loading: query.isLoading }
}

export function useQualityOverview(season = '2025-26') {
  return useRefreshableQuery<QualityOverview>({
    queryKey: ['quality-overview', season],
    path: `/quality/overview?season=${encodeURIComponent(season)}&recent_limit=50`,
    staleTime: 60_000,
    errorMessage: 'Failed to load quality data',
  })
}

export function useMLOpsMonitoring(season = '2025-26') {
  const query = useQuery({
    queryKey: ['mlops-monitoring', season],
    queryFn: async ({ signal }) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const raw: any = await fetchJSON(`/mlops/monitoring?season=${encodeURIComponent(season)}`, signal)
      // API returns nested shape; flatten into MLOpsMonitoringOverview
      const firstAlert = raw.alerts?.[0]
      return {
        season:                    raw.season,
        evaluated_predictions:     raw.metrics?.evaluated_predictions ?? 0,
        accuracy:                  raw.metrics?.accuracy ?? null,
        brier_score:               raw.metrics?.brier_score ?? null,
        accuracy_threshold:        raw.thresholds?.accuracy_min ?? null,
        brier_threshold:           raw.thresholds?.brier_max ?? null,
        game_data_freshness_days:  raw.metrics?.game_data_freshness_days ?? null,
        pipeline_freshness_days:   raw.metrics?.pipeline_freshness_days ?? null,
        alert_count:               raw.escalation?.total_alerts ?? 0,
        escalation_level:          raw.escalation?.state ?? 'none',
        recommended_action:        firstAlert?.recommended_action ?? '',
        breach_streak:             firstAlert?.breach_streak ?? 0,
        alerts: (raw.alerts ?? []).map((a: any) => ({
          type:    a.id ?? 'alert',
          message: a.message,
          level:   a.severity === 'high' ? 'error' : a.severity === 'medium' ? 'warning' : 'info',
        })),
      } as MLOpsMonitoringOverview
    },
    staleTime: 15_000,
  })
  return {
    data:    query.data ?? null,
    loading: query.isLoading,
    error:   query.isError ? 'Failed to load MLOps monitoring' : null,
    refresh: () => { void query.refetch() },
  }
}

export function useMLOpsMonitoringTrend(season = '2025-26', days = 14) {
  const query = useQuery({
    queryKey: ['mlops-monitoring-trend', season, days],
    queryFn: ({ signal }) => fetchJSON<MLOpsMonitoringTrend>(`/mlops/monitoring/trend?season=${encodeURIComponent(season)}&days=${days}`, signal),
    staleTime: 60_000,
  })

  return { data: query.data ?? null, loading: query.isLoading }
}

export function useMLOpsRetrainPolicy(season = '2025-26') {
  return useRefreshableQuery<RetrainPolicyResult>({
    queryKey: ['mlops-retrain-policy', season],
    path: `/mlops/retrain/policy?season=${encodeURIComponent(season)}&dry_run=true`,
    staleTime: 15_000,
    errorMessage: 'Failed to load retrain policy',
  })
}

export function useMLOpsRetrainJobs(season = '2025-26') {
  const query = useQuery({
    queryKey: ['mlops-retrain-jobs', season],
    queryFn: ({ signal }) => fetchJSON<RetrainJobsResponse>(`/mlops/retrain/jobs?season=${encodeURIComponent(season)}&limit=20`, signal),
    staleTime: 5_000,
    refetchInterval: 5_000,
  })

  return { data: query.data ?? null, loading: query.isLoading }
}

export function useDailyBrief(season = '2025-26', briefDate?: string) {
  const query = useQuery({
    queryKey: ['daily-brief', season, briefDate ?? null],
    queryFn: ({ signal }) => {
      const dateParam = briefDate ? `&date=${briefDate}` : ''
      return fetchJSON<DailyBriefResponse>(`/intelligence/brief?season=${encodeURIComponent(season)}${dateParam}`, signal)
    },
    staleTime: 0,
  })

  const message = query.error instanceof Error ? query.error.message : ''
  const disabled = message.includes('503')
  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: query.isError
      ? (disabled ? 'Intelligence layer is disabled (INTELLIGENCE_ENABLED=false)' : 'Failed to load daily brief')
      : null,
    disabled,
    refresh: () => {
      void query.refetch()
    },
  }
}

export function useTodaysPredictions() {
  return useRefreshableQuery<TodayPredictionsResponse>({
    queryKey: ['todays-predictions'],
    path: '/predictions/today?persist=true',
    staleTime: 0,
    errorMessage: 'Failed to load predictions',
  })
}

export function useMatches(
  season = '2025-26',
  limit = 20,
  teamSearch?: string,
  date?: string,
  dateFrom?: string,
  dateTo?: string,
  completedOnly = false,
) {
  const query = useQuery({
    queryKey: ['matches', season, limit, teamSearch ?? '', date ?? '', dateFrom ?? '', dateTo ?? '', completedOnly],
    queryFn: ({ signal }) => {
      let url = `/matches?season=${encodeURIComponent(season)}&limit=${limit}`
      if (teamSearch) url += `&team_search=${encodeURIComponent(teamSearch)}`
      if (date) url += `&date=${encodeURIComponent(date)}`
      if (dateFrom) url += `&date_from=${encodeURIComponent(dateFrom)}`
      if (dateTo) url += `&date_to=${encodeURIComponent(dateTo)}`
      if (completedOnly) url += '&completed_only=true'
      return fetchJSON<MatchesResponse>(url, signal)
    },
    staleTime: 60_000,
  })

  return { data: query.data ?? null, loading: query.isLoading }
}

export function useGameStats(gameId: string | null) {
  const query = useQuery({
    queryKey: ['game-stats', gameId],
    queryFn: ({ signal }) => fetchJSON<GameStatsResponse>(`/matches/${gameId}/stats`, signal),
    enabled: Boolean(gameId),
    staleTime: 60_000,
  })

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: query.isError ? 'Failed to load game stats' : null,
  }
}

export function useGamePrediction(gameId: string | null) {
  const query = useQuery({
    queryKey: ['game-prediction', gameId],
    queryFn: ({ signal }) => fetchJSON<GamePredictionResponse>(`/predictions/game/${gameId}`, signal),
    enabled: Boolean(gameId),
    staleTime: 0,
  })

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: query.isError ? 'Failed to load prediction' : null,
  }
}

export function useModelPerformance(season = '2025-26') {
  return useRefreshableQuery<ModelPerformanceResponse>({
    queryKey: ['model-performance', season],
    path: `/predictions/performance?season=${encodeURIComponent(season)}`,
    staleTime: 0,
    errorMessage: 'Failed to load model performance',
  })
}

export function usePlayers(search: string, team?: string, limit = 50) {
  const normalizedSearch = search.trim().replace(/\s+/g, ' ')
  const enabled = normalizedSearch.length >= 2 || Boolean(team)
  const query = useQuery({
    queryKey: ['players', normalizedSearch, team ?? '', limit],
    queryFn: ({ signal }) => {
      let url = `/players?limit=${limit}`
      if (normalizedSearch.length >= 2) url += `&search=${encodeURIComponent(normalizedSearch)}`
      if (team) url += `&team=${encodeURIComponent(team)}`
      return fetchJSON<PlayersListResponse>(url, signal)
    },
    enabled,
    staleTime: 60_000,
  })

  return { data: query.data ?? null, loading: query.isLoading }
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
  const limit = filters.limit ?? 50
  const opponent = filters.opponent?.trim()
  const dateFrom = filters.dateFrom
  const dateTo = filters.dateTo

  const query = useQuery({
    queryKey: ['player-game-stats', playerId, seasons.join(','), limit, opponent ?? '', dateFrom ?? '', dateTo ?? ''],
    queryFn: async ({ signal }) => {
      const responses = await Promise.all(
        seasons.map(async (seasonValue) => {
          let url = `/players/${playerId}/game-stats?season=${encodeURIComponent(seasonValue)}&limit=${limit}`
          if (opponent) url += `&opponent=${encodeURIComponent(opponent)}`
          if (dateFrom) url += `&date_from=${encodeURIComponent(dateFrom)}`
          if (dateTo) url += `&date_to=${encodeURIComponent(dateTo)}`
          return fetchJSON<PlayerGameLogResponse>(url, signal)
        }),
      )

      if (!responses.length) return null

      const games = responses
        .flatMap(r => r.games)
        .sort((a, b) => String(b.game_date).localeCompare(String(a.game_date)))

      const averages = (() => {
        if (!games.length) return {}
        const keys: Array<keyof PlayerGameLogEntry> = ['points', 'rebounds', 'assists', 'steals', 'blocks', 'turnovers']
        const round1 = (value: number) => Math.round(value * 10) / 10
        const acc: Record<string, number> = { games_played: games.length }
        for (const key of keys) {
          const sum = games.reduce((total, game) => total + Number(game[key] ?? 0), 0)
          acc[String(key)] = round1(sum / games.length)
        }
        return acc
      })()

      return {
        player: responses[0].player,
        season: seasons.length === 1 ? seasons[0] : seasons.join(','),
        averages,
        games,
      } as PlayerGameLogResponse
    },
    enabled: Boolean(playerId) && seasons.length > 0,
    staleTime: 60_000,
  })

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: query.isError ? 'Failed to load player stats' : null,
  }
}

export function useTeamGameStats(abbreviation: string | null, seasons: string[] = ['2025-26'], limit = 50) {
  const query = useQuery({
    queryKey: ['team-game-stats', abbreviation, seasons.join(','), limit],
    queryFn: async ({ signal }) => {
      const responses = await Promise.all(
        seasons.map((seasonValue) =>
          fetchJSON<TeamGameLogResponse>(
            `/teams/${encodeURIComponent(abbreviation as string)}/game-stats?season=${encodeURIComponent(seasonValue)}&limit=${limit}`,
            signal,
          ),
        ),
      )

      if (!responses.length) return null

      const games = responses
        .flatMap(r => r.games)
        .sort((a, b) => String(b.game_date).localeCompare(String(a.game_date)))

      const wins = games.filter(g => g.result === 'W').length
      const losses = games.filter(g => g.result === 'L').length

      return {
        team: responses[0].team,
        season: seasons.length === 1 ? seasons[0] : seasons.join(','),
        record: { wins, losses, games: games.length },
        games: games as TeamGameLogEntry[],
      } as TeamGameLogResponse
    },
    enabled: Boolean(abbreviation) && seasons.length > 0,
    staleTime: 60_000,
  })

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: query.isError ? 'Failed to load team stats' : null,
  }
}

export function useTeamsList() {
  const query = useQuery({
    queryKey: ['teams-list'],
    queryFn: ({ signal }) => fetchJSON<{ teams: Array<{ team_id: number; abbreviation: string; full_name: string; city: string }>; count: number }>('/teams', signal),
    staleTime: 60_000,
  })

  return { data: query.data ?? null, loading: query.isLoading }
}

// ── Phase 6.4 Statistics API ──────────────────────────────────────────────────

export function useTeamRatings(season = '2025-26', topN = 30) {
  return useRefreshableQuery<import('../types').TeamRatingsResponse>({
    queryKey: ['team-ratings', season, topN],
    path: `/stats/team-ratings?season=${encodeURIComponent(season)}&top_n=${topN}`,
    staleTime: 300_000,  // 5 min — ratings don't change after every game
    errorMessage: 'Failed to load team ratings',
  })
}

export function useHomeCourtEffect() {
  return useRefreshableQuery<import('../types').HomeCourtEffectResponse>({
    queryKey: ['home-court-effect'],
    path: '/stats/home-court-effect',
    staleTime: 3_600_000, // 1 hour — historical analysis, rarely changes
    errorMessage: 'Failed to load home court effect',
  })
}

// ── Phase 6.5 Time-Series Forecast API ────────────────────────────────────────

export function useTeamForecast(teamName: string | null, season = '2025-26') {
  return useRefreshableQuery<import('../types').TeamForecastResponse>({
    queryKey: ['team-forecast', teamName, season],
    path: `/forecast/${encodeURIComponent(teamName ?? '')}?season=${encodeURIComponent(season)}`,
    enabled: Boolean(teamName),
    staleTime: 300_000,
    errorMessage: `Failed to load forecast for ${teamName}`,
  })
}

export function useLeagueMomentum(season = '2025-26') {
  return useRefreshableQuery<import('../types').LeagueMomentumResponse>({
    queryKey: ['league-momentum', season],
    path: `/forecast/league/momentum?season=${encodeURIComponent(season)}`,
    staleTime: 300_000,
    errorMessage: 'Failed to load league momentum',
  })
}

export { fetchJSON }
