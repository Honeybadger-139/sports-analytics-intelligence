import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  useMLOpsMonitoring,
  useMLOpsRetrainPolicy,
  useMLOpsRetrainJobs,
} from '../../hooks/useApi'
import type { RetrainJob, MLOpsAlert } from '../../types'

const ACCENT = '#7C3AED'
const SEASONS = ['2025-26', '2024-25', '2023-24']

function fmt(n: number | null | undefined, decimals = 3): string {
  if (n == null) return '—'
  return n.toFixed(decimals)
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return '—'
  return `${(n * 100).toFixed(1)}%`
}

function fmtTime(iso: string | null): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
  } catch {
    return iso
  }
}

function EscalationBadge({ level }: { level: string }) {
  const cfg: Record<string, { color: string; bg: string }> = {
    none:     { color: 'var(--success)',  bg: 'rgba(0,214,143,0.10)' },
    watch:    { color: 'var(--warning)',  bg: 'rgba(255,177,0,0.10)' },
    incident: { color: 'var(--error)',    bg: 'rgba(255,76,106,0.12)' },
  }
  const { color, bg } = cfg[level] ?? cfg.none
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '4px 12px', borderRadius: 20,
      background: bg, color, fontSize: '0.78rem', fontWeight: 700,
      fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.06em',
    }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: color }} />
      {level}
    </span>
  )
}

function AlertRow({ alert }: { alert: MLOpsAlert }) {
  const color = alert.level === 'error' ? 'var(--error)' : alert.level === 'warning' ? 'var(--warning)' : 'var(--text-2)'
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 10,
      padding: '12px 16px', borderBottom: '1px solid var(--border)',
    }}>
      <span style={{
        marginTop: 1, width: 20, height: 20, flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        borderRadius: 4, background: color === 'var(--error)' ? 'rgba(255,76,106,0.12)' : 'rgba(255,177,0,0.10)',
        color,
      }}>
        <svg width="11" height="11" viewBox="0 0 11 11" fill="none" aria-hidden>
          <path d="M5.5 1.5L9.5 9H1.5L5.5 1.5Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
          <line x1="5.5" y1="4.5" x2="5.5" y2="6.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
          <circle cx="5.5" cy="8" r="0.5" fill="currentColor"/>
        </svg>
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-1)', margin: '0 0 2px' }}>{alert.message}</p>
        <span style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color, fontWeight: 600, textTransform: 'uppercase' }}>{alert.type}</span>
      </div>
    </div>
  )
}

function MetricCard({
  label, value, threshold, better, unit = '',
}: {
  label: string; value: string; threshold?: string; better: 'higher' | 'lower'; unit?: string
}) {
  return (
    <div style={{
      background: 'var(--bg-panel)', border: '1px solid var(--border)',
      borderRadius: 'var(--r-md)', padding: '18px 20px',
    }}>
      <p style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-2)', marginBottom: 8 }}>
        {label}
      </p>
      <p style={{ fontSize: '1.7rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: 'var(--text-1)', lineHeight: 1, marginBottom: 6 }}>
        {value}{unit}
      </p>
      {threshold && (
        <p style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>
          {better === 'higher' ? '↑' : '↓'} threshold: {threshold}{unit}
        </p>
      )}
    </div>
  )
}

function JobStatusPill({ status }: { status: string }) {
  const cfg: Record<string, { color: string; bg: string }> = {
    queued:    { color: 'var(--warning)',  bg: 'rgba(255,177,0,0.10)' },
    running:   { color: '#06C5F8',        bg: 'rgba(6,197,248,0.10)' },
    completed: { color: 'var(--success)', bg: 'rgba(0,214,143,0.10)' },
    failed:    { color: 'var(--error)',   bg: 'rgba(255,76,106,0.12)' },
    canceled:  { color: 'var(--text-2)', bg: 'var(--bg-elevated)' },
  }
  const { color, bg } = cfg[status] ?? { color: 'var(--text-2)', bg: 'var(--bg-elevated)' }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 9px', borderRadius: 20,
      background: bg, color, fontSize: '0.72rem', fontWeight: 700,
      fontFamily: 'var(--font-mono)',
    }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: color }} />
      {status}
    </span>
  )
}

