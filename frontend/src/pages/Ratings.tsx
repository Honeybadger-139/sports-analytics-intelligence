import { useState } from 'react'
import { motion } from 'framer-motion'
import { useTeamRatings, useHomeCourtEffect } from '../hooks/useApi'
import { useSportContext } from '../context/SportContext'
import type { TeamRatingEntry } from '../types'

const ACCENT = '#A78BFA'     // matches --accent-lab (purple)
const ACCENT_DIM = 'rgba(167, 139, 250, 0.12)'

const TIER_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  elite:      { color: '#34D399', bg: 'rgba(52, 211, 153, 0.15)', label: 'ELITE' },
  contender:  { color: '#2BC9FF', bg: 'rgba(43, 201, 255, 0.15)', label: 'CONTENDER' },
  average:    { color: '#F7B24A', bg: 'rgba(247, 178, 74, 0.15)',  label: 'AVERAGE' },
  rebuilding: { color: '#FB923C', bg: 'rgba(251, 146, 60, 0.15)',  label: 'REBUILDING' },
  lottery:    { color: '#FB7185', bg: 'rgba(251, 113, 133, 0.15)', label: 'LOTTERY' },
}

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.03 } },
}

const fadeUp = {
  hidden: { opacity: 0, y: 10 },
  show:   { opacity: 1, y: 0, transition: { duration: 0.3 } },
}

function fmt(n: number | undefined | null, decimals = 0) {
  if (n == null) return '--'
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: decimals })
}

function pct(n: number | undefined | null) {
  if (n == null) return '--'
  return `${Math.round(n * 100)}%`
}

function StrengthBar({ strength, max }: { strength: number; max: number }) {
  const abs = Math.abs(strength)
  const normalized = max > 0 ? abs / max : 0
  const isPositive = strength >= 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{ fontSize: 11, color: isPositive ? '#34D399' : '#FB7185', fontVariantNumeric: 'tabular-nums', minWidth: 42, textAlign: 'right' }}>
        {isPositive ? '+' : '-'}{abs.toFixed(3)}
      </span>
      <div style={{ flex: 1, height: 6, background: 'var(--bg-elevated)', borderRadius: 3, overflow: 'hidden', minWidth: 80 }}>
        <div style={{
          height: '100%',
          width: `${normalized * 100}%`,
          background: isPositive ? '#34D399' : '#FB7185',
          borderRadius: 3,
          transition: 'width 0.6s ease',
        }} />
      </div>
    </div>
  )
}

function TierBadge({ tier }: { tier: string }) {
  const cfg = TIER_CONFIG[tier] ?? TIER_CONFIG.average
  return (
    <span style={{
      fontSize: 9,
      fontWeight: 700,
      letterSpacing: '0.06em',
      padding: '2px 7px',
      borderRadius: 4,
      background: cfg.bg,
      color: cfg.color,
      whiteSpace: 'nowrap',
    }}>
      {cfg.label}
    </span>
  )
}

