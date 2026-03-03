import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useDailyBrief, useMatches } from '../../hooks/useApi'
import type { BriefItem } from '../../types'

const ACCENT  = '#FF5C1A'
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

function fmtShort(iso: string): string {
  if (iso === todayISO()) return 'Today'
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function fmtLong(iso: string): string {
  if (iso === todayISO()) return 'Today'
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
}

// ── Sub-components ────────────────────────────────────────────────────────────

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
          The RAG intelligence layer requires{' '}
          <code style={{ fontFamily: 'var(--font-mono)', color: ACCENT }}>INTELLIGENCE_ENABLED=true</code>{' '}
          and a valid Gemini API key to be set in your environment.
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
        borderRadius: 'var(--r-md)', overflow: 'hidden', transition: 'border-color 0.15s',
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border-mid)')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
    >
      <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '1rem', color: ACCENT, letterSpacing: '0.04em' }}>
          {item.matchup}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <RiskBadge level={item.risk_level} />
          <span style={{ padding: '3px 9px', borderRadius: 20, background: 'var(--bg-elevated)', color: 'var(--text-2)', fontSize: '0.7rem', fontFamily: 'var(--font-mono)' }}>
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
          <button onClick={() => setExpanded(v => !v)} style={{ background: 'none', border: 'none', padding: '6px 0 0', color: ACCENT, fontSize: '0.78rem', fontWeight: 600, cursor: 'pointer' }}>
            {expanded ? '↑ Show less' : '↓ Show full brief'}
          </button>
        )}
      </div>
      <div style={{ padding: '10px 20px', borderTop: '1px solid var(--border)', background: 'var(--bg-elevated)' }}>
        <span style={{ fontSize: '0.7rem', fontFamily: 'var(--font-mono)', color: 'var(--text-3)' }}>game_id: {item.game_id}</span>
      </div>
    </motion.div>
  )
}

// ── Date filter panel ─────────────────────────────────────────────────────────

interface DateFilterPanelProps {
  briefDate:      string
  availableDates: string[]
  onSelect:       (date: string) => void
  onClose:        () => void
}

