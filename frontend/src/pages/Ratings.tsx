import { useState } from 'react'
import { motion } from 'framer-motion'
import { useTeamRatings, useHomeCourtEffect } from '../hooks/useApi'
import { useSportContext } from '../context/SportContext'
import type { TeamRatingEntry } from '../types'

// CSS variables adapt in light mode: --accent-lab → #6D28D9, --accent-green → #047857, etc.
const ACCENT = 'var(--accent-lab)'
const ACCENT_DIM = 'var(--accent-lab-dim)'

const TIER: Record<string, { color: string; bg: string }> = {
  elite:      { color: 'var(--accent-green)',     bg: 'var(--accent-scrib-dim)' },
  contender:  { color: 'var(--accent-arena)',     bg: 'var(--accent-arena-dim)' },
  average:    { color: 'var(--accent-chat)',      bg: 'var(--accent-chat-dim)' },
  rebuilding: { color: 'var(--accent-dashboard)', bg: 'var(--accent-dashboard-dim)' },
  lottery:    { color: 'var(--accent-red)',       bg: 'var(--accent-red-dim)' },
}

const TIERS = ['all', 'elite', 'contender', 'average', 'rebuilding', 'lottery'] as const
type TierFilter = typeof TIERS[number]

function pct(n: number | null | undefined) {
  if (n == null) return '--'
  return `${Math.round(n * 100)}%`
}

function fmt(n: unknown, d = 3) {
  if (n == null || typeof n === 'undefined') return '--'
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: d })
}

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div style={{ background: 'var(--bg-elevated)', borderRadius: 8, padding: '10px 14px', flex: '1 1 100px' }}>
      <div style={{ fontSize: 9, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 700, color: accent ?? 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>{value}</div>
    </div>
  )
}

// ── Causal effect mini-panel ──────────────────────────────────────────────────

