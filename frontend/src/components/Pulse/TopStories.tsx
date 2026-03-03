import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useDailyBrief, useMatches } from '../../hooks/useApi'
import type { BriefItem } from '../../types'

const ACCENT  = '#FF5C1A'
const SEASONS = ['2025-26', '2024-25', '2023-24']

const RISK_CFG = {
  high:   { color: '#FF4C6A', bg: 'rgba(255,76,106,0.10)',  label: 'High Risk',   emoji: '🔴' },
  medium: { color: '#FFB100', bg: 'rgba(255,177,0,0.10)',   label: 'Medium Risk', emoji: '🟡' },
  low:    { color: '#00D68F', bg: 'rgba(0,214,143,0.10)',   label: 'Low Risk',    emoji: '🟢' },
}
const RISK_ORDER: Record<string, number> = { high: 0, medium: 1, low: 2 }

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
  return new Date(y, m - 1, d).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
}

// ── Sub-components ────────────────────────────────────────────────────────────

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
  const risk  = RISK_CFG[item.risk_level] ?? RISK_CFG.low
  const parts = item.matchup.includes(' @ ')
    ? item.matchup.split(' @ ')
    : item.matchup.includes(' vs ')
      ? item.matchup.split(' vs ')
      : [item.matchup, '']
  const [team1, team2] = parts

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
      onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--border-mid)'; e.currentTarget.style.boxShadow = 'var(--shadow-sm)' }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.boxShadow = 'none' }}
    >
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, background: risk.color, borderRadius: '3px 0 0 3px' }} />
      <div style={{ paddingLeft: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-3)' }}>Matchup</span>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '0.92rem', color: 'var(--text-1)', letterSpacing: '0.04em' }}>
              {team1}
              {team2 && <span style={{ color: 'var(--text-3)', margin: '0 6px', fontWeight: 400 }}>vs</span>}
              {team2}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ padding: '2px 9px', borderRadius: 20, background: risk.bg, color: risk.color, fontSize: '0.68rem', fontWeight: 700, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              {risk.emoji} {risk.label}
            </span>
            <span style={{ padding: '2px 8px', borderRadius: 20, background: 'var(--bg-elevated)', color: 'var(--text-2)', fontSize: '0.68rem', fontFamily: 'var(--font-mono)' }}>
              {item.citation_count} source{item.citation_count !== 1 ? 's' : ''}
            </span>
          </div>
        </div>
        <p style={{ fontSize: '0.84rem', color: 'var(--text-2)', lineHeight: 1.7, margin: 0 }}>
          {item.summary.length > 300 ? item.summary.slice(0, 300) + '… ' : item.summary}
          {item.summary.length > 300 && (
            <span style={{ color: 'var(--text-3)', fontSize: '0.75rem' }}>(full brief in Daily Brief tab)</span>
          )}
        </p>
      </div>
    </motion.div>
  )
}

// ── Date filter panel (shared logic) ─────────────────────────────────────────

interface DateFilterPanelProps {
  briefDate:      string
  availableDates: string[]
  onSelect:       (date: string) => void
  onClose:        () => void
}

