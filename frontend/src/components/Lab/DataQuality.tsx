import { useState } from 'react'
import { motion } from 'framer-motion'
import { useQualityOverview } from '../../hooks/useApi'
import type { TopTeam } from '../../types'

const ACCENT   = '#8B5CF6'
const SEASONS  = ['2025-26', '2024-25', '2023-24']

function fmt(n: number | null | undefined, decimals = 1): string {
  if (n == null) return '—'
  return n.toFixed(decimals)
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div style={{
      background: 'var(--bg-panel)', border: '1px solid var(--border)',
      borderRadius: 'var(--r-md)', padding: '18px 20px',
    }}>
      <p style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-2)', marginBottom: 8 }}>
        {label}
      </p>
      <p style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--text-1)', fontFamily: 'var(--font-mono)', lineHeight: 1 }}>
        {value}
      </p>
      {sub && <p style={{ fontSize: '0.75rem', color: 'var(--text-2)', marginTop: 6 }}>{sub}</p>}
    </div>
  )
}

function TimingBar({ label, avg, latest }: { label: string; avg: number | null; latest: number | null }) {
  return (
    <div style={{
      background: 'var(--bg-panel)', border: '1px solid var(--border)',
      borderRadius: 'var(--r-md)', padding: '16px 20px',
      display: 'flex', flexDirection: 'column', gap: 10,
    }}>
      <p style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-1)', margin: 0 }}>{label}</p>
      <div style={{ display: 'flex', gap: 24 }}>
        <div>
          <p style={{ fontSize: '0.68rem', color: 'var(--text-2)', marginBottom: 2 }}>Avg</p>
          <p style={{ fontSize: '1.1rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: ACCENT }}>
            {avg != null ? `${fmt(avg)}s` : '—'}
          </p>
        </div>
        <div>
          <p style={{ fontSize: '0.68rem', color: 'var(--text-2)', marginBottom: 2 }}>Latest</p>
          <p style={{ fontSize: '1.1rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-1)' }}>
            {latest != null ? `${fmt(latest)}s` : '—'}
          </p>
        </div>
      </div>
    </div>
  )
}

function WinPctBar({ pct }: { pct: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
      <div style={{ flex: 1, height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct * 100}%`, height: '100%', background: ACCENT, borderRadius: 2 }} />
      </div>
      <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-1)', minWidth: 36 }}>
        {(pct * 100).toFixed(1)}%
      </span>
    </div>
  )
}

export default function DataQuality() {
  const [season, setSeason] = useState('2025-26')
  const { data, loading, error, refresh } = useQualityOverview(season)

  const rc = data?.row_counts
  const pt = data?.pipeline_timing
  const qc = data?.quality_checks ?? {}
  const qcEntries = Object.entries(qc)

  return (
    <div style={{ padding: '28px 28px', maxWidth: 'var(--content-w)', margin: '0 auto' }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <select
            className="scribble-select"
            value={season}
            onChange={e => setSeason(e.target.value)}
          >
            {SEASONS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          {loading && (
            <span style={{ fontSize: '0.78rem', color: 'var(--text-2)' }}>Loading…</span>
          )}
          {error && (
            <span style={{ fontSize: '0.78rem', color: 'var(--error)' }}>{error}</span>
          )}
        </div>
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
          Refresh
        </button>
      </div>

      {/* ── Row counts ── */}
      <p className="section-label" style={{ marginBottom: 12, color: ACCENT }}>Row Counts</p>
      <motion.div
        initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}
        style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 10, marginBottom: 28 }}
      >
        <StatCard label="Matches"        value={rc ? rc.matches.toLocaleString()         : '—'} sub={`Season ${season}`} />
        <StatCard label="Teams"          value={rc ? rc.teams.toLocaleString()            : '—'} sub="All franchises" />
        <StatCard label="Active Players" value={rc ? rc.players.toLocaleString()          : '—'} sub="is_active = true" />
        <StatCard label="Team Stat Rows" value={rc ? rc.team_game_stats.toLocaleString()  : '—'} sub="2 rows per game" />
        <StatCard label="Player Game Rows" value={rc ? rc.player_game_stats.toLocaleString() : '—'} sub="Per player per game" />
      </motion.div>

      {/* ── Pipeline timing ── */}
      <p className="section-label" style={{ marginBottom: 12, color: ACCENT }}>Pipeline Timing</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10, marginBottom: 28 }}>
        <TimingBar label="Ingestion" avg={pt?.avg_ingestion_seconds ?? null} latest={pt?.latest_ingestion_seconds ?? null} />
        <TimingBar label="Feature Engineering" avg={pt?.avg_feature_seconds ?? null} latest={pt?.latest_feature_seconds ?? null} />
      </div>

      {/* ── Quality checks ── */}
      <p className="section-label" style={{ marginBottom: 12, color: ACCENT }}>Quality Checks</p>
      <div style={{
        background: 'var(--bg-panel)', border: '1px solid var(--border)',
        borderRadius: 'var(--r-md)', marginBottom: 28, overflow: 'hidden',
      }}>
        {qcEntries.length === 0 ? (
          <p style={{ padding: '20px 24px', color: 'var(--text-2)', fontSize: '0.85rem' }}>
            {loading ? 'Loading quality checks…' : 'No quality violations recorded.'}
          </p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Check', 'Value'].map(h => (
                  <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-2)' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {qcEntries.map(([key, val], i) => (
                <tr key={key} style={{ borderBottom: i < qcEntries.length - 1 ? '1px solid var(--border)' : 'none' }}>
                  <td style={{ padding: '10px 16px', fontSize: '0.82rem', color: 'var(--text-2)', fontFamily: 'var(--font-mono)' }}>{key}</td>
                  <td style={{ padding: '10px 16px', fontSize: '0.82rem', color: val ? 'var(--error)' : 'var(--success)', fontFamily: 'var(--font-mono)' }}>
                    {String(val)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Top teams ── */}
      <p className="section-label" style={{ marginBottom: 12, color: ACCENT }}>Top 10 Teams by Win %</p>
      <div style={{
        background: 'var(--bg-panel)', border: '1px solid var(--border)',
        borderRadius: 'var(--r-md)', marginBottom: 8, overflow: 'hidden',
      }}>
        {!data?.top_teams?.length ? (
          <p style={{ padding: '20px 24px', color: 'var(--text-2)', fontSize: '0.85rem' }}>
            {loading ? 'Loading…' : 'No team data available for this season.'}
          </p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['#', 'Team', 'GP', 'W', 'L', 'Win %'].map(h => (
                  <th key={h} style={{ padding: '10px 16px', textAlign: h === 'Win %' ? 'left' : (h === '#' || h === 'GP' || h === 'W' || h === 'L') ? 'center' : 'left', fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-2)' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(data.top_teams as TopTeam[]).map((t, i) => (
                <tr key={t.abbreviation} style={{ borderBottom: i < data.top_teams.length - 1 ? '1px solid var(--border)' : 'none' }}>
                  <td style={{ padding: '10px 16px', textAlign: 'center', fontSize: '0.8rem', color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>{i + 1}</td>
                  <td style={{ padding: '10px 16px' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.88rem', color: 'var(--text-1)', fontFamily: 'var(--font-mono)', letterSpacing: '0.04em' }}>{t.abbreviation}</span>
                  </td>
                  <td style={{ padding: '10px 16px', textAlign: 'center', fontSize: '0.82rem', color: 'var(--text-2)', fontFamily: 'var(--font-mono)' }}>{t.games_played}</td>
                  <td style={{ padding: '10px 16px', textAlign: 'center', fontSize: '0.82rem', color: 'var(--success)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{t.wins}</td>
                  <td style={{ padding: '10px 16px', textAlign: 'center', fontSize: '0.82rem', color: 'var(--error)', fontFamily: 'var(--font-mono)' }}>{t.losses}</td>
                  <td style={{ padding: '10px 16px', minWidth: 180 }}>
                    <WinPctBar pct={t.win_pct} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
