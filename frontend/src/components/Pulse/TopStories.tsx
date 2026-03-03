import { useState } from 'react'
import { motion } from 'framer-motion'
import { useDailyBrief } from '../../hooks/useApi'
import type { BriefItem } from '../../types'

const ACCENT = '#FF5C1A'

const RISK_CFG = {
  high:   { color: '#FF4C6A', bg: 'rgba(255,76,106,0.10)',  label: 'High Risk',   emoji: '🔴' },
  medium: { color: '#FFB100', bg: 'rgba(255,177,0,0.10)',   label: 'Medium Risk', emoji: '🟡' },
  low:    { color: '#00D68F', bg: 'rgba(0,214,143,0.10)',   label: 'Low Risk',    emoji: '🟢' },
}

function DisabledState() {
  return (
    <div style={{
      margin: '40px 28px',
      background: 'var(--bg-panel)', border: '1px solid var(--border)',
      borderRadius: 'var(--r-lg)', padding: '36px 32px',
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, textAlign: 'center',
    }}>
      <p style={{ fontSize: '2rem' }}>⚙️</p>
      <p style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-1)' }}>Intelligence Layer Disabled</p>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-2)', lineHeight: 1.6, maxWidth: 420 }}>
        Top Stories are sourced from the RAG intelligence layer. Enable it by setting{' '}
        <code style={{ fontFamily: 'var(--font-mono)', color: ACCENT }}>INTELLIGENCE_ENABLED=true</code> and a valid Gemini API key.
      </p>
    </div>
  )
}

function StoryCard({ item, index }: { item: BriefItem; index: number }) {
  const risk = RISK_CFG[item.risk_level] ?? RISK_CFG.low
  const [vs_home, vs_away] = item.matchup.includes(' vs ') ? item.matchup.split(' vs ') : item.matchup.includes(' @ ') ? item.matchup.split(' @ ').reverse() : [item.matchup, '']

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: index * 0.04 }}
      style={{
        background: 'var(--bg-panel)', border: '1px solid var(--border)',
        borderRadius: 'var(--r-md)', padding: '20px 22px',
        transition: 'border-color 0.15s, box-shadow 0.15s',
        position: 'relative', overflow: 'hidden',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = 'var(--border-mid)'
        e.currentTarget.style.boxShadow = 'var(--shadow-sm)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = 'var(--border)'
        e.currentTarget.style.boxShadow = 'none'
      }}
    >
      {/* Left accent bar */}
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0, width: 3,
        background: risk.color, borderRadius: '3px 0 0 3px',
      }} />

      <div style={{ paddingLeft: 6 }}>
        {/* Matchup header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-3)' }}>
              Matchup
            </span>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '0.92rem', color: 'var(--text-1)', letterSpacing: '0.04em' }}>
              {vs_home}
              {vs_away && <span style={{ color: 'var(--text-3)', margin: '0 6px', fontWeight: 400 }}>vs</span>}
              {vs_away}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{
              padding: '2px 9px', borderRadius: 20, background: risk.bg, color: risk.color,
              fontSize: '0.68rem', fontWeight: 700, fontFamily: 'var(--font-mono)',
              textTransform: 'uppercase', letterSpacing: '0.06em',
            }}>
              {risk.emoji} {risk.label}
            </span>
            <span style={{
              padding: '2px 8px', borderRadius: 20, background: 'var(--bg-elevated)', color: 'var(--text-2)',
              fontSize: '0.68rem', fontFamily: 'var(--font-mono)',
            }}>
              {item.citation_count} source{item.citation_count !== 1 ? 's' : ''}
            </span>
          </div>
        </div>

        {/* Story body */}
        <p style={{ fontSize: '0.84rem', color: 'var(--text-2)', lineHeight: 1.7, margin: 0 }}>
          {item.summary.length > 300
            ? item.summary.slice(0, 300) + '… '
            : item.summary}
          {item.summary.length > 300 && (
            <span style={{ color: 'var(--text-3)', fontSize: '0.75rem' }}>
              (full brief in Daily Brief tab)
            </span>
          )}
        </p>
      </div>
    </motion.div>
  )
}

