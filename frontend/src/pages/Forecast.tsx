import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { useTeamForecast, useLeagueMomentum } from '../hooks/useApi'
import { useSportContext } from '../context/SportContext'
import type { ForecastPoint, LeagueMomentumEntry } from '../types'

const ACCENT = '#2BC9FF'     // matches --accent-arena (blue)
const ACCENT_DIM = 'rgba(43, 201, 255, 0.12)'

const TREND_CONFIG = {
  hot:     { color: '#34D399', icon: '↑', label: 'Hot' },
  cold:    { color: '#FB7185', icon: '↓', label: 'Cold' },
  neutral: { color: '#F7B24A', icon: '→', label: 'Neutral' },
}

const fadeUp = {
  hidden: { opacity: 0, y: 10 },
  show:   { opacity: 1, y: 0, transition: { duration: 0.3 } },
}

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.03 } },
}

function pct(n: number | null | undefined) {
  if (n == null) return '--'
  return `${Math.round(n * 100)}%`
}

// ── Inline SVG Line Chart ────────────────────────────────────────────────────

function ForecastChart({ points }: { points: ForecastPoint[] }) {
  const W = 560
  const H = 160
  const PAD = { top: 14, right: 16, bottom: 28, left: 38 }
  const chartW = W - PAD.left - PAD.right
  const chartH = H - PAD.top - PAD.bottom

  const allValues = points.flatMap(p => [
    p.prophet_forecast, p.ci_lower, p.ci_upper, p.arima_forecast,
  ]).filter((v): v is number => v != null)

  const minY = Math.max(0, Math.min(...allValues) - 0.05)
  const maxY = Math.min(1, Math.max(...allValues) + 0.05)

  const scaleX = (i: number) => PAD.left + (i / Math.max(points.length - 1, 1)) * chartW
  const scaleY = (v: number) => PAD.top + chartH - ((v - minY) / Math.max(maxY - minY, 0.01)) * chartH

  if (points.length === 0) {
    return (
      <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 12 }}>
        No forecast data available — Prophet requires prophet to be installed.
      </div>
    )
  }

  // CI area (shaded region)
  const ciPoints = points
    .filter(p => p.ci_upper != null)
    .map((p, i) => `${scaleX(i)},${scaleY(p.ci_upper!)}`)
    .concat(
      [...points].reverse()
        .filter(p => p.ci_lower != null)
        .map((p, i) => `${scaleX(points.length - 1 - i)},${scaleY(p.ci_lower!)}`)
    )
    .join(' ')

  // Prophet line
  const prophetPath = points
    .filter(p => p.prophet_forecast != null)
    .map((p, idx) => {
      const x = scaleX(points.findIndex((_, i) => points[i] === p))
      return `${idx === 0 ? 'M' : 'L'}${x},${scaleY(p.prophet_forecast!)}`
    })
    .join(' ')

  // ARIMA line
  const arimaPath = points
    .filter(p => p.arima_forecast != null)
    .map((p, idx) => {
      const x = scaleX(points.findIndex((_, i) => points[i] === p))
      return `${idx === 0 ? 'M' : 'L'}${x},${scaleY(p.arima_forecast!)}`
    })
    .join(' ')

  // Y-axis ticks
  const yTicks = [0.25, 0.50, 0.75].map(v => ({
    y: scaleY(minY + (v * (maxY - minY))),
    label: pct(minY + (v * (maxY - minY))),
  }))

  // X-axis date labels (first, middle, last)
  const xLabels = [0, Math.floor(points.length / 2), points.length - 1]
    .filter(i => i < points.length)
    .map(i => ({
      x: scaleX(i),
      label: points[i]?.date?.slice(5) ?? '', // MM-DD
    }))

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: W, height: 'auto', display: 'block' }}>
      {/* Grid lines */}
      {yTicks.map(t => (
        <line key={t.label} x1={PAD.left} y1={t.y} x2={W - PAD.right} y2={t.y}
          stroke="var(--bg-elevated)" strokeWidth="1" />
      ))}

      {/* CI shaded area */}
      {ciPoints.length > 0 && (
        <polygon points={ciPoints} fill={`${ACCENT}18`} />
      )}

      {/* ARIMA dashed line */}
      {arimaPath && (
        <path d={arimaPath} fill="none" stroke="#F7B24A" strokeWidth="1.5"
          strokeDasharray="4 3" opacity={0.7} />
      )}

      {/* Prophet solid line */}
      {prophetPath && (
        <path d={prophetPath} fill="none" stroke={ACCENT} strokeWidth="2" />
      )}

      {/* Y-axis labels */}
      {yTicks.map(t => (
        <text key={t.label} x={PAD.left - 4} y={t.y + 4}
          textAnchor="end" fontSize="9" fill="var(--text-tertiary)">
          {t.label}
        </text>
      ))}

      {/* X-axis date labels */}
      {xLabels.map(l => (
        <text key={l.label} x={l.x} y={H - 8}
          textAnchor="middle" fontSize="9" fill="var(--text-tertiary)">
          {l.label}
        </text>
      ))}

      {/* Legend */}
      <g transform={`translate(${PAD.left + 4}, ${PAD.top + 4})`}>
        <line x1="0" y1="5" x2="14" y2="5" stroke={ACCENT} strokeWidth="2" />
        <text x="17" y="9" fontSize="9" fill="var(--text-secondary)">Prophet</text>
        <line x1="58" y1="5" x2="72" y2="5" stroke="#F7B24A" strokeWidth="1.5" strokeDasharray="4 3" />
        <text x="75" y="9" fontSize="9" fill="var(--text-secondary)">ARIMA</text>
        <rect x="118" y="1" width="12" height="8" fill={`${ACCENT}30`} rx="2" />
        <text x="133" y="9" fontSize="9" fill="var(--text-secondary)">95% CI</text>
      </g>
    </svg>
  )
}

