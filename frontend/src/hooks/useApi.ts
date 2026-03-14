import { useQuery } from '@tanstack/react-query'
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

const API_BASE = '/api/v1'

async function fetchJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { signal })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
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
    error: query.isError ? (options.errorMessage ?? 'Request failed') : null,
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
  return useRefreshableQuery<MLOpsMonitoringOverview>({
    queryKey: ['mlops-monitoring', season],
    path: `/mlops/monitoring?season=${encodeURIComponent(season)}`,
    staleTime: 15_000,
    errorMessage: 'Failed to load MLOps monitoring',
  })
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
    path: '/predictions/today?persist=false',
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
) {
  const query = useQuery({
    queryKey: ['matches', season, limit, teamSearch ?? '', date ?? '', dateFrom ?? '', dateTo ?? ''],
    queryFn: ({ signal }) => {
      let url = `/matches?season=${encodeURIComponent(season)}&limit=${limit}`
      if (teamSearch) url += `&team_search=${encodeURIComponent(teamSearch)}`
      if (date) url += `&date=${encodeURIComponent(date)}`
      if (dateFrom) url += `&date_from=${encodeURIComponent(dateFrom)}`
      if (dateTo) url += `&date_to=${encodeURIComponent(dateTo)}`
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

export { fetchJSON }
