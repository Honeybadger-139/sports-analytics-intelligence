import { useState } from 'react'
import { motion } from 'framer-motion'
import { useMatches, useTodaysPredictions } from '../../hooks/useApi'
import type { MatchRow, TodayGamePrediction } from '../../types'

const ACCENT  = '#FF5C1A'
const SEASONS = ['2025-26', '2024-25', '2023-24']

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
  } catch { return iso }
}

function WinBar({ homeProb, label }: { homeProb: number; label: string }) {
  const awayProb = 1 - homeProb
  const homePct  = (homeProb * 100).toFixed(0)
  const awayPct  = (awayProb * 100).toFixed(0)

  return (
    <div style={{ width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: '0.68rem', color: homeProb >= 0.5 ? ACCENT : 'var(--text-3)', fontWeight: homeProb >= 0.5 ? 700 : 400 }}>
          Home {homePct}%
        </span>
        <span style={{ fontSize: '0.68rem', color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>{label}</span>
        <span style={{ fontSize: '0.68rem', color: awayProb > homeProb ? ACCENT : 'var(--text-3)', fontWeight: awayProb > homeProb ? 700 : 400 }}>
          Away {awayPct}%
        </span>
      </div>
      <div style={{ height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden', display: 'flex' }}>
        <div style={{ width: `${homeProb * 100}%`, background: ACCENT, borderRadius: '3px 0 0 3px', transition: 'width 0.4s ease' }} />
        <div style={{ flex: 1, background: 'var(--border-mid)' }} />
      </div>
    </div>
  )
}

function TodayCard({ game, index }: { game: TodayGamePrediction; index: number }) {
  const ensemblePred = game.predictions?.ensemble ?? game.predictions?.xgboost ?? Object.values(game.predictions ?? {})[0]

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: index * 0.05 }}
      style={{
        background: 'var(--bg-panel)', border: `1px solid ${ACCENT}30`,
        borderRadius: 'var(--r-md)', overflow: 'hidden',
      }}
    >
      {/* Chip */}
      <div style={{ padding: '6px 16px', background: `${ACCENT}12`, borderBottom: `1px solid ${ACCENT}20` }}>
        <span style={{ fontSize: '0.68rem', fontWeight: 700, color: ACCENT, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Today's Game
        </span>
      </div>

      <div style={{ padding: '16px 20px' }}>
        {/* Matchup */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, marginBottom: 16 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '1.1rem', color: 'var(--text-1)' }}>
            {game.home_team}
          </span>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-3)', fontWeight: 500 }}>vs</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '1.1rem', color: 'var(--text-1)' }}>
            {game.away_team}
          </span>
        </div>

        {/* Prediction bar */}
        {ensemblePred ? (
          <div style={{ marginBottom: 12 }}>
            <WinBar homeProb={ensemblePred.home_win_prob} label="ensemble" />
            <div style={{ marginTop: 6, textAlign: 'center' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-3)' }}>
                Confidence: <span style={{ color: 'var(--text-2)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  {(ensemblePred.confidence * 100).toFixed(1)}%
                </span>
              </span>
            </div>
          </div>
        ) : (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-3)', textAlign: 'center', marginBottom: 12 }}>No model predictions available</p>
        )}

        <p style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: 'var(--text-3)', textAlign: 'center' }}>
          {game.game_id}
        </p>
      </div>
    </motion.div>
  )
}

function MatchCard({ match, index }: { match: MatchRow; index: number }) {
  const completed = match.winner_team_id != null
  const homeWon   = completed && match.home_score != null && match.away_score != null && match.home_score > match.away_score

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: index * 0.03 }}
      style={{
        background: 'var(--bg-panel)', border: '1px solid var(--border)',
        borderRadius: 'var(--r-md)', padding: '14px 18px',
        display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
        transition: 'border-color 0.15s',
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border-mid)')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
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

      {/* Score / status */}
      {completed && match.home_score != null ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{
            fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '0.9rem',
            color: homeWon ? 'var(--success)' : 'var(--text-2)',
          }}>
            {match.home_score}
          </span>
          <span style={{ color: 'var(--text-3)', fontSize: '0.8rem' }}>–</span>
          <span style={{
            fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '0.9rem',
            color: !homeWon ? 'var(--success)' : 'var(--text-2)',
          }}>
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
    </motion.div>
  )
}

export default function MatchPreviews() {
  const [season, setSeason] = useState('2025-26')
  const [limit,  setLimit]  = useState(20)

  const { data: matches,  loading: matchLoading  } = useMatches(season, limit)
  const { data: todayData, loading: todayLoading, error: todayError, refresh } = useTodaysPredictions()

  const todayGames: TodayGamePrediction[] = todayData?.games ?? []
  const recentMatches: MatchRow[]         = matches?.matches ?? []

  return (
    <div style={{ padding: '28px 28px', maxWidth: 'var(--content-w)', margin: '0 auto' }}>
      {/* Header controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 28, flexWrap: 'wrap' }}>
        <select className="scribble-select" value={season} onChange={e => setSeason(e.target.value)}>
          {SEASONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
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
          {todayGames.map((g, i) => <TodayCard key={g.game_id} game={g} index={i} />)}
        </div>
      )}

      {/* ── Recent match history ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <p className="section-label" style={{ color: ACCENT, margin: 0 }}>
          Recent Match History
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
        <p style={{ color: 'var(--text-2)', fontSize: '0.85rem', padding: '16px 0' }}>No match data for {season}.</p>
      )}

      {!matchLoading && recentMatches.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {recentMatches.map((m, i) => <MatchCard key={m.game_id} match={m} index={i} />)}
        </div>
      )}

      <p style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginTop: 14 }}>
        Showing last {recentMatches.length} games from <code style={{ fontFamily: 'var(--font-mono)' }}>matches</code> table · Season {season}
      </p>
    </div>
  )
}
