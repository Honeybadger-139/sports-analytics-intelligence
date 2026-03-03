import { useState, useCallback } from 'react'
import type React from 'react'
import { motion } from 'framer-motion'
import { useMatches, useTodaysPredictions } from '../../hooks/useApi'
import type { MatchRow, TodayGamePrediction } from '../../types'
import GameStatsModal from './GameStatsModal'

const ACCENT  = '#FF5C1A'
const SEASONS = ['2025-26', '2024-25', '2023-24']

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
  } catch { return iso }
}

// ── Today's prediction card ──────────────────────────────────────────────────

function WinBar({ homeProb, homeTeam, awayTeam }: { homeProb: number; homeTeam: string; awayTeam: string }) {
  const awayProb = 1 - homeProb
  return (
    <div style={{ width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: '0.7rem', color: homeProb >= 0.5 ? ACCENT : 'var(--text-3)', fontWeight: homeProb >= 0.5 ? 700 : 400 }}>
          {homeTeam} {(homeProb * 100).toFixed(0)}%
        </span>
        <span style={{ fontSize: '0.7rem', color: awayProb > homeProb ? ACCENT : 'var(--text-3)', fontWeight: awayProb > homeProb ? 700 : 400 }}>
          {awayTeam} {(awayProb * 100).toFixed(0)}%
        </span>
      </div>
      <div style={{ height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden', display: 'flex' }}>
        <div style={{ width: `${homeProb * 100}%`, background: ACCENT, borderRadius: '3px 0 0 3px', transition: 'width 0.4s ease' }} />
        <div style={{ flex: 1, background: 'var(--border-mid)' }} />
      </div>
    </div>
  )
}

function TodayCard({ game, index, onSelect }: { game: TodayGamePrediction; index: number; onSelect: (id: string) => void }) {
  const ensemblePred = game.predictions?.ensemble ?? game.predictions?.xgboost ?? Object.values(game.predictions ?? {})[0]

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: index * 0.05 }}
      onClick={() => onSelect(game.game_id)}
      style={{
        background: 'var(--bg-panel)', border: `1px solid ${ACCENT}30`,
        borderRadius: 'var(--r-md)', overflow: 'hidden', cursor: 'pointer',
        transition: 'border-color 0.15s, transform 0.1s',
      }}
      whileHover={{ scale: 1.01 }}
    >
      <div style={{ padding: '6px 16px', background: `${ACCENT}12`, borderBottom: `1px solid ${ACCENT}20` }}>
        <span style={{ fontSize: '0.68rem', fontWeight: 700, color: ACCENT, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Today's Game · Click for box score
        </span>
      </div>

      <div style={{ padding: '16px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, marginBottom: 16 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '1.1rem', color: 'var(--text-1)' }}>
            {game.home_team}
          </span>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-3)', fontWeight: 500 }}>vs</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '1.1rem', color: 'var(--text-1)' }}>
            {game.away_team}
          </span>
        </div>

        {ensemblePred ? (
          <div style={{ marginBottom: 12 }}>
            <WinBar homeProb={ensemblePred.home_win_prob} homeTeam={game.home_team} awayTeam={game.away_team} />
            <div style={{ marginTop: 6, textAlign: 'center' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-3)' }}>
                Confidence: <span style={{ color: 'var(--text-2)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  {(ensemblePred.confidence * 100).toFixed(1)}%
                </span>
              </span>
            </div>
          </div>
        ) : (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-3)', textAlign: 'center', marginBottom: 12 }}>No predictions available</p>
        )}
      </div>
    </motion.div>
  )
}

// ── Match history row ─────────────────────────────────────────────────────────

function MatchRow({ match, index, onSelect }: {
  match: MatchRow
  index: number
  onSelect: (id: string) => void
}) {
  const completed = match.winner_team_id != null
  const homeWon   = completed && match.home_score != null && match.away_score != null && match.home_score > match.away_score

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15, delay: index * 0.02 }}
      onClick={() => onSelect(match.game_id)}
      style={{
        background: 'var(--bg-panel)', border: '1px solid var(--border)',
        borderRadius: 'var(--r-md)', padding: '12px 18px',
        display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
        cursor: 'pointer', transition: 'border-color 0.15s, background 0.15s',
      }}
      whileHover={{ borderColor: ACCENT + '60', backgroundColor: `${ACCENT}06` } as Record<string, string>}
    >
      {/* Date */}
      <span style={{ fontSize: '0.72rem', color: 'var(--text-3)', fontFamily: 'var(--font-mono)', minWidth: 90 }}>
        {fmtDate(match.game_date)}
      </span>

      {/* Teams */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{
          fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '0.9rem',
          color: homeWon ? 'var(--text-1)' : 'var(--text-2)',
        }}>
          {match.home_team}
        </span>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-3)' }}>vs</span>
        <span style={{
          fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '0.9rem',
          color: !homeWon && completed ? 'var(--text-1)' : 'var(--text-2)',
        }}>
          {match.away_team}
        </span>
      </div>

      {/* Score */}
      {completed && match.home_score != null ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '0.9rem', color: homeWon ? 'var(--success)' : 'var(--text-2)' }}>
            {match.home_score}
          </span>
          <span style={{ color: 'var(--text-3)', fontSize: '0.8rem' }}>–</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '0.9rem', color: !homeWon ? 'var(--success)' : 'var(--text-2)' }}>
            {match.away_score}
          </span>
        </div>
      ) : (
        <span style={{ fontSize: '0.72rem', color: 'var(--text-3)', fontStyle: 'italic' }}>Upcoming</span>
      )}

      {/* Status pill */}
      <span style={{
        padding: '2px 8px', borderRadius: 20, fontSize: '0.68rem', fontWeight: 600,
        background: completed ? 'rgba(0,214,143,0.10)' : 'rgba(255,177,0,0.10)',
        color: completed ? 'var(--success)' : 'var(--warning)',
        fontFamily: 'var(--font-mono)',
      }}>
        {completed ? 'Final' : 'Upcoming'}
      </span>

      {/* Click hint */}
      <span style={{ fontSize: '0.62rem', color: 'var(--text-3)', opacity: 0.6 }}>
        ↗ Details
      </span>
    </motion.div>
  )
}