function DateFilterPanel({ briefDate, availableDates, onSelect, onClose }: DateFilterPanelProps) {
  const [mode,      setMode]      = useState<'single' | 'range'>('single')
  const [single,    setSingle]    = useState(briefDate)
  const [rangeFrom, setRangeFrom] = useState('')
  const [rangeTo,   setRangeTo]   = useState('')
  const maxDate = todayISO()

  function applyRange() {
    if (!rangeFrom) return
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
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)' }}>
        {(['single', 'range'] as const).map(m => (
          <button key={m} onClick={() => setMode(m)} style={{
            flex: 1, padding: '10px', border: 'none', background: 'transparent', cursor: 'pointer',
            fontSize: '0.78rem', fontWeight: mode === m ? 700 : 500,
            color: mode === m ? ACCENT : 'var(--text-2)',
            borderBottom: mode === m ? `2px solid ${ACCENT}` : '2px solid transparent',
          }}>
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
            <input type="date" className="scribble-input" max={maxDate} value={single} onChange={e => setSingle(e.target.value)} style={{ width: '100%', marginBottom: 12 }} />
            {availableDates.length > 0 && (
              <>
                <p style={{ fontSize: '0.7rem', color: 'var(--text-3)', marginBottom: 6 }}>Recent game days</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
                  {availableDates.slice(0, 8).map(d => (
                    <button key={d} onClick={() => { onSelect(d); onClose() }} style={{
                      padding: '4px 10px', borderRadius: 20, cursor: 'pointer',
                      border: `1px solid ${d === briefDate ? ACCENT : 'var(--border)'}`,
                      background: d === briefDate ? `${ACCENT}15` : 'transparent',
                      color: d === briefDate ? ACCENT : 'var(--text-2)',
                      fontSize: '0.72rem', fontWeight: d === briefDate ? 700 : 400,
                    }}>
                      {fmtShort(d)}
                    </button>
                  ))}
                </div>
              </>
            )}
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => { onSelect(single); onClose() }} disabled={!single} style={{ flex: 1, padding: '8px', borderRadius: 'var(--r-sm)', cursor: 'pointer', background: ACCENT, border: 'none', color: '#fff', fontSize: '0.8rem', fontWeight: 700 }}>
                Go to date
              </button>
              <button onClick={() => { onSelect(todayISO()); onClose() }} style={{ padding: '8px 14px', borderRadius: 'var(--r-sm)', cursor: 'pointer', background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-2)', fontSize: '0.8rem' }}>
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
                <input type="date" className="scribble-input" max={maxDate} value={rangeFrom} onChange={e => setRangeFrom(e.target.value)} style={{ width: '100%' }} />
              </div>
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: '0.7rem', color: 'var(--text-3)', marginBottom: 4 }}>To</p>
                <input type="date" className="scribble-input" max={maxDate} min={rangeFrom || undefined} value={rangeTo} onChange={e => setRangeTo(e.target.value)} style={{ width: '100%' }} />
              </div>
            </div>
            {rangeFrom && (
              <p style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginBottom: 10 }}>
                {availableDates.filter(d => d >= rangeFrom && d <= (rangeTo || maxDate)).length} game day(s) in range
              </p>
            )}
            <button onClick={applyRange} disabled={!rangeFrom} style={{ width: '100%', padding: '8px', borderRadius: 'var(--r-sm)', cursor: rangeFrom ? 'pointer' : 'default', background: rangeFrom ? ACCENT : 'var(--border)', border: 'none', color: rangeFrom ? '#fff' : 'var(--text-3)', fontSize: '0.8rem', fontWeight: 700 }}>
              Jump to first game in range
            </button>
          </>
        )}
      </div>
    </motion.div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function TopStories() {
  const [season,     setSeason]     = useState('2025-26')
  const [riskFilter, setRiskFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all')
  const [briefDate,  setBriefDate]  = useState(todayISO)
  const [filterOpen, setFilterOpen] = useState(false)
  const autoFallbackDone = useRef(false)
  const filterRef        = useRef<HTMLDivElement>(null)

  const { data, loading, error, disabled, refresh } = useDailyBrief(season, briefDate)
  const { data: matchData, loading: matchLoading }   = useMatches(season, 30)

  const availableDates: string[] = matchData?.matches
    ? [...new Set(matchData.matches.map(m => (m.game_date as string).slice(0, 10)))]
        .sort((a, b) => b.localeCompare(a))
    : []

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

  useEffect(() => {
    autoFallbackDone.current = false
    setBriefDate(todayISO())
    setRiskFilter('all')
  }, [season])

  useEffect(() => {
    if (!filterOpen) return
    const handler = (e: MouseEvent) => {
      if (filterRef.current && !filterRef.current.contains(e.target as Node)) setFilterOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [filterOpen])

  if (disabled) return <DisabledState />

  const isToday  = briefDate === todayISO()
  const items    = data?.items ?? []
  const filtered = riskFilter === 'all' ? items : items.filter(i => i.risk_level === riskFilter)
  const sorted   = [...filtered].sort((a, b) => (RISK_ORDER[a.risk_level] ?? 3) - (RISK_ORDER[b.risk_level] ?? 3))

  return (
    <div style={{ padding: '28px 28px', maxWidth: 'var(--content-w)', margin: '0 auto' }}>
      {/* ── Header controls ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>

        {/* Season */}
        <select className="scribble-select" value={season} onChange={e => setSeason(e.target.value)}>
          {SEASONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>

        {/* Active date pill */}
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
            <button onClick={() => { setBriefDate(todayISO()); autoFallbackDone.current = false }} title="Back to today" style={{ background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer', padding: '0 0 0 2px', fontSize: '0.9rem', lineHeight: 1 }}>×</button>
          )}
        </div>

        {/* Filter button + panel */}
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

        {/* Risk filter chips */}
        <div style={{ display: 'flex', gap: 5 }}>
          {(['all', 'high', 'medium', 'low'] as const).map(lvl => {
            const cfg = lvl !== 'all' ? RISK_CFG[lvl] : null
            const isActive = riskFilter === lvl
            return (
              <button key={lvl} onClick={() => setRiskFilter(lvl)} style={{
                padding: '5px 11px', borderRadius: 20, cursor: 'pointer',
                border: `1px solid ${isActive ? (cfg?.color ?? ACCENT) : 'var(--border)'}`,
                background: isActive ? (cfg?.bg ?? 'rgba(255,92,26,0.10)') : 'transparent',
                color: isActive ? (cfg?.color ?? ACCENT) : 'var(--text-2)',
                fontSize: '0.73rem', fontWeight: isActive ? 700 : 500, transition: 'all 0.15s',
              }}>
                {lvl === 'all' ? 'All' : `${cfg?.emoji} ${lvl.charAt(0).toUpperCase() + lvl.slice(1)}`}
              </button>
            )
          })}
        </div>

        {loading && <span style={{ fontSize: '0.78rem', color: 'var(--text-2)' }}>Loading…</span>}
        {error && <span style={{ fontSize: '0.78rem', color: 'var(--error)' }}>{error}</span>}

        <button onClick={() => refresh()} style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', background: 'var(--bg-panel)', border: `1px solid ${ACCENT}`, borderRadius: 'var(--r-sm)', color: ACCENT, fontSize: '0.78rem', fontWeight: 600, cursor: 'pointer' }}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
            <path d="M10 6a4 4 0 1 1-1.07-2.72" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
            <path d="M10 2v2.5H7.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Refresh
        </button>
      </div>

      {/* Auto-fallback notice */}
      {autoFallbackDone.current && !loading && items.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, padding: '8px 14px', background: 'rgba(255,177,0,0.07)', border: '1px solid rgba(255,177,0,0.2)', borderRadius: 'var(--r-sm)' }}>
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden>
            <circle cx="6.5" cy="6.5" r="5.5" stroke="#FFB100" strokeWidth="1.2"/>
            <line x1="6.5" y1="4" x2="6.5" y2="7" stroke="#FFB100" strokeWidth="1.2" strokeLinecap="round"/>
            <circle cx="6.5" cy="9" r="0.6" fill="#FFB100"/>
          </svg>
          <span style={{ fontSize: '0.75rem', color: '#FFB100' }}>
            No games today — showing {briefDate}. Use "Filter by date" to navigate.
          </span>
        </div>
      )}

      {/* Source note */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, padding: '8px 14px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', width: 'fit-content' }}>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
          <circle cx="6" cy="6" r="5" stroke="var(--text-3)" strokeWidth="1.2"/>
          <line x1="6" y1="4" x2="6" y2="6.5" stroke="var(--text-3)" strokeWidth="1.2" strokeLinecap="round"/>
          <circle cx="6" cy="8.5" r="0.5" fill="var(--text-3)"/>
        </svg>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>
          ESPN, CBS Sports and RotoWire · {briefDate}
        </span>
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {[...Array(3)].map((_, i) => <div key={i} style={{ height: 110, background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)' }} className="skeleton-row" />)}
        </div>
      )}

      {/* Empty state */}
      {!loading && sorted.length === 0 && !matchLoading && (
        <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text-2)' }}>
          <p style={{ fontSize: '1.5rem', marginBottom: 10 }}>📰</p>
          <p style={{ fontWeight: 700, color: 'var(--text-1)', marginBottom: 6 }}>No stories available</p>
          <p style={{ fontSize: '0.85rem' }}>
            {riskFilter !== 'all'
              ? `No ${riskFilter}-risk matchups for ${briefDate}. Try a different filter.`
              : availableDates.length > 0
                ? `No games on ${briefDate}. Use "Filter by date" to browse other days.`
                : 'No games found for this season. Check that the ingestion pipeline has run.'}
          </p>
          {riskFilter === 'all' && availableDates.length > 0 && (
            <button onClick={() => { setBriefDate(availableDates[0]); autoFallbackDone.current = true }} style={{ marginTop: 12, padding: '7px 16px', borderRadius: 'var(--r-sm)', background: 'transparent', border: `1px solid ${ACCENT}`, color: ACCENT, fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer' }}>
              Go to {availableDates[0]}
            </button>
          )}
        </div>
      )}

      {/* Stories */}
      {!loading && sorted.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {sorted.map((item, i) => <StoryCard key={item.game_id} item={item} index={i} />)}
        </div>
      )}
    </div>
  )
}