export default function MLOpsMonitor() {
  const [season, setSeason] = useState('2025-26')

  const { data: mon,    loading: monLoading,    error: monError,    refresh: refreshMon }    = useMLOpsMonitoring(season)
  const { data: policy, loading: policyLoading, error: policyError, refresh: refreshPolicy } = useMLOpsRetrainPolicy(season)
  const { data: jobs,   loading: jobsLoading }  = useMLOpsRetrainJobs(season)

  const isLoading = monLoading || policyLoading || jobsLoading
  const hasError  = monError || policyError

  function handleRefresh() { refreshMon(); refreshPolicy() }

  return (
    <div style={{ padding: '28px 28px', maxWidth: 'var(--content-w)', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 28, flexWrap: 'wrap' }}>
        <select className="scribble-select" value={season} onChange={e => setSeason(e.target.value)}>
          {SEASONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        {isLoading && <span style={{ fontSize: '0.78rem', color: 'var(--text-2)' }}>Loading…</span>}
        {hasError && <span style={{ fontSize: '0.78rem', color: 'var(--error)' }}>Some data failed to load</span>}
        <button
          onClick={handleRefresh}
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

      {/* ── Escalation status ── */}
      {mon && (
        <motion.div
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          style={{
            background: 'var(--bg-panel)', border: '1px solid var(--border)',
            borderRadius: 'var(--r-md)', padding: '18px 22px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            flexWrap: 'wrap', gap: 12, marginBottom: 24,
          }}
        >
          <div>
            <p style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-2)', marginBottom: 6 }}>Escalation State</p>
            <EscalationBadge level={mon.escalation_level} />
          </div>
          <div>
            <p style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-2)', marginBottom: 4 }}>Recommended Action</p>
            <p style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--text-1)' }}>{mon.recommended_action?.replace(/_/g, ' ')}</p>
          </div>
          <div>
            <p style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-2)', marginBottom: 4 }}>Breach Streak</p>
            <p style={{ fontSize: '1.2rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: mon.breach_streak > 0 ? 'var(--warning)' : 'var(--success)' }}>
              {mon.breach_streak}
            </p>
          </div>
          <div>
            <p style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-2)', marginBottom: 4 }}>Active Alerts</p>
            <p style={{ fontSize: '1.2rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: mon.alert_count > 0 ? 'var(--error)' : 'var(--success)' }}>
              {mon.alert_count}
            </p>
          </div>
        </motion.div>
      )}

      {/* ── Model metrics ── */}
      <p className="section-label" style={{ marginBottom: 12, color: ACCENT }}>Model Metrics</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 10, marginBottom: 28 }}>
        <MetricCard
          label="Accuracy"
          value={fmtPct(mon?.accuracy)}
          threshold={fmtPct(mon?.accuracy_threshold)}
          better="higher"
        />
        <MetricCard
          label="Brier Score"
          value={fmt(mon?.brier_score)}
          threshold={fmt(mon?.brier_threshold)}
          better="lower"
        />
        <MetricCard
          label="Evaluated Predictions"
          value={mon?.evaluated_predictions?.toLocaleString() ?? '—'}
          better="higher"
        />
        <MetricCard
          label="Data Freshness"
          value={mon?.game_data_freshness_days != null ? String(mon.game_data_freshness_days) : '—'}
          better="lower"
          unit=" days"
        />
        <MetricCard
          label="Pipeline Freshness"
          value={mon?.pipeline_freshness_days != null ? String(mon.pipeline_freshness_days) : '—'}
          better="lower"
          unit=" days"
        />
      </div>

      {/* ── Active alerts ── */}
      <p className="section-label" style={{ marginBottom: 12, color: ACCENT }}>
        Active Alerts {mon?.alert_count != null && `(${mon.alert_count})`}
      </p>
      <div style={{
        background: 'var(--bg-panel)', border: '1px solid var(--border)',
        borderRadius: 'var(--r-md)', marginBottom: 28, overflow: 'hidden',
      }}>
        {!mon?.alerts?.length ? (
          <p style={{ padding: '20px 16px', color: mon ? 'var(--success)' : 'var(--text-2)', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: 8 }}>
            {mon
              ? <><svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden><circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.3"/><path d="M4.5 7L6.5 9L9.5 5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg>No active alerts — model is within thresholds.</>
              : 'Loading alerts…'}
          </p>
        ) : (
          <div>
            {mon.alerts.map((alert, i) => (
              <div key={i} style={{ borderBottom: i < mon.alerts.length - 1 ? '1px solid var(--border)' : 'none' }}>
                <AlertRow alert={alert} />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Retrain policy ── */}
      <p className="section-label" style={{ marginBottom: 12, color: ACCENT }}>Retrain Policy (Dry Run)</p>
      <div style={{
        background: 'var(--bg-panel)', border: '1px solid var(--border)',
        borderRadius: 'var(--r-md)', padding: '18px 20px', marginBottom: 28,
      }}>
        {policyLoading ? (
          <p style={{ color: 'var(--text-2)', fontSize: '0.85rem' }}>Evaluating policy…</p>
        ) : policyError ? (
          <p style={{ color: 'var(--error)', fontSize: '0.85rem' }}>{policyError}</p>
        ) : policy ? (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                padding: '5px 14px', borderRadius: 20,
                background: policy.should_retrain ? 'rgba(255,177,0,0.12)' : 'rgba(0,214,143,0.10)',
                color: policy.should_retrain ? 'var(--warning)' : 'var(--success)',
                fontSize: '0.82rem', fontWeight: 700,
              }}>
                {policy.should_retrain ? '⚡ Retrain recommended' : '✓ No retrain needed'}
              </span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>dry_run = true</span>
            </div>

            {policy.reasons?.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <p style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>Trigger Reasons</p>
                <ul style={{ margin: 0, padding: '0 0 0 16px', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {policy.reasons.map((r, i) => (
                    <li key={i} style={{ fontSize: '0.82rem', color: 'var(--warning)' }}>{r}</li>
                  ))}
                </ul>
              </div>
            )}

            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
              <div>
                <p style={{ fontSize: '0.68rem', color: 'var(--text-2)', marginBottom: 2 }}>Accuracy</p>
                <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-1)' }}>{fmtPct(policy.accuracy)}</p>
              </div>
              <div>
                <p style={{ fontSize: '0.68rem', color: 'var(--text-2)', marginBottom: 2 }}>Brier Score</p>
                <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-1)' }}>{fmt(policy.brier_score)}</p>
              </div>
              <div>
                <p style={{ fontSize: '0.68rem', color: 'var(--text-2)', marginBottom: 2 }}>New Labels Since Last Train</p>
                <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-1)' }}>{policy.new_labels_since_last_train}</p>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      {/* ── Retrain job queue ── */}
      <p className="section-label" style={{ marginBottom: 12, color: ACCENT }}>
        Retrain Job Queue {jobs?.jobs?.length != null && `(${jobs.jobs.length})`}
      </p>
      <div style={{
        background: 'var(--bg-panel)', border: '1px solid var(--border)',
        borderRadius: 'var(--r-md)', overflow: 'hidden',
      }}>
        {jobsLoading ? (
          <p style={{ padding: '20px 16px', color: 'var(--text-2)', fontSize: '0.85rem' }}>Loading job queue…</p>
        ) : !jobs?.jobs?.length ? (
          <p style={{ padding: '20px 16px', color: 'var(--text-2)', fontSize: '0.85rem' }}>No retrain jobs on record for this season.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 580 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['ID', 'Status', 'Trigger', 'Created', 'Started', 'Completed', 'Reasons'].map(h => (
                    <th key={h} style={{
                      padding: '10px 14px', textAlign: 'left',
                      fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase',
                      letterSpacing: '0.08em', color: 'var(--text-2)', whiteSpace: 'nowrap',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(jobs.jobs as RetrainJob[]).map((job, i) => (
                  <tr key={job.id} style={{ borderBottom: i < jobs.jobs.length - 1 ? '1px solid var(--border)' : 'none' }}>
                    <td style={{ padding: '10px 14px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-3)' }}>#{job.id}</td>
                    <td style={{ padding: '10px 14px' }}><JobStatusPill status={job.status} /></td>
                    <td style={{ padding: '10px 14px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>{job.trigger_source}</td>
                    <td style={{ padding: '10px 14px', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', whiteSpace: 'nowrap' }}>{fmtTime(job.created_at)}</td>
                    <td style={{ padding: '10px 14px', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', whiteSpace: 'nowrap' }}>{fmtTime(job.started_at)}</td>
                    <td style={{ padding: '10px 14px', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', whiteSpace: 'nowrap' }}>{fmtTime(job.completed_at)}</td>
                    <td style={{ padding: '10px 14px', fontSize: '0.75rem', color: 'var(--text-2)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      title={job.reasons?.join(', ')}
                    >
                      {job.reasons?.join(', ') ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
