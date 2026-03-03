import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { useDailyBrief, useMatches } from '../../hooks/useApi'
import type { BriefItem } from '../../types'

const ACCENT = '#FF5C1A'
const SEASONS = ['2025-26', '2024-25', '2023-24']

const RISK_CFG = {
  high:   { color: '#FF4C6A', bg: 'rgba(255,76,106,0.10)',  label: 'High Risk' },
  medium: { color: '#FFB100', bg: 'rgba(255,177,0,0.10)',   label: 'Medium Risk' },
  low:    { color: '#00D68F', bg: 'rgba(0,214,143,0.10)',   label: 'Low Risk' },
}

function todayISO(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function fmtDisplayDate(iso: string): string {
  if (iso === todayISO()) return 'Today'
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
}

function RiskBadge({ level }: { level: 'low' | 'medium' | 'high' }) {
  const cfg = RISK_CFG[level] ?? RISK_CFG.low
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 10px', borderRadius: 20,
      background: cfg.bg, color: cfg.color,
      fontSize: '0.7rem', fontWeight: 700,
      fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.06em',
    }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: cfg.color, flexShrink: 0 }} />
      {cfg.label}
    </span>
  )
}

function DisabledState() {
  return (
    <div style={{
      margin: '40px 28px',
      background: 'var(--bg-panel)', border: '1px solid var(--border)',
      borderRadius: 'var(--r-lg)', padding: '36px 32px',
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, textAlign: 'center',
    }}>
      <div style={{
        width: 48, height: 48, borderRadius: '50%',
        background: 'rgba(255,177,0,0.10)', display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden>
          <path d="M11 2L19.5 18H2.5L11 2Z" stroke="#FFB100" strokeWidth="1.5" strokeLinejoin="round"/>
          <line x1="11" y1="8" x2="11" y2="13" stroke="#FFB100" strokeWidth="1.5" strokeLinecap="round"/>
          <circle cx="11" cy="16" r="0.8" fill="#FFB100"/>
        </svg>
      </div>
      <div>
        <p style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-1)', marginBottom: 6 }}>Intelligence Layer Disabled</p>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-2)', lineHeight: 1.6, maxWidth: 420 }}>
          The RAG intelligence layer requires <code style={{ fontFamily: 'var(--font-mono)', color: ACCENT }}>INTELLIGENCE_ENABLED=true</code> and a valid Gemini API key to be set in your environment.
        </p>
      </div>
      <div style={{
        background: 'var(--bg-elevated)', borderRadius: 'var(--r-sm)',
        padding: '10px 16px', fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: 'var(--text-2)',
      }}>
        INTELLIGENCE_ENABLED=true<br/>GEMINI_API_KEY=your_key_here
      </div>
    </div>
  )
}

function BriefCard({ item, index }: { item: BriefItem; index: number }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: index * 0.05 }}
      style={{
        background: 'var(--bg-panel)', border: '1px solid var(--border)',
        borderRadius: 'var(--r-md)', overflow: 'hidden',
        transition: 'border-color 0.15s',
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border-mid)')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
    >
      <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <span style={{
          fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '1rem',
          color: ACCENT, letterSpacing: '0.04em',
        }}>
          {item.matchup}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <RiskBadge level={item.risk_level} />
          <span style={{
            padding: '3px 9px', borderRadius: 20,
            background: 'var(--bg-elevated)', color: 'var(--text-2)',
            fontSize: '0.7rem', fontFamily: 'var(--font-mono)',
          }}>
            {item.citation_count} {item.citation_count === 1 ? 'source' : 'sources'}
          </span>
        </div>
      </div>

      <div style={{ padding: '16px 20px' }}>
        <p style={{
          fontSize: '0.85rem', color: 'var(--text-1)', lineHeight: 1.65,
          display: expanded ? 'block' : '-webkit-box',
          WebkitLineClamp: expanded ? undefined : 3,
          WebkitBoxOrient: 'vertical' as const,
          overflow: expanded ? 'visible' : 'hidden',
        }}>
          {item.summary}
        </p>
        {item.summary.length > 200 && (
          <button
            onClick={() => setExpanded(v => !v)}
            style={{
              background: 'none', border: 'none', padding: '6px 0 0',
              color: ACCENT, fontSize: '0.78rem', fontWeight: 600, cursor: 'pointer',
            }}
          >
            {expanded ? '↑ Show less' : '↓ Show full brief'}
          </button>
        )}
      </div>

      <div style={{ padding: '10px 20px', borderTop: '1px solid var(--border)', background: 'var(--bg-elevated)' }}>
        <span style={{ fontSize: '0.7rem', fontFamily: 'var(--font-mono)', color: 'var(--text-3)' }}>
          game_id: {item.game_id}
        </span>
      </div>
    </motion.div>
  )
}

