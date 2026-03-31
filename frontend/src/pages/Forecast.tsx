import { useState, useMemo, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useTeamForecast, useLeagueMomentum } from '../hooks/useApi'
import { useSportContext } from '../context/SportContext'
import type { ForecastPoint, LeagueMomentumEntry } from '../types'

// Use CSS variables so colors adapt correctly in both dark and light themes.
// In dark mode: cyan, bright green, bright red, amber.
// In light mode: --accent-arena → #0369A1, --accent-green → #047857, etc.
const ACCENT = 'var(--accent-arena)'
const ACCENT_DIM = 'var(--accent-arena-dim)'

const TREND: Record<string, { color: string; bg: string; icon: string; label: string }> = {
  hot:     { color: 'var(--accent-green)', bg: 'var(--accent-scrib-dim)', icon: '↑', label: 'Hot' },
  cold:    { color: 'var(--accent-red)',   bg: 'var(--accent-red-dim)',   icon: '↓', label: 'Cold' },
  neutral: { color: 'var(--accent-chat)',  bg: 'var(--accent-chat-dim)',  icon: '→', label: 'Neutral' },
}

const NBA_TEAMS = [
  'Atlanta Hawks','Boston Celtics','Brooklyn Nets','Charlotte Hornets',
  'Chicago Bulls','Cleveland Cavaliers','Dallas Mavericks','Denver Nuggets',
  'Detroit Pistons','Golden State Warriors','Houston Rockets','Indiana Pacers',
  'LA Clippers','Los Angeles Lakers','Memphis Grizzlies','Miami Heat',
  'Milwaukee Bucks','Minnesota Timberwolves','New Orleans Pelicans','New York Knicks',
  'Oklahoma City Thunder','Orlando Magic','Philadelphia 76ers','Phoenix Suns',
  'Portland Trail Blazers','Sacramento Kings','San Antonio Spurs','Toronto Raptors',
  'Utah Jazz','Washington Wizards',
]

const MODEL_DISPLAY: Record<string, string> = {
  'prophet+arima_ensemble': 'Prophet + ARIMA Ensemble',
  'prophet':                'Prophet',
  'arima':                  'ARIMA',
}
function fmtModel(m: string): string {
  return MODEL_DISPLAY[m] ?? m.replace(/[_+]+/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function pct(n: number | null | undefined) {
  if (n == null) return '--'
  return `${Math.round(n * 100)}%`
}

// ── Inline SVG forecast chart ─────────────────────────────────────────────────

function ForecastChart({ points }: { points: ForecastPoint[] }) {
  if (!points.length) return (
    <div style={{ padding: '28px 0', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 12 }}>
      Forecast unavailable — Prophet requires <code style={{ color: ACCENT }}>pip install prophet</code> in the Cloud Run environment.
      ARIMA baseline will appear once <code style={{ color: ACCENT }}>statsmodels</code> finishes deploying.
    </div>
  )

  const W = 520, H = 140
  const PAD = { top: 12, right: 12, bottom: 24, left: 36 }
  const cW = W - PAD.left - PAD.right
  const cH = H - PAD.top - PAD.bottom

  const allVals = points.flatMap(p =>
    [p.prophet_forecast, p.ci_lower, p.ci_upper, p.arima_forecast].filter((v): v is number => v != null)
  )
  const minY = Math.max(0, (Math.min(...allVals) - 0.06))
  const maxY = Math.min(1, (Math.max(...allVals) + 0.06))
  const range = Math.max(maxY - minY, 0.01)

  const sx = (i: number) => PAD.left + (i / Math.max(points.length - 1, 1)) * cW
  const sy = (v: number) => PAD.top + cH - ((v - minY) / range) * cH

  const ciPoly = [
    ...points.filter(p => p.ci_upper != null).map((p, i) => `${sx(i)},${sy(p.ci_upper!)}`),
    ...[...points].reverse().filter(p => p.ci_lower != null).map((p, i) => `${sx(points.length - 1 - i)},${sy(p.ci_lower!)}`),
  ].join(' ')

  const propLine = points
    .filter(p => p.prophet_forecast != null)
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${sx(points.findIndex(x => x === p))},${sy(p.prophet_forecast!)}`)
    .join(' ')

  const arimaLine = points
    .filter(p => p.arima_forecast != null)
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${sx(points.findIndex(x => x === p))},${sy(p.arima_forecast!)}`)
    .join(' ')

  const yLabels = [0.25, 0.5, 0.75].map(t => ({
    y: sy(minY + t * range), label: pct(minY + t * range),
  }))
  const xLabels = [0, Math.floor(points.length / 2), points.length - 1]
    .filter(i => i < points.length)
    .map(i => ({ x: sx(i), label: (points[i]?.date ?? '').slice(5) }))

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: W, display: 'block' }}>
      {yLabels.map(t => (
        <g key={t.label}>
          <line x1={PAD.left} y1={t.y} x2={W - PAD.right} y2={t.y} stroke="var(--bg-elevated)" strokeWidth="1" />
          <text x={PAD.left - 4} y={t.y + 4} textAnchor="end" fontSize="9" fill="var(--text-tertiary)">{t.label}</text>
        </g>
      ))}
      {ciPoly && <polygon points={ciPoly} fill={`${ACCENT}20`} />}
      {arimaLine && <path d={arimaLine} fill="none" stroke="var(--accent-chat)" strokeWidth="1.5" strokeDasharray="4 3" opacity={0.65} />}
      {propLine && <path d={propLine} fill="none" stroke={ACCENT} strokeWidth="2" />}
      {xLabels.map(l => (
        <text key={l.label} x={l.x} y={H - 6} textAnchor="middle" fontSize="9" fill="var(--text-tertiary)">{l.label}</text>
      ))}
      <g transform={`translate(${PAD.left + 4},${PAD.top + 2})`}>
        <line x1="0" y1="5" x2="12" y2="5" stroke={ACCENT} strokeWidth="2" />
        <text x="15" y="9" fontSize="8" fill="var(--text-secondary)">Prophet</text>
        <line x1="55" y1="5" x2="67" y2="5" stroke="var(--accent-chat)" strokeWidth="1.5" strokeDasharray="3 2" />
        <text x="70" y="9" fontSize="8" fill="var(--text-secondary)">ARIMA</text>
        <rect x="108" y="1" width="10" height="7" fill={`${ACCENT}28`} rx="1" />
        <text x="121" y="9" fontSize="8" fill="var(--text-secondary)">95% CI</text>
      </g>
    </svg>
  )
}