function DateFilterPanel({ briefDate, availableDates, onSelect, onClose }: DateFilterPanelProps) {
  const [mode,     setMode]     = useState<'single' | 'range'>('single')
  const [single,   setSingle]   = useState(briefDate)
  const [rangeFrom, setRangeFrom] = useState('')
  const [rangeTo,   setRangeTo]   = useState('')

  // Clamp date value to YYYY-MM-DD for the native input
  const maxDate = todayISO()

  function applyRange() {
    if (!rangeFrom) return
    // Jump to the first available date within the range, or rangeFrom itself
    const from = rangeFrom
    const to   = rangeTo || maxDate
    const match = availableDates.find(d => d >= from && d <= to)
    onSelect(match ?? from)
    onClose()
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.15 }}
      style={{
        position: 'absolute', top: 'calc(100% + 8px)', left: 0,
        zIndex: 100, width: 340,
        background: 'var(--bg-surface)', border: '1px solid var(--border)',
        borderRadius: 'var(--r-md)', boxShadow: 'var(--shadow-md)',
        overflow: 'hidden',
      }}
    >
      {/* Mode tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)' }}>
        {(['single', 'range'] as const).map(m => (
          <button
            key={m}
            onClick={() => setMode(m)}
            style={{
              flex: 1, padding: '10px', border: 'none', background: 'transparent', cursor: 'pointer',
              fontSize: '0.78rem', fontWeight: mode === m ? 700 : 500,
              color: mode === m ? ACCENT : 'var(--text-2)',
              borderBottom: mode === m ? `2px solid ${ACCENT}` : '2px solid transparent',
            }}
          >
            {m === 'single' ? 'Jump to date' : 'Date range'}
          </button>
        ))}
      </div>

      <div style={{ padding: '16px' }}>
        {mode === 'single' && (
          <>
            <label style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.07em', display: 'block', marginBottom: 8 }}>
              Select a date
            </label>
            <input
              type="date"
              className="scribble-input"
              max={maxDate}
              value={single}
              onChange={e => setSingle(e.target.value)}
              style={{ width: '100%', marginBottom: 12 }}
            />
            {/* Quick-pick chips — most recent available game dates */}
            {availableDates.length > 0 && (
              <>
                <p style={{ fontSize: '0.7rem', color: 'var(--text-3)', marginBottom: 6 }}>Recent game days</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
                  {availableDates.slice(0, 8).map(d => (
                    <button
                      key={d}
                      onClick={() => { onSelect(d); onClose() }}
                      style={{
                        padding: '4px 10px', borderRadius: 20, cursor: 'pointer',
                        border: `1px solid ${d === briefDate ? ACCENT : 'var(--border)'}`,
                        background: d === briefDate ? `${ACCENT}15` : 'transparent',
                        color: d === briefDate ? ACCENT : 'var(--text-2)',
                        fontSize: '0.72rem', fontWeight: d === briefDate ? 700 : 400,
                      }}
                    >
                      {fmtShort(d)}
                    </button>
                  ))}
                </div>
              </>
            )}
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => { onSelect(single); onClose() }}
                disabled={!single}
                style={{
                  flex: 1, padding: '8px', borderRadius: 'var(--r-sm)', cursor: 'pointer',
                  background: ACCENT, border: 'none', color: '#fff', fontSize: '0.8rem', fontWeight: 700,
                }}
              >
                Go to date
              </button>
              <button
                onClick={() => { onSelect(todayISO()); onClose() }}
                style={{
                  padding: '8px 14px', borderRadius: 'var(--r-sm)', cursor: 'pointer',
                  background: 'transparent', border: '1px solid var(--border)',
                  color: 'var(--text-2)', fontSize: '0.8rem',
                }}
              >
                Today
              </button>
            </div>
          </>
        )}

        {mode === 'range' && (
          <>
            <label style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.07em', display: 'block', marginBottom: 8 }}>
              Browse between dates
            </label>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: '0.7rem', color: 'var(--text-3)', marginBottom: 4 }}>From</p>
                <input
                  type="date"
                  className="scribble-input"
                  max={maxDate}
                  value={rangeFrom}
                  onChange={e => setRangeFrom(e.target.value)}
                  style={{ width: '100%' }}
                />
              </div>
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: '0.7rem', color: 'var(--text-3)', marginBottom: 4 }}>To</p>
                <input
                  type="date"
                  className="scribble-input"
                  max={maxDate}
                  min={rangeFrom || undefined}
                  value={rangeTo}
                  onChange={e => setRangeTo(e.target.value)}
                  style={{ width: '100%' }}
                />
              </div>
            </div>
            {rangeFrom && (
              <p style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginBottom: 10 }}>
                {availableDates.filter(d => d >= rangeFrom && d <= (rangeTo || maxDate)).length} game day(s) in range
              </p>
            )}
            <button
              onClick={applyRange}
              disabled={!rangeFrom}
              style={{
                width: '100%', padding: '8px', borderRadius: 'var(--r-sm)', cursor: rangeFrom ? 'pointer' : 'default',
                background: rangeFrom ? ACCENT : 'var(--border)', border: 'none',
                color: rangeFrom ? '#fff' : 'var(--text-3)', fontSize: '0.8rem', fontWeight: 700,
              }}
            >
              Jump to first game in range
            </button>
          </>
        )}
      </div>
    </motion.div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function DailyBrief() {
  const [season,       setSeason]       = useState('2025-26')
  const [briefDate,    setBriefDate]    = useState(todayISO)
  const [filterOpen,   setFilterOpen]   = useState(false)
  const autoFallbackDone = useRef(false)
  const filterRef        = useRef<HTMLDivElement>(null)

  const { data, loading, error, disabled, refresh } = useDailyBrief(season, briefDate)
  const { data: matchData, loading: matchLoading }   = useMatches(season, 30)

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

  // Reset when season changes
  useEffect(() => {
    autoFallbackDone.current = false
    setBriefDate(todayISO())
  }, [season])

  // Close filter panel when clicking outside
  useEffect(() => {
    if (!filterOpen) return
    const handler = (e: MouseEvent) => {
      if (filterRef.current && !filterRef.current.contains(e.target as Node)) {
        setFilterOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [filterOpen])

  const isToday = briefDate === todayISO()

  if (disabled) return <DisabledState />

  return (
    <div style={{ padding: '28px 28px', maxWidth: 'var(--content-w)', margin: '0 auto' }}>
      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 28, flexWrap: 'wrap' }}>

        {/* Season selector */}
        <select className="scribble-select" value={season} onChange={e => setSeason(e.target.value)}>
          {SEASONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>

        {/* Active date pill — always visible, compact */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '5px 12px', borderRadius: 20,
          background: isToday ? `${ACCENT}12` : 'var(--bg-elevated)',
          border: `1px solid ${isToday ? `${ACCENT}40` : 'var(--border)'}`,
          fontSize: '0.78rem', fontWeight: 600,
          color: isToday ? ACCENT : 'var(--text-1)',
        }}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
            <rect x="1" y="2" width="10" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
            <line x1="4" y1="1" x2="4" y2="3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
            <line x1="8" y1="1" x2="8" y2="3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
          </svg>
          {fmtLong(briefDate)}
          {!isToday && (
            <button
              onClick={() => { setBriefDate(todayISO()); autoFallbackDone.current = false }}
              title="Back to today"
              style={{ background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer', padding: '0 0 0 2px', fontSize: '0.9rem', lineHeight: 1 }}
            >×</button>
          )}
        </div>

        {/* ── Date filter button + panel ── */}
        <div ref={filterRef} style={{ position: 'relative' }}>
          <button
            onClick={() => setFilterOpen(v => !v)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 13px', borderRadius: 'var(--r-sm)', cursor: 'pointer',
              background: filterOpen ? `${ACCENT}15` : 'var(--bg-panel)',
              border: `1px solid ${filterOpen ? ACCENT : 'var(--border)'}`,
              color: filterOpen ? ACCENT : 'var(--text-2)',
              fontSize: '0.78rem', fontWeight: 600, transition: 'all 0.15s',
            }}
          >
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden>
              <rect x="1" y="2" width="11" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
              <line x1="4.5" y1="0.5" x2="4.5" y2="3.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
              <line x1="8.5" y1="0.5" x2="8.5" y2="3.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
              <line x1="1" y1="5.5" x2="12" y2="5.5" stroke="currentColor" strokeWidth="1.2"/>
            </svg>
            Filter by date
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" style={{ transition: 'transform 0.15s', transform: filterOpen ? 'rotate(180deg)' : 'none' }}>
              <path d="M2 3.5L5 6.5L8 3.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>

          <AnimatePresence>
            {filterOpen && (
              <DateFilterPanel
                briefDate={briefDate}
                availableDates={availableDates}
                onSelect={d => { setBriefDate(d); autoFallbackDone.current = true }}
                onClose={() => setFilterOpen(false)}
              />
            )}
          </AnimatePresence>
        </div>

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
            No games on today's date — showing most recent game day. Use "Filter by date" to browse other days.
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

      {/* Empty state */}
      {!loading && !error && data?.items.length === 0 && !matchLoading && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, textAlign: 'center', padding: '48px 0' }}>
          <p style={{ fontSize: '2rem' }}>📋</p>
          <p style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-1)' }}>No brief items for {briefDate}</p>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-2)', maxWidth: 360 }}>
            {availableDates.length > 0
              ? 'No games on this date. Use "Filter by date" to jump to a game day.'
              : 'No games found for this season. Make sure the ingestion pipeline has been run.'}
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
