import { useState, useEffect, useCallback, useRef } from 'react'
import type {
  TableListResponse,
  TableRowsResponse,
  SqlQueryRequest,
  SqlQueryResponse,
  SavedNotebook,
  ScribbleView,
  ViewCreateRequest,
} from '../types'

const API_BASE = '/api/v1'

/** Key used by the legacy localStorage implementation — kept for one-time migration only. */
const _LEGACY_NOTEBOOKS_KEY = 'sai_scribble_notebooks'

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

// ── Saved Notebooks (PostgreSQL via API) ──────────────────────────────────────
//
// Notebooks are now persisted in the scribble_notebooks table in PostgreSQL.
// On first load, any notebooks found in the legacy localStorage key are
// automatically migrated to the server and removed from localStorage.

async function _migrateLegacyNotebooks(notebooks: SavedNotebook[]): Promise<void> {
  for (const nb of notebooks) {
    try {
      await apiFetch<SavedNotebook>('/scribble/notebooks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: nb.name,
          description: nb.description,
          sql: nb.sql,
        }),
      })
    } catch {
      // best-effort — skip individual failures
    }
  }
  localStorage.removeItem(_LEGACY_NOTEBOOKS_KEY)
}

export function useNotebooks() {
  const [notebooks, setNotebooks] = useState<SavedNotebook[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const list = await apiFetch<SavedNotebook[]>('/scribble/notebooks')
      setNotebooks(list)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  // Initial load + one-time localStorage migration
  useEffect(() => {
    const run = async () => {
      // Migrate legacy localStorage notebooks first (if any)
      try {
        const raw = localStorage.getItem(_LEGACY_NOTEBOOKS_KEY)
        if (raw) {
          const legacy = JSON.parse(raw) as SavedNotebook[]
          if (legacy.length > 0) {
            await _migrateLegacyNotebooks(legacy)
          } else {
            localStorage.removeItem(_LEGACY_NOTEBOOKS_KEY)
          }
        }
      } catch {
        // Ignore migration errors — they shouldn't block the main load
      }
      await refresh()
    }
    run()
  }, [refresh])

  const save = useCallback(
    async (name: string, description: string, sql: string): Promise<SavedNotebook> => {
      const nb = await apiFetch<SavedNotebook>('/scribble/notebooks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim() || 'Untitled',
          description: description.trim(),
          sql,
        }),
      })
      setNotebooks(prev => [nb, ...prev])
      return nb
    },
    []
  )

  const remove = useCallback(async (id: string) => {
    await apiFetch<void>(`/scribble/notebooks/${id}`, { method: 'DELETE' })
    setNotebooks(prev => prev.filter(nb => nb.id !== id))
  }, [])

  const update = useCallback(
    async (id: string, patch: Partial<Pick<SavedNotebook, 'name' | 'description'>>) => {
      const updated = await apiFetch<SavedNotebook>(`/scribble/notebooks/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      })
      setNotebooks(prev => prev.map(nb => (nb.id === id ? updated : nb)))
    },
    []
  )

  return { notebooks, loading, error, save, remove, update, refresh }
}

// ── Saved Views (PostgreSQL) ───────────────────────────────────────────────────
//
// Views are real PostgreSQL VIEWs in the public schema.  The hook exposes:
//  - views: current list
//  - create(name, description, sql): calls POST /scribble/views
//  - drop(name): calls DELETE /scribble/views/:name
//  - refresh(): re-fetches the list

export function useViews() {
  const [views, setViews] = useState<ScribbleView[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const list = await apiFetch<ScribbleView[]>('/scribble/views')
      setViews(list)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const create = useCallback(
    async (payload: ViewCreateRequest): Promise<ScribbleView> => {
      const view = await apiFetch<ScribbleView>('/scribble/views', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      setViews(prev => [...prev.filter(v => v.name !== view.name), view].sort((a, b) => a.name.localeCompare(b.name)))
      return view
    },
    []
  )

  const drop = useCallback(async (name: string) => {
    await apiFetch<void>(`/scribble/views/${encodeURIComponent(name)}`, { method: 'DELETE' })
    setViews(prev => prev.filter(v => v.name !== name))
  }, [])

  return { views, loading, error, create, drop, refresh }
}