export default function TopStories() {
  const [season, setSeason] = useState('2025-26')
  const [riskFilter, setRiskFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all')
  const { data, loading, error, disabled, refresh } = useDailyBrief(season)

  if (disabled) return <DisabledState />

  const items: BriefItem[] = data?.items ?? []
  const filtered = riskFilter === 'all' ? items : items.filter(i => i.risk_level === riskFilter)

  // Sort: high risk first, then medium, then low
  const RISK_ORDER = { high: 0, medium: 1, low: 2 }
  const sorted = [...filtered].sort((a, b) => (RISK_ORDER[a.risk_level] ?? 3) - (RISK_ORDER[b.risk_level] ?? 3))

  return (
    <div style={{ padding: '28px 28px', maxWidth: 'var(--content-w)', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24, flexWrap: 'wrap' }}>
        <select className="scribble-select" value={season} onChange={e => setSeason(e.target.value)}>
          {['2025-26', '2024-25', '2023-24'].map(s => <option key={s} value={s}>{s}</option>)}
        </select>

        {/* Risk filter chips */}
        <div style={{ display: 'flex', gap: 6 }}>
          {(['all', 'high', 'medium', 'low'] as const).map(lvl => {
            const cfg = lvl !== 'all' ? RISK_CFG[lvl] : null
            const isActive = riskFilter === lvl
            return (
              <button
                key={lvl}
                onClick={() => setRiskFilter(lvl)}
                style={{
                  padding: '5px 12px', borderRadius: 20, cursor: 'pointer',
                  border: `1px solid ${isActive ? (cfg?.color ?? ACCENT) : 'var(--border)'}`,
                  background: isActive ? (cfg?.bg ?? 'rgba(255,92,26,0.10)') : 'transparent',
                  color: isActive ? (cfg?.color ?? ACCENT) : 'var(--text-2)',
                  fontSize: '0.75rem', fontWeight: isActive ? 700 : 500,
                  transition: 'all 0.15s',
                }}
              >
                {lvl === 'all' ? 'All' : `${cfg?.emoji} ${lvl.charAt(0).toUpperCase() + lvl.slice(1)}`}
              </button>
            )
          })}
        </div>

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

      {/* Source note */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20,
        padding: '8px 14px', background: 'var(--bg-elevated)', border: '1px solid var(--border)',
        borderRadius: 'var(--r-sm)', width: 'fit-content',
      }}>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
          <circle cx="6" cy="6" r="5" stroke="var(--text-3)" strokeWidth="1.2"/>
          <line x1="6" y1="4" x2="6" y2="6.5" stroke="var(--text-3)" strokeWidth="1.2" strokeLinecap="round"/>
          <circle cx="6" cy="8.5" r="0.5" fill="var(--text-3)"/>
        </svg>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>
          Stories sourced from ESPN, CBS Sports and RotoWire via RAG intelligence context · {new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
        </span>
      </div>

      {/* Stories grid */}
      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {[...Array(3)].map((_, i) => (
            <div key={i} style={{ height: 110, background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)' }} className="skeleton-row" />
          ))}
        </div>
      )}

      {!loading && sorted.length === 0 && (
        <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text-2)' }}>
          <p style={{ fontSize: '1.5rem', marginBottom: 10 }}>📰</p>
          <p style={{ fontWeight: 700, color: 'var(--text-1)', marginBottom: 6 }}>No stories available</p>
          <p style={{ fontSize: '0.85rem' }}>
            {riskFilter !== 'all'
              ? `No ${riskFilter}-risk matchups today. Try a different filter.`
              : 'No games with intelligence context found for today.'}
          </p>
        </div>
      )}

      {!loading && sorted.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {sorted.map((item, i) => <StoryCard key={item.game_id} item={item} index={i} />)}
        </div>
      )}
    </div>
  )
}