function CausalPanel() {
  const { data, loading } = useHomeCourtEffect()
  if (loading) return null
  if (!data) return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '10px 16px', marginBottom: 16,
      background: 'var(--bg-panel)', borderRadius: 9,
      border: '1px solid var(--bg-elevated)', opacity: 0.65,
    }}>
      <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
        <path d="M1.5 10.5L4.5 6L7 8L11 2.5" stroke={ACCENT} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
      <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>Home Court Effect (DiD)</span>
      <span style={{
        fontSize: '0.6rem', fontWeight: 700, padding: '1px 6px', borderRadius: '999px',
        background: 'rgba(247,178,74,0.14)', color: 'var(--warning)', letterSpacing: '0.06em',
      }}>COMING SOON</span>
    </div>
  )

  const sign = data.did_estimate >= 0 ? '+' : ''
  const sigColor = data.is_significant ? 'var(--accent-green)' : 'var(--accent-chat)'

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
      padding: '12px 16px', marginBottom: 16,
      background: 'var(--bg-panel)', borderRadius: 9,
      border: `1px solid ${data.is_significant ? 'rgba(52,211,153,0.25)' : 'var(--bg-elevated)'}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
        <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
          <path d="M1.5 10.5L4.5 6L7 8L11 2.5" stroke={ACCENT} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>Home Court Effect (DiD)</span>
        {data.is_significant && (
          <span style={{ fontSize: 9, fontWeight: 700, color: sigColor, background: `${sigColor}18`, padding: '1px 6px', borderRadius: 4 }}>SIGNIFICANT</span>
        )}
      </div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginLeft: 'auto' }}>
        {[
          { l: 'DiD Estimate', v: `${sign}${(data.did_estimate * 100).toFixed(1)}pp`, c: data.did_estimate >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' },
          { l: 'p-value', v: data.p_value.toFixed(3), c: data.p_value < 0.05 ? 'var(--accent-green)' : 'var(--accent-chat)' },
          { l: 'Home Win % (fans)', v: pct(data.home_win_pct_with_fans) },
          { l: 'Home Win % (no fans)', v: pct(data.home_win_pct_without_fans) },
        ].map(s => (
          <div key={s.l}>
            <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginBottom: 1 }}>{s.l}</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: s.c ?? 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>{s.v}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Strength bar ──────────────────────────────────────────────────────────────

function StrengthBar({ strength, max }: { strength: number; max: number }) {
  const norm = max > 0 ? Math.abs(strength) / max : 0
  const pos = strength >= 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{ fontSize: 11, color: pos ? 'var(--accent-green)' : 'var(--accent-red)', fontVariantNumeric: 'tabular-nums', minWidth: 48, textAlign: 'right', flexShrink: 0 }}>
        {pos ? '+' : ''}{strength.toFixed(3)}
      </span>
      <div style={{ flex: 1, height: 5, background: 'var(--bg-elevated)', borderRadius: 3, overflow: 'hidden', minWidth: 60 }}>
        <div style={{ height: '100%', width: `${norm * 100}%`, background: pos ? 'var(--accent-green)' : 'var(--accent-red)', borderRadius: 3, transition: 'width 0.5s ease' }} />
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Ratings() {
  const { selection } = useSportContext()
  const [tier, setTier] = useState<TierFilter>('all')
  const { data, loading, error, refresh } = useTeamRatings(selection.season)

  const rankings = data?.rankings ?? []
  const filtered = tier === 'all' ? rankings : rankings.filter(r => r.tier === tier)
  const maxStr = rankings.length ? Math.max(...rankings.map(r => Math.abs(r.strength))) : 1

  return (
    <div className="page-shell">
    <div style={{ maxWidth: 'var(--content-w, 1140px)', margin: '0 auto', padding: '24px 20px' }}>

      {/* ── Header ── */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ display: 'inline-flex', width: 30, height: 30, borderRadius: 7, background: ACCENT_DIM, alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 1.5L8.2 5H12L9 7.2L10 11L7 8.8L4 11L5 7.2L2 5H5.8L7 1.5Z" stroke={ACCENT} strokeWidth="1.2" strokeLinejoin="round" fill="none"/>
              </svg>
            </span>
            <div>
              <h1 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>Team Ratings</h1>
              <p style={{ margin: 0, fontSize: 10, color: 'var(--text-tertiary)' }}>Bradley-Terry · schedule-adjusted · {selection.season}</p>
            </div>
          </div>
          <button onClick={refresh} style={{ background: ACCENT_DIM, border: `1px solid ${ACCENT}`, color: ACCENT, borderRadius: 7, padding: '6px 14px', fontSize: 11, fontWeight: 600, cursor: 'pointer', letterSpacing: '0.04em' }}>
            Refresh
          </button>
        </div>
      </motion.div>

      {/* ── Causal panel ── */}
      <CausalPanel />

      {/* ── Summary stat row ── */}
      {data?.summary && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
          <StatCard label="Strongest" value={String(data.summary.strongest_team ?? '--')} accent="var(--accent-green)" />
          <StatCard label="Weakest" value={String(data.summary.weakest_team ?? '--')} accent="var(--accent-red)" />
          <StatCard label="Rating Spread" value={fmt(data.summary.std)} />
          <StatCard label="Model Fit (LL)" value={fmt(data.summary.training_log_likelihood, 1)} />
        </div>
      )}

      {/* ── Tier filter ── */}
      <div style={{ display: 'flex', gap: 5, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
        {TIERS.map(t => {
          const cfg = t === 'all' ? null : TIER[t]
          const active = tier === t
          return (
            <button key={t} onClick={() => setTier(t)} style={{
              padding: '5px 11px', borderRadius: 6, cursor: 'pointer',
              border: active ? `1px solid ${cfg?.color ?? ACCENT}` : '1px solid var(--bg-elevated)',
              background: active ? (cfg?.bg ?? ACCENT_DIM) : 'var(--bg-panel)',
              color: active ? (cfg?.color ?? ACCENT) : 'var(--text-secondary)',
              fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em',
              transition: 'all 0.13s',
            }}>
              {t === 'all' ? 'All' : t}
            </button>
          )
        })}
        {data && (
          <span style={{ marginLeft: 6, fontSize: 10, color: 'var(--text-tertiary)' }}>
            {filtered.length} team{filtered.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* ── States ── */}
      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {[...Array(8)].map((_, i) => (
            <div key={i} style={{ height: 48, background: 'var(--bg-panel)', borderRadius: 8, animation: 'pulse 1.5s infinite', animationDelay: `${i * 0.04}s`, opacity: 1 - i * 0.08 }} />
          ))}
        </div>
      )}

      {error && !loading && (
        <div style={{ padding: '28px 24px', background: 'var(--bg-panel)', borderRadius: 10, border: '1px solid var(--bg-elevated)', textAlign: 'center' }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>Ratings unavailable</div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
            {error}
          </div>
        </div>
      )}

      {!loading && !error && (
        <>
          {/* Column headers */}
          <div style={{ display: 'grid', gridTemplateColumns: '32px 1fr 90px 1fr 64px', gap: 12, padding: '4px 14px', marginBottom: 4 }}>
            {['#', 'Team', 'Tier', 'Strength', 'vs Avg'].map(h => (
              <span key={h} style={{ fontSize: 9, fontWeight: 600, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>{h}</span>
            ))}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {filtered.map((r: TeamRatingEntry, idx: number) => {
              const tierCfg = TIER[r.tier]
              return (
                <motion.div
                  key={r.team}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.015, duration: 0.2 }}
                  style={{
                    display: 'grid', gridTemplateColumns: '32px 1fr 90px 1fr 64px',
                    gap: 12, alignItems: 'center',
                    padding: '11px 14px', background: 'var(--bg-panel)',
                    borderRadius: 8, border: '1px solid var(--bg-elevated)',
                    transition: 'background 0.12s',
                  }}
                >
                  <span style={{
                    fontSize: r.rank <= 3 ? 13 : 11, fontWeight: r.rank <= 3 ? 700 : 400,
                    color: r.rank === 1 ? 'var(--accent-chat)' : r.rank === 2 ? 'var(--accent-lab)' : r.rank === 3 ? 'var(--accent-dashboard)' : 'var(--text-tertiary)',
                    fontVariantNumeric: 'tabular-nums',
                  }}>{r.rank}</span>

                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {r.team}
                  </span>

                  <span style={{ fontSize: 9, fontWeight: 700, color: tierCfg.color, background: tierCfg.bg, padding: '2px 7px', borderRadius: 4, letterSpacing: '0.05em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>
                    {r.tier}
                  </span>

                  <StrengthBar strength={r.strength} max={maxStr} />

                  <span style={{
                    fontSize: 12, fontWeight: 600, textAlign: 'right',
                    color: r.win_vs_average_team >= 0.6 ? 'var(--accent-green)' : r.win_vs_average_team <= 0.4 ? 'var(--accent-red)' : 'var(--text-secondary)',
                    fontVariantNumeric: 'tabular-nums',
                  }}>
                    {pct(r.win_vs_average_team)}
                  </span>
                </motion.div>
              )
            })}
          </div>

          {filtered.length === 0 && (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
              No {tier} teams in {selection.season}.
            </div>
          )}
        </>
      )}
    </div>
    </div>
  )
}
