import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { useTeamsList, useTeamGameStats } from '../../hooks/useApi'
import type { TeamGameLogEntry } from '../../types'

const ACCENT = '#06C5F8'
const SEASONS = ['2025-26', '2024-25', '2023-24']

function fmtDate(iso: string): string {
    try { return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) }
    catch { return iso }
}

function pct(v: number | null): string {
    if (v == null) return '—'
    return (v * 100).toFixed(1)
}

function num(v: number | null, decimals = 1): string {
    if (v == null) return '—'
    return v.toFixed(decimals)
}

function TeamRow({ team, isSelected, onClick }: {
    team: { team_id: number; abbreviation: string; full_name: string; city: string };
    isSelected: boolean; onClick: () => void;
}) {
    return (
        <button
            onClick={onClick}
            style={{
                width: '100%', textAlign: 'left', background: isSelected ? `${ACCENT}0D` : 'transparent',
                border: 'none', borderLeft: isSelected ? `2px solid ${ACCENT}` : '2px solid transparent',
                padding: '10px 14px', cursor: 'pointer', transition: 'background 0.12s',
            }}
            onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = 'var(--bg-elevated)' }}
            onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'transparent' }}
        >
            <span style={{
                fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '0.82rem',
                color: isSelected ? ACCENT : 'var(--text-1)',
            }}>
                {team.abbreviation}
            </span>
            <p style={{ fontSize: '0.7rem', color: 'var(--text-3)', margin: '2px 0 0', fontFamily: 'var(--font-mono)' }}>
                {team.city} {team.full_name}
            </p>
        </button>
    )
}

function RecordCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
    return (
        <div style={{
            background: 'var(--bg-panel)', border: '1px solid var(--border)',
            borderRadius: 'var(--r-md)', padding: '14px 18px', textAlign: 'center',
        }}>
            <p style={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-2)', marginBottom: 4 }}>
                {label}
            </p>
            <p style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '1.1rem', color: ACCENT, margin: 0 }}>
                {value}
            </p>
            {sub && <p style={{ fontSize: '0.68rem', color: 'var(--text-3)', margin: '4px 0 0' }}>{sub}</p>}
        </div>
    )
}

