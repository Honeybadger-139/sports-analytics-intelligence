import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { usePlayers, usePlayerGameStats, useTeamsList } from '../../hooks/useApi'
import type { PlayerListItem, PlayerGameLogEntry } from '../../types'

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

function PlayerRow({ player, isSelected, onClick }: { player: PlayerListItem; isSelected: boolean; onClick: () => void }) {
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
                {player.full_name}
            </span>
            {player.team_abbreviation && (
                <p style={{ fontSize: '0.7rem', color: 'var(--text-3)', margin: '2px 0 0', fontFamily: 'var(--font-mono)' }}>
                    {player.team_abbreviation}
                </p>
            )}
        </button>
    )
}

function StatCard({ label, value }: { label: string; value: string | number }) {
    return (
        <div style={{
            background: 'var(--bg-panel)', border: '1px solid var(--border)',
            borderRadius: 'var(--r-md)', padding: '12px 16px', textAlign: 'center',
        }}>
            <p style={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-2)', marginBottom: 4 }}>
                {label}
            </p>
            <p style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '1.1rem', color: ACCENT, margin: 0 }}>
                {value}
            </p>
        </div>
    )
}

export default function PlayerStatsView() {
    const [season, setSeason] = useState('2025-26')
    const [search, setSearch] = useState('')
    const [selectedId, setSelectedId] = useState<number | null>(null)
    const [opponent, setOpponent] = useState('')
    const [dateFrom, setDateFrom] = useState('')
    const [dateTo, setDateTo] = useState('')

    const { data: playerData, loading: searchLoading } = usePlayers(search)
    const { data: teamsData } = useTeamsList()

    const rawDateFrom = dateFrom || undefined
    const rawDateTo = dateTo || undefined
    const hasInvertedRange = !!(rawDateFrom && rawDateTo && rawDateFrom > rawDateTo)
    const normalizedDateFrom = hasInvertedRange ? rawDateTo : rawDateFrom
    const normalizedDateTo = hasInvertedRange ? rawDateFrom : rawDateTo
    const hasActiveFilters = !!(opponent || normalizedDateFrom || normalizedDateTo)

    const { data: statsData, loading: statsLoading, error: statsError } = usePlayerGameStats(selectedId, season, {
        limit: 200,
        opponent: opponent || undefined,
        dateFrom: normalizedDateFrom,
        dateTo: normalizedDateTo,
    })

    const players = playerData?.players ?? []
    const opponentOptions = useMemo(
        () => [...new Set((teamsData?.teams ?? []).map(t => t.abbreviation))].sort(),
        [teamsData?.teams],
    )

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
                            setSelectedId(null)
                            setOpponent('')
                            setDateFrom('')
                            setDateTo('')
                        }}
                        style={{ width: '100%', marginBottom: 10 }}
                    >
                        {SEASONS.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                    <p style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-2)', marginBottom: 6 }}>Search Players</p>
                    <input
                        type="text"
                        placeholder="Type a name…"
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                        style={{
                            width: '100%', padding: '8px 12px', borderRadius: 'var(--r-md)',
                            border: '1px solid var(--border)', background: 'var(--bg-elevated)',
                            color: 'var(--text-1)', fontFamily: 'var(--font-mono)', fontSize: '0.82rem',
                            outline: 'none', boxSizing: 'border-box',
                        }}
                    />
                </div>

                <div style={{ padding: '10px 14px 6px', borderBottom: '1px solid var(--border)' }}>
                    <p style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-2)' }}>
                        Players {!searchLoading && players.length > 0 && `(${players.length})`}
                    </p>
                </div>

                <div style={{ flex: 1, overflowY: 'auto' }}>
                    {searchLoading && (
                        <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                            {[...Array(6)].map((_, i) => <div key={i} style={{ height: 40, borderRadius: 6 }} className="skeleton-row" />)}
                        </div>
                    )}
                    {!searchLoading && search.length >= 2 && players.length === 0 && (
                        <p style={{ padding: '16px 14px', fontSize: '0.8rem', color: 'var(--text-3)' }}>No players found.</p>
                    )}
                    {!searchLoading && search.length < 2 && (
                        <p style={{ padding: '16px 14px', fontSize: '0.8rem', color: 'var(--text-3)' }}>Type at least 2 characters to search.</p>
                    )}
                    {!searchLoading && players.map(p => (
                        <PlayerRow
                            key={p.player_id}
                            player={p}
                            isSelected={selectedId === p.player_id}
                            onClick={() => setSelectedId(p.player_id)}
                        />
                    ))}
                </div>
            </aside>

            {/* ── Main panel ── */}
            <div style={{ flex: 1, overflow: 'auto', padding: '28px 28px' }}>
                {!selectedId && (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 300, gap: 12, textAlign: 'center' }}>
                        <div style={{ width: 48, height: 48, borderRadius: '50%', background: `${ACCENT}10`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: ACCENT }}>
                            <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden>
                                <circle cx="11" cy="8" r="4" stroke="currentColor" strokeWidth="1.4" />
                                <path d="M4 19c0-3.3 3.1-6 7-6s7 2.7 7 6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                            </svg>
                        </div>
                        <p style={{ fontWeight: 700, color: 'var(--text-1)', fontSize: '1rem' }}>Search for a player</p>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-2)', maxWidth: 300 }}>
                            Type a player name in the sidebar to find them and view their game-by-game stats.
                        </p>
                    </div>
                )}

                {selectedId && statsLoading && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-2)', fontSize: '0.85rem' }}>
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ animation: 'spin 1s linear infinite' }}>
                            <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="28" strokeDashoffset="10" />
                        </svg>
                        Loading player stats…
                    </div>
                )}

                {selectedId && statsError && (
                    <div style={{ padding: '16px 20px', background: 'rgba(255,76,106,0.07)', border: '1px solid rgba(255,76,106,0.2)', borderRadius: 'var(--r-md)' }}>
                        <p style={{ color: 'var(--error)', fontSize: '0.85rem' }}>{statsError}</p>
                    </div>
                )}

                {selectedId && statsData && !statsLoading && (
                    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
                        {/* Player header */}
                        <div style={{ marginBottom: 24 }}>
                            <p style={{ fontFamily: 'var(--font-mono)', fontWeight: 900, fontSize: '1.4rem', color: 'var(--text-1)', letterSpacing: '0.04em', marginBottom: 4 }}>
                                {statsData.player.full_name}
                            </p>
                            <p style={{ fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-3)' }}>
                                {statsData.player.team_abbreviation} · {statsData.season}
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
                                        .filter(abbr => abbr !== statsData.player.team_abbreviation)
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

                        {/* Averages cards */}
                        {Object.keys(statsData.averages).length > 0 && (
                            <>
                                <p className="section-label" style={{ color: ACCENT, marginBottom: 12 }}>
                                    {hasActiveFilters ? 'Filtered Averages' : 'Season Averages'}
                                </p>
                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: 10, marginBottom: 28 }}>
                                    <StatCard label="GP" value={statsData.averages.games_played ?? 0} />
                                    <StatCard label="PPG" value={statsData.averages.points ?? 0} />
                                    <StatCard label="RPG" value={statsData.averages.rebounds ?? 0} />
                                    <StatCard label="APG" value={statsData.averages.assists ?? 0} />
                                    <StatCard label="SPG" value={statsData.averages.steals ?? 0} />
                                    <StatCard label="BPG" value={statsData.averages.blocks ?? 0} />
                                </div>
                            </>
                        )}

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
                                <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 800 }}>
                                    <thead>
                                        <tr style={{ borderBottom: '1px solid var(--border)' }}>
                                            {['Date', 'Opp', 'W/L', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 'FG%', '3P%', 'FT%', '+/-'].map(h => (
                                                <th key={h} style={{
                                                    padding: '9px 10px', textAlign: h === 'Date' || h === 'Opp' || h === 'W/L' ? 'left' : 'right',
                                                    fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em',
                                                    color: 'var(--text-2)', whiteSpace: 'nowrap',
                                                }}>{h}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {(statsData.games as PlayerGameLogEntry[]).map((g, i) => (
                                            <tr key={g.game_id} style={{ borderBottom: i < statsData.games.length - 1 ? '1px solid var(--border)' : 'none' }}>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>{fmtDate(g.game_date)}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-1)', fontWeight: 600 }}>{g.location} {g.opponent}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: g.result === 'W' ? '#4ADE80' : g.result === 'L' ? 'var(--error)' : 'var(--text-3)', fontWeight: 700 }}>{g.result ?? '—'}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>{g.minutes ?? '—'}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-1)', fontWeight: 700, textAlign: 'right' }}>{g.points}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>{g.rebounds}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>{g.assists}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>{g.steals}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>{g.blocks}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>{g.turnovers}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>{pct(g.field_goal_pct)}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>{pct(g.three_point_pct)}</td>
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>{pct(g.free_throw_pct)}</td>
                                                <td style={{
                                                    padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', textAlign: 'right',
                                                    color: (g.plus_minus ?? 0) > 0 ? '#4ADE80' : (g.plus_minus ?? 0) < 0 ? 'var(--error)' : 'var(--text-3)',
                                                    fontWeight: 600,
                                                }}>{g.plus_minus != null ? (g.plus_minus > 0 ? `+${g.plus_minus}` : g.plus_minus) : '—'}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {statsData.games.length === 0 && (
                            <div style={{ padding: '20px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', marginTop: 12 }}>
                                <p style={{ fontSize: '0.85rem', color: 'var(--text-2)' }}>
                                    {hasActiveFilters
                                        ? `No games found for the selected filters in ${season}.`
                                        : `No games found for this player in ${season}.`}
                                </p>
                            </div>
                        )}
                    </motion.div>
                )}
            </div>
        </div>
    )
}
