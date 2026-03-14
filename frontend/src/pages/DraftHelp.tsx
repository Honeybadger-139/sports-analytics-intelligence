import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { usePlayerGameStats, usePlayers, useTeamsList } from '../hooks/useApi'
import type { PlayerListItem, PlayerGameLogEntry } from '../types'
import { useSportContext } from '../context/SportContext'

const ACCENT = '#22C55E'
const SEASONS = ['2025-26', '2024-25', '2023-24']

interface PlayerProfile {
  valuation: number
  consistency: number
  sampleSize: number
  points: number
  rebounds: number
  assists: number
  stocks: number
  recentPoints: number
}

function avg(values: number[]): number {
  if (!values.length) return 0
  return values.reduce((sum, val) => sum + val, 0) / values.length
}

function stdDev(values: number[]): number {
  if (values.length < 2) return 0
  const mean = avg(values)
  const variance = avg(values.map(v => (v - mean) ** 2))
  return Math.sqrt(variance)
}

function round1(value: number): number {
  return Math.round(value * 10) / 10
}

function buildProfile(games: PlayerGameLogEntry[]): PlayerProfile | null {
  if (!games.length) return null

  const recent = games.slice(0, 10)
  const points = recent.map(g => Number(g.points ?? 0))
  const rebounds = recent.map(g => Number(g.rebounds ?? 0))
  const assists = recent.map(g => Number(g.assists ?? 0))
  const steals = recent.map(g => Number(g.steals ?? 0))
  const blocks = recent.map(g => Number(g.blocks ?? 0))

  const pts = avg(points)
  const reb = avg(rebounds)
  const ast = avg(assists)
  const stl = avg(steals)
  const blk = avg(blocks)
  const stocks = stl + blk

  const variability = stdDev(points)
  const consistency = Math.max(0, Math.min(100, 100 - variability * 8))
  const valuation = pts * 2 + reb * 1.2 + ast * 1.5 + stl * 3 + blk * 3 + consistency * 0.25

  return {
    valuation: round1(valuation),
    consistency: round1(consistency),
    sampleSize: recent.length,
    points: round1(pts),
    rebounds: round1(reb),
    assists: round1(ast),
    stocks: round1(stocks),
    recentPoints: round1(avg(points.slice(0, 5))),
  }
}

function ProfileCard({ player, profile }: { player: PlayerListItem | null; profile: PlayerProfile | null }) {
  if (!player) {
    return (
      <div style={{ border: '1px dashed var(--border)', borderRadius: 'var(--r-md)', padding: '14px 16px', color: 'var(--text-3)', fontSize: '0.82rem' }}>
        Select a player to see valuation metrics.
      </div>
    )
  }

  if (!profile) {
    return (
      <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--r-md)', padding: '14px 16px', color: 'var(--text-2)', fontSize: '0.82rem' }}>
        Loading stats for {player.full_name}…
      </div>
    )
  }

  return (
    <div style={{ border: '1px solid var(--border)', background: 'var(--bg-panel)', borderRadius: 'var(--r-md)', padding: '14px 16px' }}>
      <p style={{ fontWeight: 800, color: 'var(--text-1)', marginBottom: 2 }}>{player.full_name}</p>
      <p style={{ fontSize: '0.75rem', color: 'var(--text-3)', fontFamily: 'var(--font-mono)', marginBottom: 12 }}>
        {player.team_abbreviation ?? 'FA'} · sample {profile.sampleSize} games
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0,1fr))', gap: 8 }}>
        <Metric label="Valuation" value={profile.valuation} accent />
        <Metric label="Consistency" value={`${profile.consistency}%`} />
        <Metric label="Recent PTS" value={profile.recentPoints} />
        <Metric label="PTS" value={profile.points} />
        <Metric label="REB" value={profile.rebounds} />
        <Metric label="AST" value={profile.assists} />
        <Metric label="STOCKS" value={profile.stocks} />
      </div>
    </div>
  )
}

function Metric({ label, value, accent = false }: { label: string; value: string | number; accent?: boolean }) {
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: '8px 9px', background: 'var(--bg-elevated)' }}>
      <p style={{ fontSize: '0.63rem', color: 'var(--text-3)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</p>
      <p style={{ fontSize: '0.9rem', color: accent ? ACCENT : 'var(--text-1)', fontFamily: 'var(--font-mono)', fontWeight: 800 }}>{value}</p>
    </div>
  )
}