export default function TeamStatsView() {
    const [season, setSeason] = useState('2025-26')
    const [selectedAbbr, setSelectedAbbr] = useState<string | null>(null)
    const [opponent, setOpponent] = useState('')
    const [dateFrom, setDateFrom] = useState('')
    const [dateTo, setDateTo] = useState('')

    const { data: teamsData, loading: teamsLoading } = useTeamsList()
    const { data: statsData, loading: statsLoading, error: statsError } = useTeamGameStats(selectedAbbr, season, 200)

    const teams = teamsData?.teams ?? []
    const opponentOptions = useMemo(
        () => [...new Set(teams.map(t => t.abbreviation))].sort(),
        [teams],
    )
    const rawDateFrom = dateFrom || undefined
    const rawDateTo = dateTo || undefined
    const hasInvertedRange = !!(rawDateFrom && rawDateTo && rawDateFrom > rawDateTo)
    const normalizedDateFrom = hasInvertedRange ? rawDateTo : rawDateFrom
    const normalizedDateTo = hasInvertedRange ? rawDateFrom : rawDateTo
    const hasActiveFilters = !!(opponent || normalizedDateFrom || normalizedDateTo)
    const allGames = useMemo(
        () => ((statsData?.games ?? []) as TeamGameLogEntry[]),
        [statsData?.games],
    )
    const filteredGames = useMemo(() => {
        return allGames.filter(g => {
            const gameDate = String(g.game_date).slice(0, 10)
            const opponentOk = !opponent || g.opponent === opponent
            const fromOk = !normalizedDateFrom || gameDate >= normalizedDateFrom
            const toOk = !normalizedDateTo || gameDate <= normalizedDateTo
            return opponentOk && fromOk && toOk
        })
    }, [allGames, opponent, normalizedDateFrom, normalizedDateTo])
    const displayedRecord = useMemo(() => {
        const source = hasActiveFilters ? filteredGames : allGames
        const wins = source.filter(g => g.result === 'W').length
        const losses = source.filter(g => g.result === 'L').length
        return { wins, losses, games: source.length }
    }, [hasActiveFilters, filteredGames, allGames])

    return (
        <div style={{ display: 'flex', height: '100%', minHeight: 0 }}>
            {/* ── Sidebar ── */}
            <aside style={{
                width: 280, flexShrink: 0, borderRight: '1px solid var(--border)',
                display: 'flex', flexDirection: 'column', overflow: 'hidden',
            }}>
                <div style={{ padding: '16px 14px 10px', borderBottom: '1px solid var(--border)' }}>
                    <p style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-2)', marginBottom: 8 }}>Season</p>
                    <select
                        className="scribble-select"
                        value={season}
                        onChange={e => {
                            setSeason(e.target.value)
                            setSelectedAbbr(null)
                            setOpponent('')
                            setDateFrom('')
                            setDateTo('')
                        }}
                        style={{ width: '100%' }}
                    >
                        {SEASONS.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                </div>

                <div style={{ padding: '10px 14px 6px', borderBottom: '1px solid var(--border)' }}>
                    <p style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-2)' }}>
                        Teams {!teamsLoading && `(${teams.length})`}
                    </p>
                </div>

                <div style={{ flex: 1, overflowY: 'auto' }}>
                    {teamsLoading && (
                        <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                            {[...Array(8)].map((_, i) => <div key={i} style={{ height: 44, borderRadius: 6 }} className="skeleton-row" />)}
                        </div>
                    )}
                    {!teamsLoading && teams.map(t => (
                        <TeamRow
                            key={t.team_id}
                            team={t}
                            isSelected={selectedAbbr === t.abbreviation}
                            onClick={() => {
                                setSelectedAbbr(t.abbreviation)
                                setOpponent('')
                                setDateFrom('')
                                setDateTo('')
                            }}
                        />
                    ))}
                </div>
            </aside>

            {/* ── Main panel ── */}
            <div style={{ flex: 1, overflow: 'auto', padding: '28px 28px' }}>
                {!selectedAbbr && (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 300, gap: 12, textAlign: 'center' }}>
                        <div style={{ width: 48, height: 48, borderRadius: '50%', background: `${ACCENT}10`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: ACCENT }}>
                            <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden>
                                <rect x="3" y="6" width="16" height="12" rx="2" stroke="currentColor" strokeWidth="1.4" />
                                <path d="M7 6V4a4 4 0 0 1 8 0v2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                            </svg>
                        </div>
                        <p style={{ fontWeight: 700, color: 'var(--text-1)', fontSize: '1rem' }}>Select a team</p>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-2)', maxWidth: 300 }}>
                            Pick any team from the sidebar to view their game-by-game stats and season record.
                        </p>
                    </div>
                )}

                {selectedAbbr && statsLoading && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-2)', fontSize: '0.85rem' }}>
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ animation: 'spin 1s linear infinite' }}>
                            <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="28" strokeDashoffset="10" />
                        </svg>
                        Loading team stats…
                    </div>
                )}

                {selectedAbbr && statsError && (
                    <div style={{ padding: '16px 20px', background: 'rgba(255,76,106,0.07)', border: '1px solid rgba(255,76,106,0.2)', borderRadius: 'var(--r-md)' }}>
                        <p style={{ color: 'var(--error)', fontSize: '0.85rem' }}>{statsError}</p>
                    </div>
                )}

                {selectedAbbr && statsData && !statsLoading && (
                    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
                        {/* Team header */}
                        <div style={{ marginBottom: 24 }}>
                            <p style={{ fontFamily: 'var(--font-mono)', fontWeight: 900, fontSize: '1.4rem', color: 'var(--text-1)', letterSpacing: '0.04em', marginBottom: 4 }}>
                                {statsData.team.city} {statsData.team.full_name}
                            </p>
                            <p style={{ fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-3)' }}>
                                {statsData.team.abbreviation} · {statsData.season}
                            </p>
                        </div>

                        {/* Game-log filters */}
                        <p className="section-label" style={{ color: ACCENT, marginBottom: 10 }}>Game Log Filters</p>
                        <div style={{
                            display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center',
                            background: 'var(--bg-panel)', border: '1px solid var(--border)',
                            borderRadius: 'var(--r-md)', padding: '10px 12px', marginBottom: 20,
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <span style={{ fontSize: '0.72rem', color: 'var(--text-3)', fontWeight: 600 }}>Opponent</span>
                                <select
                                    className="scribble-select"
                                    value={opponent}
                                    onChange={e => setOpponent(e.target.value)}
                                    style={{ fontSize: '0.78rem', minWidth: 130 }}
                                >
                                    <option value="">All teams</option>
                                    {opponentOptions
                                        .filter(abbr => abbr !== statsData.team.abbreviation)
                                        .map(abbr => <option key={abbr} value={abbr}>{abbr}</option>)}
                                </select>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <span style={{ fontSize: '0.72rem', color: 'var(--text-3)', fontWeight: 600 }}>From</span>
                                <input
                                    type="date"
                                    value={dateFrom}
                                    onChange={e => setDateFrom(e.target.value)}
                                    style={{
                                        background: 'var(--bg-base)', border: '1px solid var(--border)',
                                        borderRadius: 'var(--r-sm)', padding: '4px 8px',
                                        color: 'var(--text-1)', fontSize: '0.78rem', fontFamily: 'var(--font-mono)',
                                    }}
                                />
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <span style={{ fontSize: '0.72rem', color: 'var(--text-3)', fontWeight: 600 }}>To</span>
                                <input
                                    type="date"
                                    value={dateTo}
                                    onChange={e => setDateTo(e.target.value)}
                                    style={{
                                        background: 'var(--bg-base)', border: '1px solid var(--border)',
                                        borderRadius: 'var(--r-sm)', padding: '4px 8px',
                                        color: 'var(--text-1)', fontSize: '0.78rem', fontFamily: 'var(--font-mono)',
                                    }}
                                />
                            </div>
                            {hasActiveFilters && (
                                <button
                                    onClick={() => { setOpponent(''); setDateFrom(''); setDateTo('') }}
                                    style={{
                                        padding: '5px 10px', background: 'transparent',
                                        border: '1px solid var(--border)', borderRadius: 'var(--r-sm)',
                                        color: 'var(--text-3)', fontSize: '0.72rem', cursor: 'pointer',
                                    }}
                                >
                                    Clear filters
                                </button>
                            )}
                            {hasActiveFilters && (
                                <span style={{
                                    marginLeft: 'auto',
                                    padding: '2px 8px', borderRadius: 20,
                                    background: `${ACCENT}18`, color: ACCENT,
                                    fontSize: '0.68rem', fontWeight: 600,
                                }}>
                                    Filters active
                                </span>
                            )}
                        </div>

                        {hasInvertedRange && (
                            <p style={{ fontSize: '0.72rem', color: 'var(--warning)', marginTop: -10, marginBottom: 16 }}>
                                Date range was normalized automatically (From/To were reversed).
                            </p>
                        )}

                        {/* Record cards */}
                        <p className="section-label" style={{ color: ACCENT, marginBottom: 12 }}>
                            {hasActiveFilters ? 'Filtered Record' : 'Season Record'}
                        </p>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 10, marginBottom: 28 }}>
                            <RecordCard label="Record" value={`${displayedRecord.wins}-${displayedRecord.losses}`} />
                            <RecordCard label="Games" value={displayedRecord.games} />
                            <RecordCard label="Win %" value={displayedRecord.games > 0 ? ((displayedRecord.wins / displayedRecord.games) * 100).toFixed(1) + '%' : '—'} />
                        </div>

                        {/* Game log table */}
                        <p className="section-label" style={{ color: ACCENT, marginBottom: 12 }}>
                            Game Log
                            {hasActiveFilters && (
                                <span style={{ fontSize: '0.72rem', fontWeight: 400, color: 'var(--text-3)', marginLeft: 8 }}>
                                    {opponent ? `vs ${opponent}` : 'all opponents'}
                                    {normalizedDateFrom && normalizedDateTo
                                        ? ` · ${normalizedDateFrom} → ${normalizedDateTo}`
                                        : normalizedDateFrom
                                            ? ` · from ${normalizedDateFrom}`
                                            : normalizedDateTo
                                                ? ` · to ${normalizedDateTo}`
                                                : ''}
                                </span>
                            )}
                        </p>
                        <div style={{
                            background: 'var(--bg-panel)', border: '1px solid var(--border)',
                            borderRadius: 'var(--r-md)', overflow: 'hidden',
                        }}>
                            <div style={{ overflowX: 'auto' }}>
                                <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 900 }}>
                                    <thead>
                                        <tr style={{ borderBottom: '1px solid var(--border)' }}>
                                            {['Date', 'Opp', 'W/L', 'Score', 'FG%', '3P%', 'FT%', 'REB', 'AST', 'TO', 'Off Rtg', 'Def Rtg', 'Pace'].map(h => (
                                                <th key={h} style={{
                                                    padding: '9px 10px',
                                                    textAlign: h === 'Date' || h === 'Opp' || h === 'W/L' || h === 'Score' ? 'left' : 'right',
                                                    fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em',
                                                    color: 'var(--text-2)', whiteSpace: 'nowrap',
                                                }}>{h}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {filteredGames.map((g, i) => (
                                            <tr key={g.game_id} style={{ borderBottom: i < filteredGames.length - 1 ? '1px solid var(--border)' : 'none' }}>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>{fmtDate(g.game_date)}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-1)', fontWeight: 600 }}>{g.location} {g.opponent}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: g.result === 'W' ? '#4ADE80' : g.result === 'L' ? 'var(--error)' : 'var(--text-3)', fontWeight: 700 }}>{g.result ?? '—'}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-1)', fontWeight: 700 }}>{g.points}–{g.opponent_points ?? '?'}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>{pct(g.field_goal_pct)}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>{pct(g.three_point_pct)}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>{pct(g.free_throw_pct)}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>{g.rebounds}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>{g.assists}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>{g.turnovers}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>{num(g.offensive_rating)}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>{num(g.defensive_rating)}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>{num(g.pace)}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {filteredGames.length === 0 && (
                            <div style={{ padding: '20px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', marginTop: 12 }}>
                                <p style={{ fontSize: '0.85rem', color: 'var(--text-2)' }}>
                                    {hasActiveFilters
                                        ? `No games found for the selected filters in ${season}.`
                                        : `No games found for this team in ${season}.`}
                                </p>
                            </div>
                        )}
                    </motion.div>
                )}
            </div>
        </div>
    )
}