function DiDPanel() {
  const { data, loading, error } = useHomeCourtEffect()

  if (loading) return (
    <div style={{ padding: 20, background: 'var(--bg-panel)', borderRadius: 10, border: '1px solid var(--bg-elevated)', marginBottom: 20 }}>
      <div style={{ height: 14, width: 200, background: 'var(--bg-elevated)', borderRadius: 4, animation: 'pulse 1.5s infinite' }} />
    </div>
  )

  if (error || !data) return null

  const ciLow = fmt(data.confidence_interval_95?.[0], 3)
  const ciHigh = fmt(data.confidence_interval_95?.[1], 3)

  return (
    <motion.div variants={fadeUp} style={{
      background: 'var(--bg-panel)',
      border: `1px solid ${data.is_significant ? 'rgba(52,211,153,0.3)' : 'var(--bg-elevated)'}`,
      borderRadius: 10,
      padding: '18px 20px',
      marginBottom: 20,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M2 12L5 7L8 9L12 3" stroke={ACCENT} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          Home Court Effect — Causal Analysis (DiD)
        </span>
        {data.is_significant && (
          <span style={{ fontSize: 9, fontWeight: 700, color: '#34D399', background: 'rgba(52,211,153,0.15)', padding: '2px 6px', borderRadius: 4, letterSpacing: '0.05em' }}>
            SIGNIFICANT
          </span>
        )}
      </div>

      <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '0 0 14px', lineHeight: 1.6 }}>
        {data.interpretation}
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10 }}>
        {[
          { label: 'DiD Estimate', value: `${(data.did_estimate * 100).toFixed(1)}pp`, accent: data.did_estimate > 0 ? '#34D399' : '#FB7185' },
          { label: 'Home Win % (fans)', value: pct(data.home_win_pct_with_fans) },
          { label: 'Home Win % (no fans)', value: pct(data.home_win_pct_without_fans) },
          { label: 'p-value', value: data.p_value.toFixed(3), accent: data.p_value < 0.05 ? '#34D399' : '#F7B24A' },
          { label: '95% CI', value: `[${ciLow}, ${ciHigh}]` },
          { label: 'Total Games', value: fmt(data.n_total_games) },
        ].map(item => (
          <div key={item.label} style={{ background: 'var(--bg-elevated)', borderRadius: 7, padding: '10px 12px' }}>
            <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 3, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{item.label}</div>
            <div style={{ fontSize: 15, fontWeight: 600, color: item.accent ?? 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>{item.value}</div>
          </div>
        ))}
      </div>
    </motion.div>
  )
}

