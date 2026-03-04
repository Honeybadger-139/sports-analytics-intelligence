import { useState } from 'react'
import { motion } from 'framer-motion'
import { useQualityOverview } from '../../hooks/useApi'
import type { PipelineRun } from '../../types'

const ACCENT = '#7C3AED'
const SEASONS = ['2025-26', '2024-25', '2023-24']

function StatusPill({ status }: { status: string }) {
  const isSuccess = status === 'success'
  const isRunning = status === 'running'
  const color = isSuccess ? 'var(--success)' : isRunning ? 'var(--warning)' : 'var(--error)'
  const bg    = isSuccess ? 'rgba(0,214,143,0.10)' : isRunning ? 'rgba(255,177,0,0.10)' : 'rgba(255,76,106,0.10)'
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 9px', borderRadius: 20,
      background: bg, color, fontSize: '0.72rem', fontWeight: 700,
      fontFamily: 'var(--font-mono)', letterSpacing: '0.04em',
    }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: color, flexShrink: 0 }} />
      {status}
    </span>
  )
}

function ModuleBadge({ module }: { module: string }) {
  const isIngestion = module === 'ingestion'
  return (
    <span style={{
      padding: '2px 8px', borderRadius: 4,
      background: isIngestion ? 'rgba(139,92,246,0.12)' : 'rgba(6,197,248,0.10)',
      color: isIngestion ? ACCENT : '#06C5F8',
      fontSize: '0.72rem', fontWeight: 600, fontFamily: 'var(--font-mono)',
    }}>
      {module}
    </span>
  )
}

function fmtTime(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
  } catch {
    return iso
  }
}