// ── Team dropdown ─────────────────────────────────────────────────────────────

function TeamDropdown({ value, onChange }: { value: string; onChange: (t: string) => void }) {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onOut(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onOut)
    return () => document.removeEventListener('mousedown', onOut)
  }, [])

  const filtered = useMemo(
    () => NBA_TEAMS.filter(t => t.toLowerCase().includes(q.toLowerCase())),
    [q],
  )

  return (
    <div ref={ref} style={{ position: 'relative', width: 220 }}>
      <button
        onClick={() => { setOpen(o => !o); setQ('') }}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '8px 12px', background: 'var(--bg-panel)', border: `1px solid ${open ? ACCENT : 'var(--bg-elevated)'}`,
          borderRadius: 8, color: 'var(--text-primary)', fontSize: 13, fontWeight: 600, cursor: 'pointer',
          transition: 'border-color 0.15s',
        }}
      >
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{value}</span>
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" style={{ flexShrink: 0, marginLeft: 6, transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>
          <path d="M2 3.5L5 6.5L8 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
        </svg>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.12 }}
            style={{
              position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0, zIndex: 50,
              background: 'var(--bg-elevated)', border: '1px solid var(--bg-hover)',
              borderRadius: 8, overflow: 'hidden', boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
            }}
          >
            <div style={{ padding: '6px 8px', borderBottom: '1px solid var(--bg-hover)' }}>
              <input
                autoFocus value={q} onChange={e => setQ(e.target.value)}
                placeholder="Search team…"
                style={{
                  width: '100%', background: 'var(--bg-panel)', border: 'none', borderRadius: 5,
                  padding: '6px 8px', fontSize: 12, color: 'var(--text-primary)', outline: 'none', boxSizing: 'border-box',
                }}
              />
            </div>
            <div style={{ maxHeight: 240, overflowY: 'auto' }}>
              {filtered.map(t => (
                <button key={t} onClick={() => { onChange(t); setOpen(false); setQ('') }}
                  style={{
                    display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px',
                    border: 'none', background: t === value ? ACCENT_DIM : 'transparent',
                    color: t === value ? ACCENT : 'var(--text-secondary)',
                    fontSize: 12, fontWeight: t === value ? 600 : 400, cursor: 'pointer',
                    transition: 'background 0.1s',
                  }}
                >
                  {t}
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── League momentum row ───────────────────────────────────────────────────────

function MomentumRow({ entry, onSelect }: { entry: LeagueMomentumEntry; onSelect: (t: string) => void }) {
  const t = TREND[entry.trend]
  return (
    <motion.div
      layout
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      onClick={() => onSelect(entry.team)}
      style={{
        display: 'grid',
        gridTemplateColumns: '28px 1fr 80px 120px 60px 52px',
        gap: 10, alignItems: 'center',
        padding: '10px 14px',
        background: 'var(--bg-panel)',
        borderRadius: 7,
        border: '1px solid var(--bg-elevated)',
        cursor: 'pointer',
        transition: 'background 0.12s',
      }}
    >
      <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontVariantNumeric: 'tabular-nums' }}>{entry.rank}</span>
      <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{entry.team}</span>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, fontWeight: 700, color: t.color, background: t.bg, padding: '2px 7px', borderRadius: 5 }}>
        {t.icon} {t.label}
      </span>
      {/* momentum bar */}
      <div>
        <div style={{ height: 5, background: 'var(--bg-elevated)', borderRadius: 3, overflow: 'hidden', marginBottom: 3 }}>
          <div style={{ height: '100%', width: `${entry.momentum_score * 100}%`, background: t.color, borderRadius: 3, transition: 'width 0.5s ease' }} />
        </div>
        <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>{(entry.momentum_score * 100).toFixed(0)}/100</span>
      </div>
      <span style={{ fontSize: 11, color: entry.streak_type === 'win' ? 'var(--accent-green)' : entry.streak_type === 'loss' ? 'var(--accent-red)' : 'var(--text-tertiary)', fontWeight: 600 }}>
        {entry.streak_type === 'none' ? '--' : `${entry.streak_length}${entry.streak_type === 'win' ? 'W' : 'L'}`}
      </span>
      <span style={{ fontSize: 11, color: 'var(--text-secondary)', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{pct(entry.recent_win_pct)}</span>
    </motion.div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Forecast() {
  const { selection } = useSportContext()
  const [tab, setTab] = useState<'league' | 'team'>('league')
  const [team, setTeam] = useState('Boston Celtics')

  const { data: league, loading: leagueLoading, error: leagueErr } = useLeagueMomentum(selection.season)
  const { data: forecast, loading: forecastLoading, error: forecastErr } = useTeamForecast(
    tab === 'team' ? team : null, selection.season
  )

  function selectTeam(t: string) {
    setTeam(t)
    setTab('team')
  }

  const trend = forecast ? TREND[forecast.momentum.trend] : null

  return (
    <div className="page-shell">
    <div style={{ maxWidth: 'var(--content-w, 1140px)', margin: '0 auto', padding: '24px 20px' }}>

      {/* ── Header ── */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
          <span style={{ display: 'inline-flex', width: 30, height: 30, borderRadius: 7, background: ACCENT_DIM, alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M2 11L5.5 6.5L8 8.5L12 3" stroke={ACCENT} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              <circle cx="12" cy="3" r="1.4" fill={ACCENT}/>
            </svg>
          </span>
          <h1 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>Forecast</h1>
        </div>
        <p style={{ margin: 0, fontSize: 11, color: 'var(--text-tertiary)', paddingLeft: 38 }}>
          14-day win-rate · Prophet + ARIMA ensemble · {selection.season}
        </p>
      </motion.div>

      {/* ── Tab bar + team selector ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', background: 'var(--bg-panel)', borderRadius: 8, padding: 3, gap: 2 }}>
          {(['league', 'team'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding: '6px 16px', borderRadius: 6, border: 'none', cursor: 'pointer',
              background: tab === t ? ACCENT_DIM : 'transparent',
              color: tab === t ? ACCENT : 'var(--text-secondary)',
              fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em',
              transition: 'all 0.15s',
            }}>
              {t === 'league' ? 'League Momentum' : 'Team Forecast'}
            </button>
          ))}
        </div>

        {tab === 'team' && (
          <TeamDropdown value={team} onChange={selectTeam} />
        )}
      </div>

      {/* ── League tab ── */}
      {tab === 'league' && (
        <motion.div key="league" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          {/* Column headers */}
          <div style={{ display: 'grid', gridTemplateColumns: '28px 1fr 80px 120px 60px 52px', gap: 10, padding: '4px 14px', marginBottom: 6 }}>
            {['#', 'Team', 'Trend', 'Momentum', 'Streak', 'L10'].map(h => (
              <span key={h} style={{ fontSize: 9, fontWeight: 600, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>{h}</span>
            ))}
          </div>

          {leagueLoading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {[...Array(10)].map((_, i) => (
                <div key={i} style={{ height: 44, background: 'var(--bg-panel)', borderRadius: 7, opacity: 1 - i * 0.07, animation: 'pulse 1.5s infinite', animationDelay: `${i * 0.04}s` }} />
              ))}
            </div>
          )}

          {leagueErr && (
            <div style={{ padding: '20px 16px', background: 'var(--bg-panel)', borderRadius: 10, border: '1px solid var(--bg-elevated)', textAlign: 'center' }}>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 }}>Momentum data unavailable</div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{leagueErr}</div>
            </div>
          )}

          {league && !leagueLoading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {league.teams.map(entry => (
                <MomentumRow key={entry.team} entry={entry} onSelect={selectTeam} />
              ))}
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', textAlign: 'center', padding: '10px 0 4px' }}>
                Click any team to view 14-day forecast →
              </div>
            </div>
          )}
        </motion.div>
      )}

      {/* ── Team forecast tab ── */}
      {tab === 'team' && (
        <motion.div key="team" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          {forecastLoading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[160, 220, 100].map((h, i) => (
                <div key={i} style={{ height: h, background: 'var(--bg-panel)', borderRadius: 10, animation: 'pulse 1.5s infinite', animationDelay: `${i * 0.1}s` }} />
              ))}
            </div>
          )}

          {forecastErr && !forecastLoading && (
            <div style={{ padding: '28px 24px', background: 'var(--bg-panel)', borderRadius: 10, border: '1px solid var(--bg-elevated)', textAlign: 'center' }}>
              <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--bg-elevated)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px' }}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 5V8M8 11H8.01" stroke="var(--text-tertiary)" strokeWidth="1.5" strokeLinecap="round"/><circle cx="8" cy="8" r="6.5" stroke="var(--text-tertiary)" strokeWidth="1.3"/></svg>
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                Forecast unavailable for {team}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', maxWidth: 340, margin: '0 auto' }}>
                {forecastErr}
              </div>
            </div>
          )}

          {forecast && !forecastLoading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {/* Team summary card */}
              <div style={{ background: 'var(--bg-panel)', borderRadius: 10, border: '1px solid var(--bg-elevated)', padding: '16px 18px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14, flexWrap: 'wrap', gap: 8 }}>
                  <div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>{forecast.team}</div>
                    <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 2 }}>
                      {forecast.n_games_used} games · {fmtModel(forecast.model)}
                    </div>
                  </div>
                  {trend && (
                    <span style={{ fontSize: 11, fontWeight: 700, color: trend.color, background: trend.bg, padding: '5px 12px', borderRadius: 6 }}>
                      {trend.icon} {trend.label.toUpperCase()} STREAK
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {[
                    { label: 'Season Win %', value: pct(forecast.current_win_rate) },
                    { label: 'Last 10', value: pct(forecast.last_10_win_rate) },
                    { label: 'Momentum', value: (forecast.momentum.momentum_score * 100).toFixed(0), color: trend?.color },
                    {
                      label: 'Streak',
                      value: forecast.momentum.streak_type === 'none' ? '--' : `${forecast.momentum.streak_length}${forecast.momentum.streak_type === 'win' ? 'W' : 'L'}`,
                      color: forecast.momentum.streak_type === 'win' ? '#34D399' : forecast.momentum.streak_type === 'loss' ? '#FB7185' : undefined,
                    },
                  ].map(s => (
                    <div key={s.label} style={{ background: 'var(--bg-elevated)', borderRadius: 7, padding: '8px 14px', flex: '1 1 80px' }}>
                      <div style={{ fontSize: 9, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 4 }}>{s.label}</div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: s.color ?? 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>{s.value}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Chart card */}
              <div style={{ background: 'var(--bg-panel)', borderRadius: 10, border: '1px solid var(--bg-elevated)', padding: '14px 18px' }}>
                <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 12 }}>
                  14-Day Win-Rate Forecast
                </div>
                <ForecastChart points={forecast.forecast} />
              </div>

              {/* Changepoints */}
              {forecast.changepoints.length > 0 && (
                <div style={{ background: 'var(--bg-panel)', borderRadius: 10, border: '1px solid var(--bg-elevated)', padding: '14px 18px' }}>
                  <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 10 }}>
                    Detected Trend Shifts
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {forecast.changepoints.map((cp, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px', background: 'var(--bg-elevated)', borderRadius: 6 }}>
                        <span style={{ fontSize: 18, color: cp.direction === 'upward' ? '#34D399' : '#FB7185', lineHeight: 1 }}>{cp.direction === 'upward' ? '↑' : '↓'}</span>
                        <div>
                          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{cp.date}</div>
                          <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{cp.direction} · magnitude {cp.magnitude.toFixed(3)}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </motion.div>
      )}
    </div>
    </div>
  )
}
