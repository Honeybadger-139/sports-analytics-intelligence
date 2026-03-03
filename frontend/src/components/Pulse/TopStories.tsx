import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { useDailyBrief, useMatches } from '../../hooks/useApi'
import type { BriefItem } from '../../types'

const ACCENT   = '#FF5C1A'
const SEASONS  = ['2025-26', '2024-25', '2023-24']

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

function fmtDisplayDate(iso: string): string {
  if (iso === todayISO()) return 'Today'
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
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
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = 'var(--border-mid)'
        e.currentTarget.style.boxShadow = 'var(--shadow-sm)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = 'var(--border)'
        e.currentTarget.style.boxShadow = 'none'
      }}
    >
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0, width: 3,
        background: risk.color, borderRadius: '3px 0 0 3px',
      }} />

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

        <p style={{ fontSize: '0.84rem', color: 'var(--text-2)', lineHeight: 1.7, margin: 0 }}>
          {item.summary.length > 300 ? item.summary.slice(0, 300) + '… ' : item.summary}
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
  const [season,     setSeason]     = useState('2025-26')
  const [riskFilter, setRiskFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all')
  const [briefDate,  setBriefDate]  = useState(todayISO)
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

  // Reset when season changes
  useEffect(() => {
    autoFallbackDone.current = false
    setBriefDate(todayISO())
    setRiskFilter('all')
  }, [season])

  const currentIdx = availableDates.indexOf(briefDate)
  const canGoPrev  = currentIdx === -1 ? availableDates.length > 0 : currentIdx < availableDates.length - 1
  const canGoNext  = currentIdx > 0
  const isToday    = briefDate === todayISO()

  function goPrev() {
    if (currentIdx === -1) setBriefDate(availableDates[0])
    else if (canGoPrev) setBriefDate(availableDates[currentIdx + 1])
  }
  function goNext() {
    if (canGoNext) setBriefDate(availableDates[currentIdx - 1])
  }

  if (disabled) return <DisabledState />

  const items: BriefItem[] = data?.items ?? []
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
              background: 'none', border: 'none', padding: '4px 8px',
              cursor: canGoPrev ? 'pointer' : 'default',
              color: canGoPrev ? 'var(--text-1)' : 'var(--text-3)', borderRadius: 4,
            }}
          >←</button>
          <span style={{ padding: '2px 8px', fontSize: '0.78rem', fontWeight: 600, color: isToday ? ACCENT : 'var(--text-1)', minWidth: 120, textAlign: 'center' }}>
            {fmtDisplayDate(briefDate)}
          </span>
          <button
            onClick={goNext}
            disabled={!canGoNext}
            title="Next game date"
            style={{
              background: 'none', border: 'none', padding: '4px 8px',
              cursor: canGoNext ? 'pointer' : 'default',
              color: canGoNext ? 'var(--text-1)' : 'var(--text-3)', borderRadius: 4,
            }}
          >→</button>
        </div>

        {!isToday && (
          <button
            onClick={() => { setBriefDate(todayISO()); autoFallbackDone.current = false }}
            style={{
              padding: '5px 10px', borderRadius: 'var(--r-sm)', background: 'transparent',
              border: `1px solid ${ACCENT}30`, color: ACCENT, fontSize: '0.73rem', fontWeight: 600, cursor: 'pointer',
            }}
          >Today</button>
        )}

        {/* Risk filter chips */}
        <div style={{ display: 'flex', gap: 5, marginLeft: 4 }}>
          {(['all', 'high', 'medium', 'low'] as const).map(lvl => {
            const cfg = lvl !== 'all' ? RISK_CFG[lvl] : null
            const isActive = riskFilter === lvl
            return (
              <button
                key={lvl}
                onClick={() => setRiskFilter(lvl)}
                style={{
                  padding: '5px 11px', borderRadius: 20, cursor: 'pointer',
                  border: `1px solid ${isActive ? (cfg?.color ?? ACCENT) : 'var(--border)'}`,
                  background: isActive ? (cfg?.bg ?? 'rgba(255,92,26,0.10)') : 'transparent',
                  color: isActive ? (cfg?.color ?? ACCENT) : 'var(--text-2)',
                  fontSize: '0.73rem', fontWeight: isActive ? 700 : 500,
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

      {/* Auto-fallback notice */}
      {autoFallbackDone.current && !loading && items.length > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14,
          padding: '8px 14px', background: 'rgba(255,177,0,0.07)', border: '1px solid rgba(255,177,0,0.2)',
          borderRadius: 'var(--r-sm)',
        }}>
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden>
            <circle cx="6.5" cy="6.5" r="5.5" stroke="#FFB100" strokeWidth="1.2"/>
            <line x1="6.5" y1="4" x2="6.5" y2="7" stroke="#FFB100" strokeWidth="1.2" strokeLinecap="round"/>
            <circle cx="6.5" cy="9" r="0.6" fill="#FFB100"/>
          </svg>
          <span style={{ fontSize: '0.75rem', color: '#FFB100' }}>
            No games today — showing {briefDate}. Use ← → to navigate.
          </span>
        </div>
      )}

      {/* Source note */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16,
        padding: '8px 14px', background: 'var(--bg-elevated)', border: '1px solid var(--border)',
        borderRadius: 'var(--r-sm)', width: 'fit-content',
      }}>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
          <circle cx="6" cy="6" r="5" stroke="var(--text-3)" strokeWidth="1.2"/>
          <line x1="6" y1="4" x2="6" y2="6.5" stroke="var(--text-3)" strokeWidth="1.2" strokeLinecap="round"/>
          <circle cx="6" cy="8.5" r="0.5" fill="var(--text-3)"/>
        </svg>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>
          Stories sourced from ESPN, CBS Sports and RotoWire via RAG intelligence context · {briefDate}
        </span>
      </div>

      {/* Loading skeletons */}
      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {[...Array(3)].map((_, i) => (
            <div key={i} style={{ height: 110, background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)' }} className="skeleton-row" />
          ))}
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
                ? `No games on ${briefDate}. Use ← to go to a previous game day.`
                : 'No games found for this season. Check that the ingestion pipeline has run.'}
          </p>
          {riskFilter === 'all' && availableDates.length > 0 && (
            <button
              onClick={() => { setBriefDate(availableDates[0]); autoFallbackDone.current = true }}
              style={{
                marginTop: 12, padding: '7px 16px', borderRadius: 'var(--r-sm)',
                background: 'transparent', border: `1px solid ${ACCENT}`,
                color: ACCENT, fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer',
              }}
            >
              Go to {availableDates[0]}
            </button>
          )}
        </div>
      )}

      {/* Story cards */}
      {!loading && sorted.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {sorted.map((item, i) => <StoryCard key={item.game_id} item={item} index={i} />)}
        </div>
      )}
    </div>
  )
}
