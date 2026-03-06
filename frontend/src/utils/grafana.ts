const DEFAULT_GRAFANA_URL = 'http://localhost:3301'
const DEFAULT_GRAFANA_CREATE_PATH = '/dashboard/new'

function normalizeBaseUrl(value: string): string {
  const trimmed = value.trim()
  return trimmed.endsWith('/') ? trimmed.slice(0, -1) : trimmed
}

function normalizePath(value: string): string {
  const trimmed = value.trim()
  if (!trimmed) return DEFAULT_GRAFANA_CREATE_PATH
  return trimmed.startsWith('/') ? trimmed : `/${trimmed}`
}

export function getGrafanaCreateDashboardUrl(): string {
  const base = normalizeBaseUrl(import.meta.env.VITE_GRAFANA_URL || DEFAULT_GRAFANA_URL)
  const path = normalizePath(import.meta.env.VITE_GRAFANA_CREATE_PATH || DEFAULT_GRAFANA_CREATE_PATH)
  return `${base}${path}`
}

export function openGrafanaCreateDashboard(target: '_blank' | '_self' = '_blank'): string {
  const url = getGrafanaCreateDashboardUrl()
  if (typeof window !== 'undefined') {
    window.open(url, target, target === '_blank' ? 'noopener,noreferrer' : undefined)
  }
  return url
}
