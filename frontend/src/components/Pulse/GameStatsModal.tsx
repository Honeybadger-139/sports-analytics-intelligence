import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useGameStats, useGamePrediction } from '../../hooks/useApi'
import type { PlayerBoxScore, TeamBoxScore } from '../../types'

const ACCENT = '#FF5C1A'
const BG_OVERLAY = 'rgba(0,0,0,0.75)'

function pct(val: number | null | undefined, decimals = 1): string {
  if (val == null) return '—'
  return `${(Number(val) * 100).toFixed(decimals)}%`
}

function num(val: number | null | undefined): string {
  if (val == null) return '—'
  return String(val)
}

function rating(val: number | null | undefined): string {
  if (val == null) return '—'
  return Number(val).toFixed(1)
}

// ── Team Stats Comparison (Statistics tab) ───────────────────────────────────

function StatBar({ label, homeVal, awayVal, higher = 'home' }: {
  label: string
  homeVal: string
  awayVal: string
  higher?: 'home' | 'away' | 'neither'
}) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{
          fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '0.85rem',
          color: higher === 'home' ? 'var(--text-1)' : 'var(--text-2)',
        }}>{homeVal}</span>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-3)', textAlign: 'center', flex: 1, padding: '0 12px' }}>
          {label}
        </span>
        <span style={{
          fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '0.85rem',
          color: higher === 'away' ? 'var(--text-1)' : 'var(--text-2)',
        }}>{awayVal}</span>
      </div>
    </div>
  )
}

function StatisticsTab({ home, away, homeName, awayName }: {
  home: TeamBoxScore | null
  away: TeamBoxScore | null
  homeName: string
  awayName: string
}) {
  if (!home && !away) {
    return (
      <p style={{ color: 'var(--text-3)', textAlign: 'center', padding: '40px 20px', fontSize: '0.85rem' }}>
        Team statistics not available for this game.
      </p>
    )
  }

  const rows: { label: string; home: string; away: string; homeNum: number; awayNum: number }[] = [
    { label: 'Field Goal %', home: pct(home?.field_goal_pct), away: pct(away?.field_goal_pct), homeNum: home?.field_goal_pct ?? 0, awayNum: away?.field_goal_pct ?? 0 },
    { label: '3-Point %', home: pct(home?.three_point_pct), away: pct(away?.three_point_pct), homeNum: home?.three_point_pct ?? 0, awayNum: away?.three_point_pct ?? 0 },
    { label: 'Free Throw %', home: pct(home?.free_throw_pct), away: pct(away?.free_throw_pct), homeNum: home?.free_throw_pct ?? 0, awayNum: away?.free_throw_pct ?? 0 },
    { label: 'eFG%', home: pct(home?.effective_fg_pct), away: pct(away?.effective_fg_pct), homeNum: home?.effective_fg_pct ?? 0, awayNum: away?.effective_fg_pct ?? 0 },
    { label: 'True Shooting %', home: pct(home?.true_shooting_pct), away: pct(away?.true_shooting_pct), homeNum: home?.true_shooting_pct ?? 0, awayNum: away?.true_shooting_pct ?? 0 },
    { label: 'Offensive Rating', home: rating(home?.offensive_rating), away: rating(away?.offensive_rating), homeNum: home?.offensive_rating ?? 0, awayNum: away?.offensive_rating ?? 0 },
    { label: 'Defensive Rating', home: rating(home?.defensive_rating), away: rating(away?.defensive_rating), homeNum: home?.defensive_rating ?? 0, awayNum: away?.defensive_rating ?? 0 },
    { label: 'Pace', home: rating(home?.pace), away: rating(away?.pace), homeNum: home?.pace ?? 0, awayNum: away?.pace ?? 0 },
    { label: 'Rebounds', home: num(home?.rebounds), away: num(away?.rebounds), homeNum: home?.rebounds ?? 0, awayNum: away?.rebounds ?? 0 },
    { label: 'Assists', home: num(home?.assists), away: num(away?.assists), homeNum: home?.assists ?? 0, awayNum: away?.assists ?? 0 },
    { label: 'Steals', home: num(home?.steals), away: num(away?.steals), homeNum: home?.steals ?? 0, awayNum: away?.steals ?? 0 },
    { label: 'Blocks', home: num(home?.blocks), away: num(away?.blocks), homeNum: home?.blocks ?? 0, awayNum: away?.blocks ?? 0 },
    { label: 'Turnovers', home: num(home?.turnovers), away: num(away?.turnovers), homeNum: home?.turnovers ?? 0, awayNum: away?.turnovers ?? 0 },
  ]

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, padding: '0 4px' }}>
        <span style={{ fontWeight: 700, fontSize: '0.9rem', color: ACCENT }}>{homeName}</span>
        <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text-3)' }}>{awayName}</span>
      </div>
      {rows.map(r => (
        <StatBar
          key={r.label}
          label={r.label}
          homeVal={r.home}
          awayVal={r.away}
          higher={r.homeNum > r.awayNum ? 'home' : r.awayNum > r.homeNum ? 'away' : 'neither'}
        />
      ))}
    </div>
  )
}