// ── League Momentum Table ─────────────────────────────────────────────────────

function LeagueMomentumTable({ season }: { season: string }) {
  const { data, loading } = useLeagueMomentum(season)

  if (loading) return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {[...Array(6)].map((_, i) => (
        <div key={i} style={{ height: 44, background: 'var(--bg-panel)', borderRadius: 7, animation: 'pulse 1.5s infinite', animationDelay: `${i * 0.05}s` }} />
      ))}
    </div>
  )

  if (!data?.teams?.length) return (
    <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 12 }}>
      No momentum data for {season}.
    </div>
  )

  return (
    <motion.div initial="hidden" animate="show" variants={stagger}>
      <div style={{ display: 'grid', gridTemplateColumns: '32px 1fr 70px 70px 70px 70px', gap: 10, padding: '6px 12px', marginBottom: 4 }}>
        {['#', 'Team', 'Trend', 'Momentum', 'Streak', 'Last 10'].map(h => (
          <span key={h} style={{ fontSize: 9, color: 'var(--text-tertiary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em' }}>{h}</span>
        ))}
      </div>
      {data.teams.map((t: LeagueMomentumEntry) => {
        const trend = TREND_CONFIG[t.trend]
        return (
          <motion.div
            key={t.team}
            variants={fadeUp}
            style={{
              display: 'grid',
              gridTemplateColumns: '32px 1fr 70px 70px 70px 70px',
              gap: 10,
              alignItems: 'center',
              padding: '10px 12px',
              background: 'var(--bg-panel)',
              borderRadius: 7,
              border: '1px solid var(--bg-elevated)',
              marginBottom: 3,
            }}
          >
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontVariantNumeric: 'tabular-nums' }}>{t.rank}</span>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.team}</span>
            <span style={{ fontSize: 11, fontWeight: 700, color: trend.color }}>
              {trend.icon} {trend.label}
            </span>
            {/* Momentum bar */}
            <div style={{ position: 'relative' }}>
              <div style={{ height: 5, background: 'var(--bg-elevated)', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${t.momentum_score * 100}%`, background: trend.color, borderRadius: 3 }} />
              </div>
              <span style={{ fontSize: 9, color: 'var(--text-tertiary)', marginTop: 2, display: 'block' }}>{(t.momentum_score * 100).toFixed(0)}</span>
            </div>
            <span style={{ fontSize: 11, color: t.streak_type === 'win' ? '#34D399' : '#FB7185', fontWeight: 600 }}>
              {t.streak_type === 'none' ? '--' : `${t.streak_length}${t.streak_type === 'win' ? 'W' : 'L'}`}
            </span>
            <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontVariantNumeric: 'tabular-nums' }}>{pct(t.recent_win_pct)}</span>
          </motion.div>
        )
      })}
    </motion.div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

const NBA_TEAMS = [
  'Atlanta Hawks', 'Boston Celtics', 'Brooklyn Nets', 'Charlotte Hornets',
  'Chicago Bulls', 'Cleveland Cavaliers', 'Dallas Mavericks', 'Denver Nuggets',
  'Detroit Pistons', 'Golden State Warriors', 'Houston Rockets', 'Indiana Pacers',
  'LA Clippers', 'Los Angeles Lakers', 'Memphis Grizzlies', 'Miami Heat',
  'Milwaukee Bucks', 'Minnesota Timberwolves', 'New Orleans Pelicans', 'New York Knicks',
  'Oklahoma City Thunder', 'Orlando Magic', 'Philadelphia 76ers', 'Phoenix Suns',
  'Portland Trail Blazers', 'Sacramento Kings', 'San Antonio Spurs', 'Toronto Raptors',
  'Utah Jazz', 'Washington Wizards',
]

export default function Forecast() {
  const { selection } = useSportContext()
  const [selectedTeam, setSelectedTeam] = useState<string>('Boston Celtics')
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTab, setActiveTab] = useState<'team' | 'league'>('team')

  const filteredTeams = useMemo(
    () => NBA_TEAMS.filter(t => t.toLowerCase().includes(searchQuery.toLowerCase())),
    [searchQuery],
  )

  const { data, loading, error } = useTeamForecast(selectedTeam, selection.season)
  const trend = data ? TREND_CONFIG[data.momentum.trend] : null

  return (
    <div style={{ maxWidth: 'var(--content-w, 1140px)', margin: '0 auto', padding: '24px 20px' }}>
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} style={{ marginBottom: 22 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ display: 'inline-flex', width: 32, height: 32, borderRadius: 8, background: ACCENT_DIM, alignItems: 'center', justifyContent: 'center' }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M2 12L6 7L9 9.5L13 4" stroke={ACCENT} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              <circle cx="13" cy="4" r="1.5" fill={ACCENT}/>
            </svg>
          </span>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: 'var(--text-primary)' }}>Forecast</h1>
        </div>
        <p style={{ margin: 0, fontSize: 12, color: 'var(--text-tertiary)' }}>
          14-day win-rate forecast · Prophet + ARIMA ensemble · {selection.season}
        </p>
      </motion.div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, background: 'var(--bg-panel)', borderRadius: 8, padding: 4, width: 'fit-content' }}>
        {(['team', 'league'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '7px 18px', borderRadius: 6, border: 'none', cursor: 'pointer',
              background: activeTab === tab ? ACCENT_DIM : 'transparent',
              color: activeTab === tab ? ACCENT : 'var(--text-secondary)',
              fontWeight: 600, fontSize: 12, textTransform: 'capitalize',
              transition: 'all 0.15s',
            }}
          >
            {tab === 'team' ? 'Team Forecast' : 'League Momentum'}
          </button>
        ))}
      </div>

      {activeTab === 'league' ? (
        <motion.div initial="hidden" animate="show" variants={fadeUp}>
          <div style={{ marginBottom: 12, fontSize: 12, color: 'var(--text-tertiary)' }}>
            All teams ranked by current momentum score (exponentially-weighted last 10 games)
          </div>
          <LeagueMomentumTable season={selection.season} />
        </motion.div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 16, alignItems: 'start' }}>
          {/* Team selector */}
          <div style={{ background: 'var(--bg-panel)', borderRadius: 10, border: '1px solid var(--bg-elevated)', overflow: 'hidden' }}>
            <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--bg-elevated)' }}>
              <input
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Search team…"
                style={{
                  width: '100%', background: 'var(--bg-elevated)', border: 'none',
                  borderRadius: 6, padding: '7px 10px', fontSize: 12, color: 'var(--text-primary)',
                  outline: 'none', boxSizing: 'border-box',
                }}
              />
            </div>
            <div style={{ maxHeight: 420, overflowY: 'auto' }}>
              {filteredTeams.map(team => (
                <button
                  key={team}
                  onClick={() => setSelectedTeam(team)}
                  style={{
                    display: 'block', width: '100%', textAlign: 'left',
                    padding: '9px 12px', border: 'none', cursor: 'pointer',
                    background: selectedTeam === team ? ACCENT_DIM : 'transparent',
                    color: selectedTeam === team ? ACCENT : 'var(--text-secondary)',
                    fontSize: 12, fontWeight: selectedTeam === team ? 600 : 400,
                    transition: 'background 0.12s',
                  }}
                >
                  {team}
                </button>
              ))}
            </div>
          </div>

          {/* Forecast panel */}
          <div>
            {loading && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {[...Array(3)].map((_, i) => (
                  <div key={i} style={{ height: 80, background: 'var(--bg-panel)', borderRadius: 10, animation: 'pulse 1.5s infinite', animationDelay: `${i * 0.1}s` }} />
                ))}
              </div>
            )}

            {error && (
              <div style={{ padding: 20, background: 'rgba(251,113,133,0.08)', borderRadius: 8, border: '1px solid rgba(251,113,133,0.3)', color: '#FB7185', fontSize: 13 }}>
                {error}
              </div>
            )}

            {data && !loading && (
              <motion.div initial="hidden" animate="show" variants={stagger} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {/* Team header */}
                <motion.div variants={fadeUp} style={{ background: 'var(--bg-panel)', borderRadius: 10, border: '1px solid var(--bg-elevated)', padding: '16px 18px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                    <div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>{data.team}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>{data.n_games_used} games analysed · {data.model}</div>
                    </div>
                    {trend && (
                      <span style={{
                        fontSize: 12, fontWeight: 700,
                        color: trend.color, background: `${trend.color}18`,
                        padding: '5px 12px', borderRadius: 6,
                      }}>
                        {trend.icon} {trend.label.toUpperCase()}
                      </span>
                    )}
                  </div>

                  {/* Stats row */}
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    {[
                      { label: 'Season Win %', value: pct(data.current_win_rate) },
                      { label: 'Last 10 Win %', value: pct(data.last_10_win_rate) },
                      { label: 'Momentum', value: (data.momentum.momentum_score * 100).toFixed(0), accent: trend?.color },
                      {
                        label: 'Streak',
                        value: data.momentum.streak_type === 'none' ? '--' : `${data.momentum.streak_length}${data.momentum.streak_type === 'win' ? 'W' : 'L'}`,
                        accent: data.momentum.streak_type === 'win' ? '#34D399' : data.momentum.streak_type === 'loss' ? '#FB7185' : undefined,
                      },
                    ].map(s => (
                      <div key={s.label} style={{ background: 'var(--bg-elevated)', borderRadius: 7, padding: '8px 12px', minWidth: 80 }}>
                        <div style={{ fontSize: 9, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 3 }}>{s.label}</div>
                        <div style={{ fontSize: 15, fontWeight: 700, color: s.accent ?? 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>{s.value}</div>
                      </div>
                    ))}
                  </div>
                </motion.div>

                {/* Chart */}
                <motion.div variants={fadeUp} style={{ background: 'var(--bg-panel)', borderRadius: 10, border: '1px solid var(--bg-elevated)', padding: '16px 18px' }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-tertiary)', letterSpacing: '0.07em', textTransform: 'uppercase', marginBottom: 12 }}>
                    14-Day Win-Rate Forecast
                  </div>
                  {data.forecast.length > 0 ? (
                    <ForecastChart points={data.forecast} />
                  ) : (
                    <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 12, background: 'var(--bg-elevated)', borderRadius: 8 }}>
                      Forecast unavailable — install Prophet: <code style={{ color: ACCENT }}>pip install prophet</code>
                    </div>
                  )}
                </motion.div>

                {/* Changepoints */}
                {data.changepoints.length > 0 && (
                  <motion.div variants={fadeUp} style={{ background: 'var(--bg-panel)', borderRadius: 10, border: '1px solid var(--bg-elevated)', padding: '14px 18px' }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-tertiary)', letterSpacing: '0.07em', textTransform: 'uppercase', marginBottom: 10 }}>
                      Detected Trend Changes
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {data.changepoints.map((cp, i) => (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px', background: 'var(--bg-elevated)', borderRadius: 6 }}>
                          <span style={{ fontSize: 16, color: cp.direction === 'upward' ? '#34D399' : '#FB7185' }}>
                            {cp.direction === 'upward' ? '↑' : '↓'}
                          </span>
                          <div>
                            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{cp.date}</div>
                            <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{cp.direction} · magnitude {cp.magnitude.toFixed(3)}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </motion.div>
                )}
              </motion.div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