export default function DailyBrief() {
  const [season,    setSeason]    = useState('2025-26')
  const [briefDate, setBriefDate] = useState(todayISO)
  const autoFallbackDone = useRef(false)

  const { data, loading, error, disabled, refresh } = useDailyBrief(season, briefDate)
  const { data: matchData, loading: matchLoading } = useMatches(season, 30)

  // Build sorted unique date list from recent matches (newest first)
  const availableDates: string[] = matchData?.matches
    ? [...new Set(matchData.matches.map(m => (m.game_date as string).slice(0, 10)))]
        .sort((a, b) => b.localeCompare(a))
    : []

  // Auto-fallback to most recent game date when today has no items
  useEffect(() => {
    if (autoFallbackDone.current) return
    if (loading || matchLoading) return
    if (!data || data.items.length > 0) return
    if (!availableDates.length) return
    const fallback = availableDates[0]
    if (fallback && fallback !== briefDate) {
      autoFallbackDone.current = true
      setBriefDate(fallback)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, matchLoading, data, availableDates.join(',')])

  // Reset auto-fallback when season changes
  useEffect(() => {
    autoFallbackDone.current = false
    setBriefDate(todayISO())
  }, [season])

  const currentIdx  = availableDates.indexOf(briefDate)
  const canGoPrev   = currentIdx === -1 ? availableDates.length > 0 : currentIdx < availableDates.length - 1
  const canGoNext   = currentIdx > 0
  const isToday     = briefDate === todayISO()

  function goPrev() {
    if (currentIdx === -1) setBriefDate(availableDates[0])
    else if (canGoPrev) setBriefDate(availableDates[currentIdx + 1])
  }
  function goNext() {
    if (canGoNext) setBriefDate(availableDates[currentIdx - 1])
  }

  if (disabled) return <DisabledState />

  return (
    <div style={{ padding: '28px 28px', maxWidth: 'var(--content-w)', margin: '0 auto' }}>
      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 28, flexWrap: 'wrap' }}>
        {/* Season selector */}
        <select
          className="scribble-select"
          value={season}
          onChange={e => setSeason(e.target.value)}
        >
          {SEASONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>

        {/* Date navigator */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 4,
          background: 'var(--bg-panel)', border: '1px solid var(--border)',
          borderRadius: 'var(--r-sm)', padding: '3px 4px',
        }}>
          <button
            onClick={goPrev}
            disabled={!canGoPrev}
            title="Previous game date"
            style={{
              background: 'none', border: 'none', padding: '4px 8px', cursor: canGoPrev ? 'pointer' : 'default',
              color: canGoPrev ? 'var(--text-1)' : 'var(--text-3)', borderRadius: 4,
            }}
          >
            ←
          </button>
          <div style={{ padding: '2px 8px', textAlign: 'center', minWidth: 180 }}>
            <p style={{ fontSize: '0.78rem', fontWeight: 600, color: isToday ? ACCENT : 'var(--text-1)', margin: 0 }}>
              {fmtDisplayDate(briefDate)}
            </p>
            {!isToday && (
              <p style={{ fontSize: '0.68rem', color: 'var(--text-3)', margin: 0, fontFamily: 'var(--font-mono)' }}>
                {briefDate}
              </p>
            )}
          </div>
          <button
            onClick={goNext}
            disabled={!canGoNext}
            title="Next game date"
            style={{
              background: 'none', border: 'none', padding: '4px 8px', cursor: canGoNext ? 'pointer' : 'default',
              color: canGoNext ? 'var(--text-1)' : 'var(--text-3)', borderRadius: 4,
            }}
          >
            →
          </button>
        </div>

        {/* Jump to today button when browsing historical */}
        {!isToday && (
          <button
            onClick={() => { setBriefDate(todayISO()); autoFallbackDone.current = false }}
            style={{
              padding: '5px 12px', borderRadius: 'var(--r-sm)',
              background: 'transparent', border: `1px solid ${ACCENT}30`,
              color: ACCENT, fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer',
            }}
          >
            Jump to today
          </button>
        )}

        {loading && <span style={{ fontSize: '0.78rem', color: 'var(--text-2)' }}>Loading brief…</span>}
        {error && !disabled && <span style={{ fontSize: '0.78rem', color: 'var(--error)' }}>{error}</span>}

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

      {/* Auto-fallback notice */}
      {autoFallbackDone.current && !loading && data && data.items.length > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16,
          padding: '8px 14px', background: 'rgba(255,177,0,0.07)', border: '1px solid rgba(255,177,0,0.2)',
          borderRadius: 'var(--r-sm)',
        }}>
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden>
            <circle cx="6.5" cy="6.5" r="5.5" stroke="#FFB100" strokeWidth="1.2"/>
            <line x1="6.5" y1="4" x2="6.5" y2="7" stroke="#FFB100" strokeWidth="1.2" strokeLinecap="round"/>
            <circle cx="6.5" cy="9" r="0.6" fill="#FFB100"/>
          </svg>
          <span style={{ fontSize: '0.75rem', color: '#FFB100' }}>
            No games on today's date — showing most recent game day ({briefDate}). Use ← → to navigate.
          </span>
        </div>
      )}

      {/* Summary pills */}
      {data && data.items.length > 0 && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          <span style={{ padding: '4px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 20, fontSize: '0.75rem', color: 'var(--text-2)' }}>
            {data.items.length} game{data.items.length !== 1 ? 's' : ''} briefed
          </span>
          {(['high', 'medium', 'low'] as const).map(lvl => {
            const n = data.items.filter(i => i.risk_level === lvl).length
            if (!n) return null
            const cfg = RISK_CFG[lvl]
            return (
              <span key={lvl} style={{ padding: '4px 12px', background: cfg.bg, border: `1px solid ${cfg.color}30`, borderRadius: 20, fontSize: '0.75rem', color: cfg.color, fontWeight: 600 }}>
                {n} {lvl} risk
              </span>
            )
          })}
        </div>
      )}

      {/* Loading skeletons */}
      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[...Array(3)].map((_, i) => (
            <div key={i} style={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', height: 140 }} className="skeleton-row" />
          ))}
        </div>
      )}

      {/* Empty state — only show after auto-fallback has run and still empty */}
      {!loading && !error && data?.items.length === 0 && !matchLoading && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, textAlign: 'center', padding: '48px 0' }}>
          <p style={{ fontSize: '2rem' }}>📋</p>
          <p style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-1)' }}>No brief items for {briefDate}</p>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-2)', maxWidth: 360 }}>
            {availableDates.length > 0
              ? 'No games on this date. Use the ← arrow to go to the previous game day.'
              : 'No games found in the database for this season. Make sure the ingestion pipeline has been run.'}
          </p>
          {availableDates.length > 0 && (
            <button
              onClick={() => { setBriefDate(availableDates[0]); autoFallbackDone.current = true }}
              style={{
                padding: '7px 16px', borderRadius: 'var(--r-sm)',
                background: 'transparent', border: `1px solid ${ACCENT}`,
                color: ACCENT, fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer',
              }}
            >
              Go to most recent game day ({availableDates[0]})
            </button>
          )}
        </div>
      )}

      {/* Brief cards */}
      {!loading && data && data.items.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {data.items.map((item, i) => (
            <BriefCard key={item.game_id} item={item} index={i} />
          ))}
        </div>
      )}
    </div>
  )
}