function PlayerSelector({
  title,
  search,
  onSearch,
  team,
  onTeam,
  options,
  results,
  onPick,
  selected,
}: {
  title: string
  search: string
  onSearch: (value: string) => void
  team: string
  onTeam: (value: string) => void
  options: string[]
  results: PlayerListItem[]
  onPick: (player: PlayerListItem) => void
  selected: PlayerListItem | null
}) {
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--r-md)', background: 'var(--bg-panel)', padding: '12px 14px', display: 'grid', gap: 8 }}>
      <p style={{ fontSize: '0.72rem', color: ACCENT, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
        {title}
      </p>
      <input
        className="scribble-input"
        placeholder="Type player name…"
        value={search}
        onChange={(e) => onSearch(e.target.value)}
        style={{ fontSize: '0.8rem' }}
      />
      <select className="scribble-select" value={team} onChange={(e) => onTeam(e.target.value)}>
        <option value="">All teams</option>
        {options.map(option => (
          <option key={option} value={option}>{option}</option>
        ))}
      </select>

      {selected && (
        <div style={{ fontSize: '0.74rem', color: 'var(--text-2)', fontFamily: 'var(--font-mono)' }}>
          Selected: <strong style={{ color: 'var(--text-1)' }}>{selected.full_name}</strong>
        </div>
      )}

      <div style={{ maxHeight: 170, overflow: 'auto', display: 'grid', gap: 6 }}>
        {results.slice(0, 8).map(player => (
          <button
            key={player.player_id}
            onClick={() => onPick(player)}
            style={{
              border: '1px solid var(--border)',
              borderRadius: 8,
              background: selected?.player_id === player.player_id ? `${ACCENT}20` : 'var(--bg-elevated)',
              color: selected?.player_id === player.player_id ? ACCENT : 'var(--text-1)',
              cursor: 'pointer',
              textAlign: 'left',
              padding: '7px 9px',
              fontSize: '0.77rem',
              fontFamily: 'var(--font-mono)',
            }}
          >
            {player.full_name}
            <span style={{ color: 'var(--text-3)' }}> · {player.team_abbreviation ?? 'FA'}</span>
          </button>
        ))}
        {!results.length && (
          <p style={{ fontSize: '0.74rem', color: 'var(--text-3)' }}>
            Type at least 2 letters or select a team.
          </p>
        )}
      </div>
    </div>
  )
}

export default function DraftHelp() {
  const { selection } = useSportContext()
  const [season, setSeason] = useState(SEASONS.includes(selection.season) ? selection.season : '2025-26')

  const [searchA, setSearchA] = useState('')
  const [searchB, setSearchB] = useState('')
  const [teamA, setTeamA] = useState('')
  const [teamB, setTeamB] = useState('')
  const [selectedA, setSelectedA] = useState<PlayerListItem | null>(null)
  const [selectedB, setSelectedB] = useState<PlayerListItem | null>(null)

  const { data: teamsData } = useTeamsList()
  const teamOptions = useMemo(
    () => [...new Set((teamsData?.teams ?? []).map(t => t.abbreviation))].sort(),
    [teamsData?.teams],
  )

  const { data: playersAData } = usePlayers(searchA, teamA || undefined)
  const { data: playersBData } = usePlayers(searchB, teamB || undefined)

  const { data: statsAData } = usePlayerGameStats(selectedA?.player_id ?? null, [season], { limit: 80 })
  const { data: statsBData } = usePlayerGameStats(selectedB?.player_id ?? null, [season], { limit: 80 })

  const profileA = useMemo(() => buildProfile(statsAData?.games ?? []), [statsAData?.games])
  const profileB = useMemo(() => buildProfile(statsBData?.games ?? []), [statsBData?.games])

  const comparison = useMemo(() => {
    if (!profileA || !profileB || !selectedA || !selectedB) return null
    const diff = profileA.valuation - profileB.valuation
    if (Math.abs(diff) < 3) {
      return `Close call: ${selectedA.full_name} and ${selectedB.full_name} are similarly valued on current form and stability.`
    }
    const winner = diff > 0 ? selectedA.full_name : selectedB.full_name
    const loser = diff > 0 ? selectedB.full_name : selectedA.full_name
    const gap = Math.abs(diff).toFixed(1)
    return `${winner} has the stronger current valuation index (+${gap}) versus ${loser}.`
  }, [profileA, profileB, selectedA, selectedB])

  return (
    <div className="page-shell">
      <div style={{ maxWidth: 'var(--content-w)', margin: '0 auto', padding: '28px' }}>
        <div style={{ marginBottom: 20 }}>
          <p style={{ fontSize: '0.72rem', color: ACCENT, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 4 }}>
            Draft Help
          </p>
          <h1 style={{ margin: 0, fontSize: '1.35rem', color: 'var(--text-1)', fontFamily: 'var(--font-display)' }}>
            Interactive Player Valuation Lab
          </h1>
          <p style={{ marginTop: 8, fontSize: '0.84rem', color: 'var(--text-2)', maxWidth: 760 }}>
            Compare two players side-by-side using recent production, consistency, and a composite valuation index.
          </p>
        </div>

        <div style={{ marginBottom: 14, maxWidth: 220 }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-2)', fontWeight: 700 }}>Season</span>
            <select className="scribble-select" value={season} onChange={(e) => setSeason(e.target.value)}>
              {SEASONS.map(item => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', gap: 12, marginBottom: 14 }}>
          <PlayerSelector
            title="Player A"
            search={searchA}
            onSearch={setSearchA}
            team={teamA}
            onTeam={setTeamA}
            options={teamOptions}
            results={playersAData?.players ?? []}
            onPick={setSelectedA}
            selected={selectedA}
          />
          <PlayerSelector
            title="Player B"
            search={searchB}
            onSearch={setSearchB}
            team={teamB}
            onTeam={setTeamB}
            options={teamOptions}
            results={playersBData?.players ?? []}
            onPick={setSelectedB}
            selected={selectedB}
          />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', gap: 12 }}>
          <ProfileCard player={selectedA} profile={profileA} />
          <ProfileCard player={selectedB} profile={profileB} />
        </div>

        {comparison && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              marginTop: 14,
              border: '1px solid color-mix(in srgb, var(--success) 35%, var(--border))',
              borderRadius: 'var(--r-md)',
              background: 'color-mix(in srgb, var(--success) 8%, transparent)',
              padding: '12px 14px',
            }}
          >
            <p style={{ fontSize: '0.8rem', color: 'var(--text-1)' }}>
              <strong style={{ color: ACCENT }}>Recommendation:</strong> {comparison}
            </p>
          </motion.div>
        )}
      </div>
    </div>
  )
}

