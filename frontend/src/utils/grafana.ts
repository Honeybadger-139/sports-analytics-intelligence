type DashboardProvider = 'metabase' | 'grafana'

const DEFAULT_PROVIDER: DashboardProvider = 'metabase'

const DEFAULT_METABASE_URL = 'http://localhost:3000'
const DEFAULT_METABASE_CREATE_PATH = '/collection/root'
const DEFAULT_METABASE_LIBRARY_PATH = '/collection/root'

const DEFAULT_GRAFANA_URL = 'http://localhost:3301'
const DEFAULT_GRAFANA_CREATE_PATH = '/dashboard/new'

function normalizeBaseUrl(value: string): string {
  const trimmed = value.trim()
  return trimmed.endsWith('/') ? trimmed.slice(0, -1) : trimmed
}

function normalizePath(value: string): string {
  const trimmed = value.trim()
  if (!trimmed) return '/'
  return trimmed.startsWith('/') ? trimmed : `/${trimmed}`
}

function buildUrl(baseRaw: string, pathRaw: string): string {
  const base = normalizeBaseUrl(baseRaw)
  const path = normalizePath(pathRaw)
  return `${base}${path}`
}

export function getDashboardProvider(): DashboardProvider {
  const raw = String(import.meta.env.VITE_DASHBOARD_PROVIDER || DEFAULT_PROVIDER).trim().toLowerCase()
  return raw === 'grafana' ? 'grafana' : 'metabase'
}

export function getDashboardToolLabel(): 'Metabase' | 'Grafana' {
  return getDashboardProvider() === 'grafana' ? 'Grafana' : 'Metabase'
}

export function getDashboardCreateUrl(): string {
  if (getDashboardProvider() === 'grafana') {
    return buildUrl(
      import.meta.env.VITE_GRAFANA_URL || DEFAULT_GRAFANA_URL,
      import.meta.env.VITE_GRAFANA_CREATE_PATH || DEFAULT_GRAFANA_CREATE_PATH,
    )
  }
  return buildUrl(
    import.meta.env.VITE_METABASE_URL || DEFAULT_METABASE_URL,
    import.meta.env.VITE_METABASE_CREATE_PATH || DEFAULT_METABASE_CREATE_PATH,
  )
}

export function getDashboardLibraryUrl(): string {
  if (getDashboardProvider() === 'grafana') {
    return normalizeBaseUrl(import.meta.env.VITE_GRAFANA_URL || DEFAULT_GRAFANA_URL)
  }
  return buildUrl(
    import.meta.env.VITE_METABASE_URL || DEFAULT_METABASE_URL,
    import.meta.env.VITE_METABASE_LIBRARY_PATH || DEFAULT_METABASE_LIBRARY_PATH,
  )
}

export function getDashboardPresetUrls(): {
  prediction: string | null
  pipeline: string | null
  standings: string | null
  players: string | null
  matches: string | null
} {
  if (getDashboardProvider() === 'grafana') {
    const prediction = String(import.meta.env.VITE_GRAFANA_DASHBOARD_PREDICTION_URL || '').trim()
    const pipeline = String(import.meta.env.VITE_GRAFANA_DASHBOARD_PIPELINE_URL || '').trim()
    return { prediction: prediction || null, pipeline: pipeline || null, standings: null, players: null, matches: null }
  }

  // Prefer public URLs (no login required). Fall back to ID-based URLs if not set.
  const base = normalizeBaseUrl(import.meta.env.VITE_METABASE_URL || DEFAULT_METABASE_URL)
  const pub = (pubKey: string, idKey: string) => {
    const publicUrl = String(import.meta.env[pubKey] || '').trim()
    if (publicUrl) return publicUrl
    const id = String(import.meta.env[idKey] || '').trim()
    return id ? `${base}/dashboard/${id}` : null
  }

  return {
    standings:  pub('VITE_METABASE_PUBLIC_STANDINGS',  'VITE_METABASE_DASHBOARD_STANDINGS_ID'),
    players:    pub('VITE_METABASE_PUBLIC_PLAYERS',    'VITE_METABASE_DASHBOARD_PLAYERS_ID'),
    matches:    pub('VITE_METABASE_PUBLIC_MATCHES',    'VITE_METABASE_DASHBOARD_MATCHES_ID'),
    prediction: pub('VITE_METABASE_PUBLIC_PREDICTION', 'VITE_METABASE_DASHBOARD_PREDICTION_ID'),
    pipeline:   pub('VITE_METABASE_PUBLIC_PIPELINE',   'VITE_METABASE_DASHBOARD_PIPELINE_ID'),
  }
}

// Backward-compatible export retained so existing components do not need rewiring.
export function getGrafanaCreateDashboardUrl(): string {
  return getDashboardCreateUrl()
}

// Backward-compatible export retained so existing components do not need rewiring.
export function openGrafanaCreateDashboard(target: '_blank' | '_self' = '_blank'): string {
  const url = getDashboardCreateUrl()
  if (typeof window !== 'undefined') {
    window.open(url, target, target === '_blank' ? 'noopener,noreferrer' : undefined)
  }
  return url
}