// ── Player Table ─────────────────────────────────────────────────────────────

const STAT_COLS = [
  { key: 'minutes', label: 'MIN', width: 44 },
  { key: 'points', label: 'PTS', width: 36 },
  { key: 'rebounds', label: 'REB', width: 36 },
  { key: 'assists', label: 'AST', width: 36 },
  { key: 'steals', label: 'STL', width: 36 },
  { key: 'blocks', label: 'BLK', width: 36 },
  { key: 'turnovers', label: 'TO', width: 36 },
  { key: 'fgm_a', label: 'FG', width: 52 },
  { key: '3pm_a', label: '3PT', width: 52 },
  { key: 'ftm_a', label: 'FT', width: 52 },
  { key: 'plus_minus', label: '+/-', width: 40 },
]

function PlayerRow({ player, index }: { player: PlayerBoxScore; index: number }) {
  const isTopScorer = index === 0

  function getVal(key: string) {
    if (key === 'fgm_a') return `${player.field_goals_made}/${player.field_goals_attempted}`
    if (key === '3pm_a') return `${player.three_points_made}/${player.three_points_attempted}`
    if (key === 'ftm_a') return `${player.free_throws_made}/${player.free_throws_attempted}`
    if (key === 'minutes') return player.minutes ? Math.round(parseFloat(player.minutes)).toString() : '—'
    if (key === 'plus_minus') {
      const pm = player.plus_minus
      if (pm == null) return '—'
      return pm > 0 ? `+${pm}` : String(pm)
    }
    return String((player as unknown as Record<string, unknown>)[key] ?? '—')
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center',
      padding: '9px 0',
      borderBottom: '1px solid var(--border)',
      background: isTopScorer ? `${ACCENT}08` : 'transparent',
    }}>
      {/* Player name */}
      <div style={{ width: 160, minWidth: 140, paddingRight: 8 }}>
        <span style={{
          fontSize: '0.82rem', fontWeight: isTopScorer ? 700 : 500,
          color: isTopScorer ? 'var(--text-1)' : 'var(--text-2)',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block',
        }}>
          {player.player_name}
        </span>
      </div>
      {/* Stats */}
      {STAT_COLS.map(col => (
        <div key={col.key} style={{ width: col.width, minWidth: col.width, textAlign: 'center' }}>
          <span style={{
            fontSize: '0.78rem',
            fontFamily: 'var(--font-mono)',
            fontWeight: col.key === 'points' && player.points >= 20 ? 700 : 400,
            color: col.key === 'plus_minus'
              ? (player.plus_minus ?? 0) > 0 ? 'var(--success)' : (player.plus_minus ?? 0) < 0 ? 'var(--error)' : 'var(--text-3)'
              : col.key === 'points' && player.points >= 20
                ? ACCENT
                : 'var(--text-2)',
          }}>
            {getVal(col.key)}
          </span>
        </div>
      ))}
    </div>
  )
}