function SummaryBar({ runs }: { runs: PipelineRun[] }) {
  const total   = runs.length
  const success = runs.filter(r => r.status === 'success').length
  const failed  = runs.filter(r => r.status === 'failed').length
  const ingestionRuns = runs.filter(r => r.module === 'ingestion')
  const featureRuns   = runs.filter(r => r.module === 'feature_store')

  const cards = [
    { label: 'Total Runs',   value: String(total),   color: 'var(--text-1)' },
    { label: 'Successful',   value: String(success),  color: 'var(--success)' },
    { label: 'Failed',       value: String(failed),   color: failed > 0 ? 'var(--error)' : 'var(--text-2)' },
    { label: 'Ingestion',    value: String(ingestionRuns.length), color: ACCENT },
    { label: 'Feature Store', value: String(featureRuns.length), color: '#06C5F8' },
  ]

  return (
    <div style={{ display: 'flex', gap: 10, marginBottom: 24, flexWrap: 'wrap' }}>
      {cards.map(c => (
        <div key={c.label} style={{
          background: 'var(--bg-panel)', border: '1px solid var(--border)',
          borderRadius: 'var(--r-sm)', padding: '10px 16px', minWidth: 110,
        }}>
          <p style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-2)', marginBottom: 4 }}>{c.label}</p>
          <p style={{ fontSize: '1.3rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: c.color, margin: 0 }}>{c.value}</p>
        </div>
      ))}
    </div>
  )
}

export default function PipelineRuns() {
  const [season,     setSeason]     = useState('2025-26')
  const [moduleFilter, setModuleFilter] = useState<'all' | 'ingestion' | 'feature_store'>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'success' | 'failed'>('all')

  const { data, loading, error, refresh } = useQualityOverview(season)

  const runs: PipelineRun[] = data?.recent_runs ?? []
  const filtered = runs.filter(r => {
    if (moduleFilter !== 'all' && r.module !== moduleFilter) return false
    if (statusFilter !== 'all' && r.status !== statusFilter) return false
    return true
  })

  return (
    <div style={{ padding: '28px 28px', maxWidth: 'var(--content-w)', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
        <select className="scribble-select" value={season} onChange={e => setSeason(e.target.value)}>
          {SEASONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>

        <select
          className="scribble-select"
          value={moduleFilter}
          onChange={e => setModuleFilter(e.target.value as typeof moduleFilter)}
        >
          <option value="all">All modules</option>
          <option value="ingestion">Ingestion</option>
          <option value="feature_store">Feature Store</option>
        </select>

        <select
          className="scribble-select"
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value as typeof statusFilter)}
        >
          <option value="all">All statuses</option>
          <option value="success">Success</option>
          <option value="failed">Failed</option>
        </select>

        {loading && <span style={{ fontSize: '0.78rem', color: 'var(--text-2)' }}>Loading…</span>}
        {error && <span style={{ fontSize: '0.78rem', color: 'var(--error)' }}>{error}</span>}

        <button
          onClick={() => refresh()}
          style={{
            marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6,
            padding: '7px 14px', background: 'var(--bg-panel)',
            border: `1px solid ${ACCENT}`, borderRadius: 'var(--r-sm)',
            color: ACCENT, fontSize: '0.78rem', fontWeight: 600, cursor: 'pointer',
          }}
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
            <path d="M10 6a4 4 0 1 1-1.07-2.72" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
            <path d="M10 2v2.5H7.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Refresh
        </button>
      </div>

      {/* Summary bar */}
      {runs.length > 0 && <SummaryBar runs={runs} />}

      {/* Run history table */}
      <p className="section-label" style={{ marginBottom: 12, color: ACCENT }}>
        Run History {filtered.length !== runs.length && `(${filtered.length} of ${runs.length})`}
      </p>

      <motion.div
        initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}
        style={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', overflow: 'hidden' }}
      >
        {!filtered.length ? (
          <p style={{ padding: '24px 20px', color: 'var(--text-2)', fontSize: '0.85rem' }}>
            {loading ? 'Loading run history…' : 'No pipeline runs match the current filters.'}
          </p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 680 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Time', 'Module', 'Status', 'Processed', 'Inserted', 'Elapsed', 'Errors'].map(h => (
                    <th key={h} style={{
                      padding: '10px 14px', textAlign: 'left',
                      fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase',
                      letterSpacing: '0.08em', color: 'var(--text-2)',
                      whiteSpace: 'nowrap',
                    }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((run, i) => (
                  <tr
                    key={i}
                    style={{ borderBottom: i < filtered.length - 1 ? '1px solid var(--border)' : 'none' }}
                  >
                    <td style={{ padding: '10px 14px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', whiteSpace: 'nowrap' }}>
                      {fmtTime(run.sync_time)}
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <ModuleBadge module={run.module} />
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <StatusPill status={run.status} />
                    </td>
                    <td style={{ padding: '10px 14px', fontSize: '0.82rem', fontFamily: 'var(--font-mono)', color: 'var(--text-1)', textAlign: 'right' }}>
                      {run.records_processed?.toLocaleString() ?? '—'}
                    </td>
                    <td style={{ padding: '10px 14px', fontSize: '0.82rem', fontFamily: 'var(--font-mono)', color: 'var(--success)', textAlign: 'right' }}>
                      {run.records_inserted?.toLocaleString() ?? '—'}
                    </td>
                    <td style={{ padding: '10px 14px', fontSize: '0.82rem', fontFamily: 'var(--font-mono)', color: ACCENT, textAlign: 'right', whiteSpace: 'nowrap' }}>
                      {run.elapsed_seconds != null ? `${run.elapsed_seconds.toFixed(1)}s` : '—'}
                    </td>
                    <td style={{ padding: '10px 14px', fontSize: '0.75rem', color: run.errors ? 'var(--error)' : 'var(--text-3)', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      title={run.errors ?? undefined}
                    >
                      {run.errors ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </motion.div>

      <p style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginTop: 10 }}>
        Showing last 50 runs from <code style={{ fontFamily: 'var(--font-mono)' }}>pipeline_audit</code>. Use Scribble → SQL Lab for deeper queries.
      </p>
    </div>
  )
}
