import { useState, useEffect, useCallback } from 'react'
import type { SystemStatus, BankrollSummary } from '../types'

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

export { fetchJSON }