function PlayerTable({ players, teamName }: { players: PlayerBoxScore[]; teamName: string }) {
  return (
    <div style={{ marginBottom: 28 }}>
      {/* Team header */}
      <div style={{
        padding: '7px 0 7px 0',
        borderBottom: `2px solid ${ACCENT}40`,
        marginBottom: 4,
      }}>
        <span style={{ fontSize: '0.78rem', fontWeight: 700, color: ACCENT, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          {teamName}
        </span>
      </div>
      {/* Column headers */}
      <div style={{ display: 'flex', alignItems: 'center', padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
        <div style={{ width: 160, minWidth: 140 }}>
          <span style={{ fontSize: '0.68rem', color: 'var(--text-3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Player
          </span>
        </div>
        {STAT_COLS.map(col => (
          <div key={col.key} style={{ width: col.width, minWidth: col.width, textAlign: 'center' }}>
            <span style={{ fontSize: '0.68rem', color: 'var(--text-3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              {col.label}
            </span>
          </div>
        ))}
      </div>
      {/* Rows */}
      {players.map((p, i) => <PlayerRow key={p.player_id} player={p} index={i} />)}
    </div>
  )
}

// ── ML Prediction Tab ─────────────────────────────────────────────────────────

function PredictionTab({ gameId, homeTeam, awayTeam }: { gameId: string; homeTeam: string; awayTeam: string }) {
  const { data, loading, error } = useGamePrediction(gameId)

  if (loading) return <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-3)' }}>Loading prediction...</div>
  if (error) return <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--error)', fontSize: '0.85rem' }}>{error}</div>
  if (!data) return null

  const ensemble = data.predictions?.ensemble ?? data.predictions?.xgboost ?? Object.values(data.predictions ?? {})[0]

  return (
    <div>
      {/* Model predictions */}
      <p style={{ fontSize: '0.72rem', color: 'var(--text-3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 16 }}>
        Model Predictions
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 28 }}>
        {Object.entries(data.predictions ?? {}).map(([modelName, pred]) => (
          <div key={modelName} style={{
            background: 'var(--bg-panel)', border: '1px solid var(--border)',
            borderRadius: 'var(--r-md)', padding: '14px 18px',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'capitalize', color: 'var(--text-2)' }}>{modelName}</span>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
                Confidence: {(pred.confidence * 100).toFixed(1)}%
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: '0.78rem', fontWeight: pred.home_win_prob >= 0.5 ? 700 : 400, color: pred.home_win_prob >= 0.5 ? ACCENT : 'var(--text-3)' }}>
                {homeTeam} {(pred.home_win_prob * 100).toFixed(0)}%
              </span>
              <span style={{ fontSize: '0.78rem', fontWeight: pred.away_win_prob > pred.home_win_prob ? 700 : 400, color: pred.away_win_prob > pred.home_win_prob ? ACCENT : 'var(--text-3)' }}>
                {awayTeam} {(pred.away_win_prob * 100).toFixed(0)}%
              </span>
            </div>
            <div style={{ height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden', display: 'flex' }}>
              <div style={{ width: `${pred.home_win_prob * 100}%`, background: ACCENT, transition: 'width 0.4s' }} />
            </div>
          </div>
        ))}
      </div>

      {/* SHAP Explanations */}
      {ensemble && Object.keys(data.explanation ?? {}).length > 0 && (
        <>
          <p style={{ fontSize: '0.72rem', color: 'var(--text-3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 16 }}>
            Key Factors (SHAP)
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {Object.entries(data.explanation).flatMap(([, factors]) =>
              factors.slice(0, 6).map(f => (
                <div key={f.feature} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-2)', flex: 1 }}>{f.display_name ?? f.feature}</span>
                  <div style={{ width: 120, height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{
                      height: '100%',
                      width: `${Math.min(Math.abs(f.shap_value) * 200, 100)}%`,
                      background: f.shap_value >= 0 ? 'var(--success)' : 'var(--error)',
                      borderRadius: 3,
                    }} />
                  </div>
                  <span style={{ fontSize: '0.7rem', fontFamily: 'var(--font-mono)', color: f.shap_value >= 0 ? 'var(--success)' : 'var(--error)', minWidth: 44, textAlign: 'right' }}>
                    {f.shap_value >= 0 ? '+' : ''}{f.shap_value.toFixed(3)}
                  </span>
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  )
}

// ── Main Modal ────────────────────────────────────────────────────────────────

type Tab = 'boxscore' | 'statistics' | 'prediction'

interface Props {
  gameId: string
  onClose: () => void
}

export default function GameStatsModal({ gameId, onClose }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('boxscore')
  const { data, loading, error } = useGameStats(gameId)

  const homeWon = data?.winner_team_id != null && data.team_stats.home?.team_id === data.winner_team_id

  const TABS: { id: Tab; label: string }[] = [
    { id: 'boxscore', label: 'Box Score' },
    { id: 'statistics', label: 'Statistics' },
    { id: 'prediction', label: 'ML Prediction' },
  ]

  return (
    <AnimatePresence>
      {/* Backdrop */}
      <motion.div
        key="backdrop"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, zIndex: 1000,
          background: BG_OVERLAY,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: '20px',
        }}
      >
        {/* Modal panel */}
        <motion.div
          key="modal"
          initial={{ opacity: 0, scale: 0.96, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 20 }}
          transition={{ duration: 0.2, ease: 'easeOut' }}
          onClick={e => e.stopPropagation()}
          style={{
            width: '100%', maxWidth: 900,
            maxHeight: 'calc(100vh - 40px)',
            background: 'var(--bg-base)',
            border: `1px solid ${ACCENT}40`,
            borderRadius: 'var(--r-lg)',
            display: 'flex', flexDirection: 'column',
            overflow: 'hidden',
          }}
        >
          {/* ── Modal header ── */}
          <div style={{
            padding: '20px 24px 0',
            borderBottom: '1px solid var(--border)',
            background: 'var(--bg-panel)',
            flexShrink: 0,
          }}>
            {loading ? (
              <div style={{ height: 60, display: 'flex', alignItems: 'center' }}>
                <div className="skeleton-row" style={{ width: 200, height: 28, borderRadius: 6 }} />
              </div>
            ) : error ? (
              <p style={{ color: 'var(--error)', padding: '12px 0', fontSize: '0.85rem' }}>{error}</p>
            ) : data ? (
              <>
                {/* Scoreline */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
                    {/* Home team */}
                    <div style={{ textAlign: 'left' }}>
                      <p style={{ fontSize: '0.68rem', color: 'var(--text-3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 2 }}>
                        {data.home_team_name}
                      </p>
                      <span style={{
                        fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '2rem',
                        color: homeWon ? ACCENT : 'var(--text-2)',
                      }}>
                        {data.home_score ?? '—'}
                      </span>
                    </div>

                    <div style={{ textAlign: 'center' }}>
                      <p style={{ fontSize: '0.68rem', color: 'var(--text-3)', marginBottom: 4 }}>
                        {new Date(data.game_date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                      </p>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-3)' }}>FINAL</span>
                    </div>

                    {/* Away team */}
                    <div style={{ textAlign: 'right' }}>
                      <p style={{ fontSize: '0.68rem', color: 'var(--text-3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 2 }}>
                        {data.away_team_name}
                      </p>
                      <span style={{
                        fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '2rem',
                        color: !homeWon ? ACCENT : 'var(--text-2)',
                      }}>
                        {data.away_score ?? '—'}
                      </span>
                    </div>
                  </div>

                  {/* Close button */}
                  <button
                    onClick={onClose}
                    aria-label="Close"
                    style={{
                      width: 32, height: 32,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      background: 'var(--bg-base)', border: '1px solid var(--border)',
                      borderRadius: 'var(--r-sm)', cursor: 'pointer', color: 'var(--text-3)',
                      fontSize: '1.1rem', lineHeight: 1,
                    }}
                  >
                    ×
                  </button>
                </div>

                {/* Tab nav */}
                <div style={{ display: 'flex', gap: 0 }}>
                  {TABS.map(tab => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      style={{
                        padding: '10px 18px',
                        background: 'transparent',
                        border: 'none',
                        borderBottom: `2px solid ${activeTab === tab.id ? ACCENT : 'transparent'}`,
                        cursor: 'pointer',
                        fontSize: '0.82rem', fontWeight: activeTab === tab.id ? 700 : 500,
                        color: activeTab === tab.id ? ACCENT : 'var(--text-3)',
                        transition: 'color 0.15s, border-color 0.15s',
                      }}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </>
            ) : null}

            {/* Close when no data yet */}
            {!loading && !data && !error && (
              <button onClick={onClose} style={{ marginLeft: 'auto', display: 'block' }}>Close</button>
            )}
          </div>

          {/* ── Modal body ── */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
            {loading && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {[...Array(6)].map((_, i) => (
                  <div key={i} className="skeleton-row" style={{ height: 44, borderRadius: 6 }} />
                ))}
              </div>
            )}

            {!loading && data && (
              <>
                {activeTab === 'boxscore' && (
                  <div style={{ overflowX: 'auto' }}>
                    <PlayerTable players={data.player_stats.home} teamName={`${data.home_team} — ${data.home_team_name}`} />
                    <PlayerTable players={data.player_stats.away} teamName={`${data.away_team} — ${data.away_team_name}`} />
                  </div>
                )}

                {activeTab === 'statistics' && (
                  <StatisticsTab
                    home={data.team_stats.home}
                    away={data.team_stats.away}
                    homeName={data.home_team}
                    awayName={data.away_team}
                  />
                )}

                {activeTab === 'prediction' && (
                  <PredictionTab
                    gameId={gameId}
                    homeTeam={data.home_team}
                    awayTeam={data.away_team}
                  />
                )}
              </>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
