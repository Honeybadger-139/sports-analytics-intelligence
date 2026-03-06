import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getGrafanaCreateDashboardUrl, openGrafanaCreateDashboard } from '../utils/grafana'

const ACCENT = '#D97706'

export default function DashboardCreate() {
  const navigate = useNavigate()
  const grafanaCreateUrl = getGrafanaCreateDashboardUrl()

  useEffect(() => {
    openGrafanaCreateDashboard('_self')
  }, [])

  return (
    <div className="page-shell">
      <div style={{ maxWidth: 760, margin: '0 auto', padding: '56px 28px', textAlign: 'center' }}>
        <p style={{ fontSize: '0.74rem', color: ACCENT, fontWeight: 700, letterSpacing: '0.09em', textTransform: 'uppercase', marginBottom: 8 }}>
          Redirecting To Grafana
        </p>
        <h1 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-1)', marginBottom: 10, fontFamily: 'var(--font-display)' }}>
          Open Grafana Dashboard Builder
        </h1>
        <p style={{ fontSize: '0.84rem', color: 'var(--text-2)', lineHeight: 1.5, marginBottom: 18 }}>
          If redirect did not trigger automatically, use the button below.
        </p>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 10, flexWrap: 'wrap' }}>
          <button
            onClick={() => openGrafanaCreateDashboard('_self')}
            style={{
              padding: '8px 14px',
              borderRadius: 'var(--r-sm)',
              border: `1px solid ${ACCENT}`,
              background: `${ACCENT}18`,
              color: ACCENT,
              fontSize: '0.78rem',
              fontWeight: 800,
              cursor: 'pointer',
            }}
          >
            Open Grafana
          </button>
          <button
            onClick={() => navigate('/dashboard')}
            style={{
              padding: '8px 14px',
              borderRadius: 'var(--r-sm)',
              border: '1px solid var(--border)',
              background: 'var(--bg-panel)',
              color: 'var(--text-2)',
              fontSize: '0.78rem',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Back to Dashboards
          </button>
        </div>
        <p style={{ marginTop: 14, fontSize: '0.72rem', color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
          {grafanaCreateUrl}
        </p>
      </div>
    </div>
  )
}