export default function Ratings() {
  const { selection } = useSportContext()
  const [filterTier, setFilterTier] = useState<string>('all')
  const { data, loading, error, refresh } = useTeamRatings(selection.season)

  const rankings = data?.rankings ?? []
  const filtered = filterTier === 'all' ? rankings : rankings.filter(r => r.tier === filterTier)

  const maxStrength = rankings.length > 0
    ? Math.max(...rankings.map(r => Math.abs(r.strength)))
    : 1

  return (
    <div style={{ maxWidth: 'var(--content-w, 1140px)', margin: '0 auto', padding: '24px 20px' }}>
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
        style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 22, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ display: 'inline-flex', width: 32, height: 32, borderRadius: 8, background: ACCENT_DIM, alignItems: 'center', justifyContent: 'center' }}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M8 2L9.5 6H14L10.5 8.5L11.5 13L8 10.5L4.5 13L5.5 8.5L2 6H6.5L8 2Z" stroke={ACCENT} strokeWidth="1.3" strokeLinejoin="round" fill="none"/>
              </svg>
            </span>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: 'var(--text-primary)' }}>Team Ratings</h1>
          </div>
          <p style={{ margin: '4px 0 0 0', fontSize: 12, color: 'var(--text-tertiary)' }}>
            Bradley-Terry schedule-adjusted strength · {selection.season}
          </p>
        </div>
        <button onClick={refresh} style={{ background: ACCENT_DIM, border: `1px solid ${ACCENT}`, color: ACCENT, borderRadius: 7, padding: '7px 14px', fontSize: 12, cursor: 'pointer', fontWeight: 600 }}>
          Refresh
        </button>
      </motion.div>

      {/* DiD Panel */}
      <motion.div initial="hidden" animate="show" variants={stagger}>
        <DiDPanel />
      </motion.div>

      {/* Tier filter */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
        {(['all', 'elite', 'contender', 'average', 'rebuilding', 'lottery'] as const).map(tier => {
          const cfg = tier === 'all' ? null : TIER_CONFIG[tier]
          const isActive = filterTier === tier
          return (
            <button
              key={tier}
              onClick={() => setFilterTier(tier)}
              style={{
                padding: '5px 12px',
                borderRadius: 6,
                border: isActive ? `1px solid ${cfg?.color ?? ACCENT}` : '1px solid var(--bg-elevated)',
                background: isActive ? (cfg?.bg ?? ACCENT_DIM) : 'var(--bg-panel)',
                color: isActive ? (cfg?.color ?? ACCENT) : 'var(--text-secondary)',
                fontSize: 11,
                fontWeight: 600,
                cursor: 'pointer',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                transition: 'all 0.15s',
              }}
            >
              {tier === 'all' ? 'All Teams' : tier}
            </button>
          )
        })}
        {data && (
          <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-tertiary)', alignSelf: 'center' }}>
            {filtered.length} team{filtered.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Table */}
      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[...Array(8)].map((_, i) => (
            <div key={i} style={{ height: 52, background: 'var(--bg-panel)', borderRadius: 8, animation: 'pulse 1.5s infinite', animationDelay: `${i * 0.05}s` }} />
          ))}
        </div>
      )}

      {error && (
        <div style={{ padding: 20, background: 'rgba(251,113,133,0.08)', borderRadius: 8, border: '1px solid rgba(251,113,133,0.3)', color: '#FB7185', fontSize: 13 }}>
          {error}
        </div>
      )}

      {!loading && !error && (
        <>
          {/* Column headers */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '40px 1fr 120px 1fr 80px',
            gap: 12,
            padding: '8px 14px',
            marginBottom: 4,
          }}>
            {['#', 'Team', 'Tier', 'Strength', 'vs Avg'].map(h => (
              <span key={h} style={{ fontSize: 10, color: 'var(--text-tertiary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em' }}>{h}</span>
            ))}
          </div>

          <motion.div initial="hidden" animate="show" variants={stagger} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {filtered.map((team: TeamRatingEntry) => (
              <motion.div
                key={team.team}
                variants={fadeUp}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '40px 1fr 120px 1fr 80px',
                  gap: 12,
                  alignItems: 'center',
                  padding: '12px 14px',
                  background: 'var(--bg-panel)',
                  borderRadius: 8,
                  border: '1px solid var(--bg-elevated)',
                  transition: 'background 0.15s',
                }}
                whileHover={{ background: 'var(--bg-hover)' } as Parameters<typeof motion.div>[0]['whileHover']}
              >
                {/* Rank */}
                <span style={{
                  fontSize: team.rank <= 3 ? 14 : 12,
                  fontWeight: team.rank <= 3 ? 700 : 500,
                  color: team.rank === 1 ? '#F7B24A' : team.rank === 2 ? '#A78BFA' : team.rank === 3 ? '#FB923C' : 'var(--text-tertiary)',
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  {team.rank}
                </span>

                {/* Team name */}
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {team.team}
                </span>

                {/* Tier badge */}
                <TierBadge tier={team.tier} />

                {/* Strength bar */}
                <StrengthBar strength={team.strength} max={maxStrength} />

                {/* Win vs average */}
                <span style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: team.win_vs_average_team >= 0.6 ? '#34D399' : team.win_vs_average_team <= 0.4 ? '#FB7185' : 'var(--text-secondary)',
                  fontVariantNumeric: 'tabular-nums',
                  textAlign: 'right',
                }}>
                  {pct(team.win_vs_average_team)}
                </span>
              </motion.div>
            ))}
          </motion.div>

          {filtered.length === 0 && (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
              No teams in this tier for {selection.season}.
            </div>
          )}

          {data?.summary && (
            <div style={{ marginTop: 20, padding: '14px 16px', background: 'var(--bg-panel)', borderRadius: 8, border: '1px solid var(--bg-elevated)' }}>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>Model Summary</div>
              <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
                {[
                  { label: 'Strongest', value: String(data.summary.strongest_team ?? '--') },
                  { label: 'Weakest', value: String(data.summary.weakest_team ?? '--') },
                  { label: 'Spread (std)', value: fmt(data.summary.std as number | null, 3) },
                  { label: 'Log-Likelihood', value: fmt(data.summary.training_log_likelihood as number | null, 1) },
                ].map(s => (
                  <div key={s.label}>
                    <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 2 }}>{s.label}</div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{s.value}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
