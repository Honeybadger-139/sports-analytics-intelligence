import { useState, useEffect, useCallback, useRef } from 'react'
import type {
  TableListResponse,
  TableRowsResponse,
  SqlQueryRequest,
  SqlQueryResponse,
  SavedNotebook,
} from '../types'

const API_BASE = '/api/v1'
const NOTEBOOKS_KEY = 'sai_scribble_notebooks'

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, options)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

// ── Table List ────────────────────────────────────────────────────────────────

export function useTableList(season = '2025-26') {
  const [data, setData] = useState<TableListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    try {
      const result = await apiFetch<TableListResponse>(
        `/raw/tables?season=${encodeURIComponent(season)}`,
        { signal }
      )
      setData(result)
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setError((err as Error).message)
      }
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

// ── Table Rows ────────────────────────────────────────────────────────────────

export function useTableRows(
  tableName: string | null,
  season = '2025-26',
  limit = 50,
  offset = 0
) {
  const [data, setData] = useState<TableRowsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(
    async (signal?: AbortSignal) => {
      if (!tableName) return
      setLoading(true)
      setError(null)
      try {
        const params = new URLSearchParams({
          season,
          limit: String(limit),
          offset: String(offset),
        })
        const result = await apiFetch<TableRowsResponse>(
          `/raw/${tableName}?${params}`,
          { signal }
        )
        setData(result)
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          setError((err as Error).message)
          setData(null)
        }
      } finally {
        setLoading(false)
      }
    },
    [tableName, season, limit, offset]
  )

  useEffect(() => {
    const ctrl = new AbortController()
    load(ctrl.signal)
    return () => ctrl.abort()
  }, [load])

  return { data, loading, error, refresh: load }
}

// ── SQL Query ─────────────────────────────────────────────────────────────────

export function useSqlQuery() {
  const [result, setResult] = useState<SqlQueryResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const run = useCallback(async (sql: string) => {
    if (!sql.trim() || loading) return

    if (abortRef.current) abortRef.current.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const payload: SqlQueryRequest = { sql }
      const res = await apiFetch<SqlQueryResponse>('/scribble/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: ctrl.signal,
      })
      setResult(res)
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setError((err as Error).message)
      }
    } finally {
      setLoading(false)
    }
  }, [loading])

  const clear = useCallback(() => {
    if (abortRef.current) abortRef.current.abort()
    setResult(null)
    setError(null)
    setLoading(false)
  }, [])

  return { result, loading, error, run, clear }
}

// ── Saved Notebooks (localStorage) ───────────────────────────────────────────

function readNotebooks(): SavedNotebook[] {
  try {
    const raw = localStorage.getItem(NOTEBOOKS_KEY)
    return raw ? (JSON.parse(raw) as SavedNotebook[]) : []
  } catch {
    return []
  }
}

function writeNotebooks(notebooks: SavedNotebook[]) {
  localStorage.setItem(NOTEBOOKS_KEY, JSON.stringify(notebooks))
}

export function useNotebooks() {
  const [notebooks, setNotebooks] = useState<SavedNotebook[]>(readNotebooks)

  const save = useCallback((name: string, description: string, sql: string): SavedNotebook => {
    const nb: SavedNotebook = {
      id: crypto.randomUUID(),
      name: name.trim() || 'Untitled',
      description: description.trim(),
      sql,
      savedAt: new Date().toISOString(),
    }
    setNotebooks(prev => {
      const next = [nb, ...prev]
      writeNotebooks(next)
      return next
    })
    return nb
  }, [])

  const remove = useCallback((id: string) => {
    setNotebooks(prev => {
      const next = prev.filter(nb => nb.id !== id)
      writeNotebooks(next)
      return next
    })
  }, [])

  const update = useCallback((id: string, patch: Partial<Pick<SavedNotebook, 'name' | 'description'>>) => {
    setNotebooks(prev => {
      const next = prev.map(nb => nb.id === id ? { ...nb, ...patch } : nb)
      writeNotebooks(next)
      return next
    })
  }, [])

  return { notebooks, save, remove, update }
}
