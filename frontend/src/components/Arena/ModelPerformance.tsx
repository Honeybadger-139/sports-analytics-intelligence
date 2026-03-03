import { useState } from 'react'
import { motion } from 'framer-motion'
import { useModelPerformance } from '../../hooks/useApi'
import type { ModelPerformanceItem } from '../../types'

const ACCENT   = '#06C5F8'
const SEASONS  = ['2025-26', '2024-25', '2023-24']

const MODEL_LABELS: Record<string, string> = {
  ensemble:            'Ensemble',
  xgboost:             'XGBoost',
  lgbm:                'LightGBM',
  logistic_regression: 'Logistic Regression',
}
const MODEL_COLORS: Record<string, string> = {
  ensemble:            '#06C5F8',
  xgboost:             '#8B5CF6',
  lgbm:                '#10B981',
  logistic_regression: '#FFB100',
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) }
  catch { return iso }
}

function AccuracyBar({ value, threshold = 0.55 }: { value: number; threshold?: number }) {
  const pct      = value * 100
  const aboveThreshold = value >= threshold
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
      <div style={{ flex: 1, height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden', position: 'relative' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: aboveThreshold ? 'var(--success)' : 'var(--warning)', borderRadius: 3, transition: 'width 0.5s ease' }} />
        {/* Threshold marker */}
        <div style={{ position: 'absolute', left: `${threshold * 100}%`, top: 0, bottom: 0, width: 1, background: 'var(--text-3)' }} />
      </div>
      <span style={{ fontSize: '0.78rem', fontFamily: 'var(--font-mono)', fontWeight: 700, color: aboveThreshold ? 'var(--success)' : 'var(--warning)', minWidth: 40 }}>
        {pct.toFixed(1)}%
      </span>
    </div>
  )
}

function BrierBar({ value, threshold = 0.25 }: { value: number; threshold?: number }) {
  const pct   = Math.min(value * 200, 100)
  const good  = value <= threshold
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
      <div style={{ flex: 1, height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: good ? 'var(--success)' : 'var(--error)', borderRadius: 3, transition: 'width 0.5s ease' }} />
      </div>
      <span style={{ fontSize: '0.78rem', fontFamily: 'var(--font-mono)', fontWeight: 700, color: good ? 'var(--success)' : 'var(--error)', minWidth: 44 }}>
        {value.toFixed(4)}
      </span>
    </div>
  )
}

function SummaryCard({ label, value, sub, color = 'var(--text-1)' }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div style={{
      background: 'var(--bg-panel)', border: '1px solid var(--border)',
      borderRadius: 'var(--r-md)', padding: '16px 18px',
    }}>
      <p style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-2)', marginBottom: 6 }}>{label}</p>
      <p style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '1.4rem', color, lineHeight: 1 }}>{value}</p>
      {sub && <p style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginTop: 4 }}>{sub}</p>}
    </div>
  )
}

