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
      .catch(() => {})
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
      .catch(() => {})
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
      .catch(() => {})
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

export function useMatches(season = '2025-26', limit = 20) {
  const [data, setData] = useState<MatchesResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const ctrl = new AbortController()
    fetchJSON<MatchesResponse>(
      `/matches?season=${encodeURIComponent(season)}&limit=${limit}`,
      ctrl.signal,
    )
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [season, limit])

  return { data, loading }
}

// ── Arena hooks ───────────────────────────────────────────────────────────────

export function useGamePrediction(gameId: string | null) {
  const [data, setData] = useState<GamePredictionResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!gameId) { setData(null); return }
    const ctrl = new AbortController()
    setLoading(true)
    setError(null)
    fetchJSON<GamePredictionResponse>(`/predictions/game/${gameId}`, ctrl.signal)
      .then(setData)
      .catch(err => {
        if ((err as Error).name !== 'AbortError') setError('Failed to load prediction')
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

export { fetchJSON }