// ── Date filter controls ─────────────────────────────────────────────────────

type FilterMode = 'single' | 'range'

interface DateFilters {
  season: string
  dateFrom: string
  dateTo: string
}

function yesterday(): string {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return d.toISOString().slice(0, 10)
}

function DateFilterBar({ filters, onChange }: {
  filters: DateFilters
  onChange: (f: Partial<DateFilters>) => void
}) {
  const [mode, setMode] = useState<FilterMode>('single')

  function switchMode(next: FilterMode) {
    setMode(next)
    if (next === 'single') {
      const d = yesterday()
      onChange({ dateFrom: d, dateTo: d })
    } else {
      onChange({ dateFrom: '', dateTo: '' })
    }
  }

  const inputStyle: React.CSSProperties = {
    background: 'var(--bg-base)', border: '1px solid var(--border)',
    borderRadius: 'var(--r-sm)', padding: '4px 8px',
    color: 'var(--text-1)', fontSize: '0.8rem',
    fontFamily: 'var(--font-mono)', cursor: 'pointer',
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
      padding: '12px 16px',
      background: 'var(--bg-panel)', border: '1px solid var(--border)',
      borderRadius: 'var(--r-md)', marginBottom: 20,
    }}>
      {/* Season */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-3)', fontWeight: 600 }}>Season</span>
        <select
          className="scribble-select"
          value={filters.season}
          onChange={e => onChange({ season: e.target.value, dateFrom: '', dateTo: '' })}
          style={{ fontSize: '0.8rem' }}
        >
          {SEASONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div style={{ width: 1, height: 24, background: 'var(--border)', margin: '0 4px' }} />

      {/* Mode toggle pill */}
      <div style={{
        display: 'flex', alignItems: 'center',
        background: 'var(--bg-base)', border: '1px solid var(--border)',
        borderRadius: 20, padding: 3, gap: 2,
      }}>
        {(['single', 'range'] as FilterMode[]).map(m => (
          <button
            key={m}
            onClick={() => switchMode(m)}
            style={{
              padding: '3px 12px', borderRadius: 16,
              border: 'none', cursor: 'pointer',
              fontSize: '0.72rem', fontWeight: 600,
              background: mode === m ? ACCENT : 'transparent',
              color: mode === m ? '#fff' : 'var(--text-3)',
              transition: 'background 0.15s, color 0.15s',
            }}
          >
            {m === 'single' ? 'Single Date' : 'Date Range'}
          </button>
        ))}
      </div>

      <div style={{ width: 1, height: 24, background: 'var(--border)', margin: '0 4px' }} />

      {/* Date inputs */}
      {mode === 'single' ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-3)', fontWeight: 600 }}>Date</span>
          <input
            type="date"
            value={filters.dateFrom}
            onChange={e => onChange({ dateFrom: e.target.value, dateTo: e.target.value })}
            style={inputStyle}
          />
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-3)', fontWeight: 600 }}>From</span>
            <input
              type="date"
              value={filters.dateFrom}
              onChange={e => onChange({ dateFrom: e.target.value })}
              style={inputStyle}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-3)', fontWeight: 600 }}>To</span>
            <input
              type="date"
              value={filters.dateTo}
              onChange={e => onChange({ dateTo: e.target.value })}
              style={inputStyle}
            />
          </div>
        </>
      )}

      {/* Clear dates */}
      {(filters.dateFrom || filters.dateTo) && (
        <button
          onClick={() => onChange({ dateFrom: '', dateTo: '' })}
          style={{
            padding: '4px 10px', background: 'transparent',
            border: '1px solid var(--border)', borderRadius: 'var(--r-sm)',
            color: 'var(--text-3)', fontSize: '0.72rem', cursor: 'pointer',
          }}
        >
          Clear
        </button>
      )}

      {/* Active filter badge */}
      {(filters.dateFrom || filters.dateTo) && (
        <span style={{
          padding: '2px 8px', borderRadius: 20,
          background: `${ACCENT}18`, color: ACCENT,
          fontSize: '0.68rem', fontWeight: 600,
        }}>
          {mode === 'single' ? `${filters.dateFrom}` : 'Date filter active'}
        </span>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function MatchPreviews() {
  const [filters, setFilters] = useState<DateFilters>({ season: '2025-26', dateFrom: '', dateTo: '' })
  const [limit, setLimit]     = useState(20)
  const [selectedGame, setSelectedGame] = useState<string | null>(null)

  const handleFilterChange = useCallback((partial: Partial<DateFilters>) => {
    setFilters(prev => ({ ...prev, ...partial }))
  }, [])

  const { data: matches, loading: matchLoading } = useMatches(
    filters.season,
    limit,
    filters.dateFrom || undefined,
    filters.dateTo || undefined,
  )
  const { data: todayData, loading: todayLoading, error: todayError, refresh } = useTodaysPredictions()

  const todayGames: TodayGamePrediction[] = todayData?.games ?? []
  const recentMatches: MatchRow[]         = matches?.matches ?? []

  return (
    <div style={{ padding: '28px 28px', maxWidth: 'var(--content-w)', margin: '0 auto' }}>

      {/* ── Date filter bar ── */}
      <DateFilterBar filters={filters} onChange={handleFilterChange} />

      {/* ── Refresh button ── */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 28 }}>
        <button
          onClick={() => refresh()}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '7px 14px', background: 'var(--bg-panel)',
            border: `1px solid ${ACCENT}`, borderRadius: 'var(--r-sm)',
            color: ACCENT, fontSize: '0.78rem', fontWeight: 600, cursor: 'pointer',
          }}
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
            <path d="M10 6a4 4 0 1 1-1.07-2.72" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
            <path d="M10 2v2.5H7.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Refresh predictions
        </button>
      </div>

      {/* ── Today's predictions ── */}
      <p className="section-label" style={{ marginBottom: 12, color: ACCENT }}>
        Today's Games &amp; Predictions
        {todayData && ` — ${todayData.date}`}
      </p>

      {todayLoading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 12, marginBottom: 36 }}>
          {[...Array(3)].map((_, i) => (
            <div key={i} style={{ height: 160, background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)' }} className="skeleton-row" />
          ))}
        </div>
      )}

      {!todayLoading && todayError && (
        <div style={{ padding: '16px 20px', background: 'rgba(255,76,106,0.07)', border: '1px solid rgba(255,76,106,0.2)', borderRadius: 'var(--r-md)', marginBottom: 28 }}>
          <p style={{ fontSize: '0.85rem', color: 'var(--error)' }}>{todayError}</p>
        </div>
      )}

      {!todayLoading && !todayError && todayGames.length === 0 && (
        <div style={{
          textAlign: 'center', padding: '28px 20px', marginBottom: 28,
          background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)',
        }}>
          <p style={{ fontSize: '1.4rem', marginBottom: 8 }}>🏀</p>
          <p style={{ fontWeight: 700, color: 'var(--text-1)', marginBottom: 4 }}>No games scheduled today</p>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-2)' }}>Check back later or browse recent match history below.</p>
        </div>
      )}

      {!todayLoading && todayGames.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 12, marginBottom: 36 }}>
          {todayGames.map((g, i) => (
            <TodayCard key={g.game_id} game={g} index={i} onSelect={setSelectedGame} />
          ))}
        </div>
      )}

      {/* ── Recent match history ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <p className="section-label" style={{ color: ACCENT, margin: 0 }}>
          Recent Match History
          {(filters.dateFrom || filters.dateTo) && (
            <span style={{ fontSize: '0.72rem', fontWeight: 400, color: 'var(--text-3)', marginLeft: 8 }}>
              {filters.dateFrom && filters.dateTo
                ? `${filters.dateFrom} → ${filters.dateTo}`
                : filters.dateFrom ? `from ${filters.dateFrom}`
                : `to ${filters.dateTo}`}
            </span>
          )}
        </p>
        <select
          className="scribble-select scribble-select--sm"
          value={limit}
          onChange={e => setLimit(Number(e.target.value))}
        >
          {[10, 20, 50].map(n => <option key={n} value={n}>{n} games</option>)}
        </select>
      </div>

      {matchLoading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[...Array(5)].map((_, i) => (
            <div key={i} style={{ height: 52, background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)' }} className="skeleton-row" />
          ))}
        </div>
      )}

      {!matchLoading && recentMatches.length === 0 && (
        <div style={{
          textAlign: 'center', padding: '28px 20px',
          background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)',
        }}>
          <p style={{ color: 'var(--text-2)', fontSize: '0.85rem' }}>
            No matches found for the selected filters.
            {(filters.dateFrom || filters.dateTo) && (
              <span> Try adjusting or clearing the date range.</span>
            )}
          </p>
        </div>
      )}

      {!matchLoading && recentMatches.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {recentMatches.map((m, i) => (
            <MatchRow key={m.game_id} match={m} index={i} onSelect={setSelectedGame} />
          ))}
        </div>
      )}

      <p style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginTop: 14 }}>
        Showing {recentMatches.length} games · Season {filters.season} · Click any row to view box score &amp; stats
      </p>

      {/* ── Game Stats Modal ── */}
      {selectedGame && (
        <GameStatsModal gameId={selectedGame} onClose={() => setSelectedGame(null)} />
      )}
    </div>
  )
}