export default function ModelPerformance() {
  const [season, setSeason] = useState('2025-26')
  const { data, loading, error, refresh } = useModelPerformance(season)

  const perf: ModelPerformanceItem[] = data?.performance ?? []
  const ensemble = perf.find(m => m.model_name === 'ensemble')
  const bestAccuracy = perf.length ? Math.max(...perf.map(m => m.accuracy ?? 0)) : null

  return (
    <div style={{ padding: '28px 28px', maxWidth: 'var(--content-w)', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 28, flexWrap: 'wrap' }}>
        <select className="scribble-select" value={season} onChange={e => setSeason(e.target.value)}>
          {SEASONS.map(s => <option key={s} value={s}>{s}</option>)}
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

      {/* Summary cards */}
      {data && (
        <motion.div
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 10, marginBottom: 28 }}
        >
          <SummaryCard label="Evaluated Models" value={String(data.evaluated_models)} />
          <SummaryCard
            label="Best Accuracy"
            value={bestAccuracy != null ? `${(bestAccuracy * 100).toFixed(1)}%` : '—'}
            color={bestAccuracy != null && bestAccuracy >= 0.55 ? 'var(--success)' : 'var(--warning)'}
            sub="across all models"
          />
          <SummaryCard
            label="Ensemble Accuracy"
            value={ensemble?.accuracy != null ? `${(ensemble.accuracy * 100).toFixed(1)}%` : '—'}
            color={ensemble?.accuracy != null && ensemble.accuracy >= 0.55 ? 'var(--success)' : 'var(--warning)'}
          />
          <SummaryCard
            label="Ensemble Brier"
            value={ensemble?.brier_score != null ? ensemble.brier_score.toFixed(4) : '—'}
            color={ensemble?.brier_score != null && ensemble.brier_score <= 0.25 ? 'var(--success)' : 'var(--error)'}
            sub="↓ lower is better"
          />
          <SummaryCard
            label="Pending Games"
            value={String(data.pending_games)}
            color={data.pending_games > 0 ? 'var(--warning)' : 'var(--text-1)'}
            sub="awaiting results"
          />
        </motion.div>
      )}

      {/* Performance table */}
      <p className="section-label" style={{ marginBottom: 12, color: ACCENT }}>Model Comparison</p>

      <motion.div
        initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
        style={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', overflow: 'hidden' }}
      >
        {loading && (
          <div style={{ padding: '24px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[...Array(4)].map((_, i) => <div key={i} style={{ height: 48 }} className="skeleton-row" />)}
          </div>
        )}

        {!loading && perf.length === 0 && (
          <div style={{ padding: '32px 24px', textAlign: 'center' }}>
            <p style={{ fontSize: '1.5rem', marginBottom: 10 }}>📊</p>
            <p style={{ fontWeight: 700, color: 'var(--text-1)', marginBottom: 6 }}>No performance data yet</p>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-2)', maxWidth: 380, margin: '0 auto' }}>
              Performance is calculated from completed games with saved predictions. Run today's predictions and settle results to see data here.
            </p>
          </div>
        )}

        {!loading && perf.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 720 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Model', 'Games Evaluated', 'Accuracy', 'Brier Score', 'Avg Confidence', 'First Pred', 'Last Pred'].map(h => (
                    <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-2)', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {perf.map((m, i) => {
                  const color = MODEL_COLORS[m.model_name] ?? ACCENT
                  const label = MODEL_LABELS[m.model_name] ?? m.model_name
                  const isBest = m.accuracy === bestAccuracy
                  return (
                    <tr key={m.model_name} style={{ borderBottom: i < perf.length - 1 ? '1px solid var(--border)' : 'none' }}>
                      <td style={{ padding: '12px 16px', whiteSpace: 'nowrap' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ width: 8, height: 8, borderRadius: 2, background: color, flexShrink: 0 }} />
                          <span style={{ fontWeight: 700, fontSize: '0.88rem', color: 'var(--text-1)' }}>{label}</span>
                          {isBest && (
                            <span style={{ padding: '1px 6px', borderRadius: 20, background: `${ACCENT}15`, color: ACCENT, fontSize: '0.65rem', fontWeight: 700 }}>BEST</span>
                          )}
                        </div>
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: '0.82rem', fontFamily: 'var(--font-mono)', color: 'var(--text-1)', textAlign: 'center' }}>
                        {m.evaluated_games}
                        <span style={{ color: 'var(--text-3)', marginLeft: 4, fontSize: '0.72rem' }}>({m.correct_games}✓)</span>
                      </td>
                      <td style={{ padding: '12px 16px', minWidth: 180 }}>
                        <AccuracyBar value={m.accuracy ?? 0} />
                      </td>
                      <td style={{ padding: '12px 16px', minWidth: 160 }}>
                        <BrierBar value={m.brier_score ?? 0} />
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: '0.82rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'center' }}>
                        {m.avg_confidence != null ? `${(m.avg_confidence * 100).toFixed(1)}%` : '—'}
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-3)', whiteSpace: 'nowrap' }}>
                        {fmtDate(m.first_prediction_at)}
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-3)', whiteSpace: 'nowrap' }}>
                        {fmtDate(m.last_prediction_at)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </motion.div>

      <p style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginTop: 10 }}>
        Accuracy threshold: 55% · Brier threshold: 0.25 · ↓ Brier = better calibration
      </p>
    </div>
  )
}
