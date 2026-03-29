import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { useTeamsList, useTeamGameStats } from '../../hooks/useApi'
import type { TeamGameLogEntry } from '../../types'
import NbaTeamLogo from '../NbaTeamLogo'
import { openGrafanaCreateDashboard } from '../../utils/grafana'
import { getNbaTeamLogoUrl } from '../../utils/nbaTeams'

const ACCENT = '#0E8ED8'
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

function int(v: number | null | undefined): string {
    if (v == null) return '—'
    return Math.round(v).toLocaleString('en-US')
}

function valueOrZero(v: number | null | undefined): number {
    return typeof v === 'number' ? v : 0
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
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <NbaTeamLogo team={team.team_id} altLabel={team.full_name} size={20} />
                <span style={{
                    fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '0.82rem',
                    color: isSelected ? ACCENT : 'var(--text-1)',
                }}>
                    {team.abbreviation}
                </span>
            </span>
            <p style={{ fontSize: '0.7rem', color: 'var(--text-3)', margin: '2px 0 0', fontFamily: 'var(--font-mono)' }}>
                {team.full_name}
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

type StatPadMetric = {
    key: string
    chipLabel: string
    tableLabel: string
    perGame: string
    totalOrSample: string
    detail: string
}

export default function TeamStatsView() {
    const [selectedSeasons, setSelectedSeasons] = useState<string[]>(['2025-26'])
    const [selectedAbbr, setSelectedAbbr] = useState<string | null>(null)
    const [opponent, setOpponent] = useState('')
    const [dateFrom, setDateFrom] = useState('')
    const [dateTo, setDateTo] = useState('')
    const [showStatPad, setShowStatPad] = useState(false)
    const [activeMetricKey, setActiveMetricKey] = useState('points')

    const { data: teamsData, loading: teamsLoading } = useTeamsList()
    const { data: statsData, loading: statsLoading, error: statsError } = useTeamGameStats(selectedAbbr, selectedSeasons, 200)

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
    const statPadMetrics = useMemo<StatPadMetric[]>(() => {
        const totals = filteredGames.reduce((acc, game) => {
            acc.points += valueOrZero(game.points)
            acc.rebounds += valueOrZero(game.rebounds)
            acc.turnovers += valueOrZero(game.turnovers)
            acc.fieldGoalsMade += valueOrZero(game.field_goals_made)
            acc.fieldGoalsAttempted += valueOrZero(game.field_goals_attempted)
            acc.threePointsMade += valueOrZero(game.three_points_made)
            acc.threePointsAttempted += valueOrZero(game.three_points_attempted)
            acc.freeThrowsMade += valueOrZero(game.free_throws_made)
            acc.offensiveRating += valueOrZero(game.offensive_rating)
            acc.pace += valueOrZero(game.pace)
            return acc
        }, {
            points: 0,
            rebounds: 0,
            turnovers: 0,
            fieldGoalsMade: 0,
            fieldGoalsAttempted: 0,
            threePointsMade: 0,
            threePointsAttempted: 0,
            freeThrowsMade: 0,
            offensiveRating: 0,
            pace: 0,
        })

        const gamesCount = filteredGames.length
        const avg = (value: number, decimals = 1) => (gamesCount ? (value / gamesCount).toFixed(decimals) : '—')
        const totalTwoPointMade = Math.max(totals.fieldGoalsMade - totals.threePointsMade, 0)

        return [
            {
                key: 'points',
                chipLabel: 'Avg points',
                tableLabel: 'Points',
                perGame: avg(totals.points),
                totalOrSample: `${int(totals.points)} total`,
                detail: 'Scoring output across the current season and filter scope.',
            },
            {
                key: 'rebounds',
                chipLabel: 'Avg rebounds',
                tableLabel: 'Rebounds',
                perGame: avg(totals.rebounds),
                totalOrSample: `${int(totals.rebounds)} total`,
                detail: 'Total board control, including both ends of the floor.',
            },
            {
                key: 'three-point-attempts',
                chipLabel: 'Avg 3PA',
                tableLabel: 'Three-point attempts',
                perGame: avg(totals.threePointsAttempted),
                totalOrSample: `${int(totals.threePointsAttempted)} attempts`,
                detail: 'How often this team is getting up threes per game.',
            },
            {
                key: 'three-point-made',
                chipLabel: 'Avg 3PM',
                tableLabel: 'Three-pointers made',
                perGame: avg(totals.threePointsMade),
                totalOrSample: `${int(totals.threePointsMade)} made`,
                detail: 'Made threes per game across the filtered sample.',
            },
            {
                key: 'two-point-made',
                chipLabel: 'Avg 2PM',
                tableLabel: 'Two-pointers made',
                perGame: avg(totalTwoPointMade),
                totalOrSample: `${int(totalTwoPointMade)} made`,
                detail: 'Interior and mid-range makes after subtracting made threes.',
            },
            {
                key: 'free-throws-made',
                chipLabel: 'Avg FTM',
                tableLabel: 'Free throws made',
                perGame: avg(totals.freeThrowsMade),
                totalOrSample: `${int(totals.freeThrowsMade)} made`,
                detail: 'Free throws converted per game in this sample.',
            },
            {
                key: 'games',
                chipLabel: 'Total items',
                tableLabel: 'Games in sample',
                perGame: '—',
                totalOrSample: `${gamesCount} games`,
                detail: 'Total number of team-game records matching the active filters.',
            },
            {
                key: 'turnovers',
                chipLabel: 'Avg turnovers',
                tableLabel: 'Turnovers',
                perGame: avg(totals.turnovers),
                totalOrSample: `${int(totals.turnovers)} total`,
                detail: 'Lost possessions per game across the current selection.',
            },
            {
                key: 'offensive-rating',
                chipLabel: 'Off. rating',
                tableLabel: 'Offensive rating',
                perGame: avg(totals.offensiveRating),
                totalOrSample: `${gamesCount} game sample`,
                detail: 'Average points scored per 100 possessions.',
            },
            {
                key: 'pace',
                chipLabel: 'Pace',
                tableLabel: 'Pace',
                perGame: avg(totals.pace),
                totalOrSample: `${gamesCount} game sample`,
                detail: 'Estimated possessions per 48 minutes.',
            },
        ]
    }, [filteredGames])
    const activeMetric = statPadMetrics.find(metric => metric.key === activeMetricKey) ?? statPadMetrics[0]
    const allSeasonsSelected = selectedSeasons.length === SEASONS.length
    const seasonLabel = allSeasonsSelected ? 'All seasons' : selectedSeasons.join(', ')
    const hasSeasonScopeFilter = !(selectedSeasons.length === 1 && selectedSeasons[0] === '2025-26')
    const selectedTeamLogoUrl = useMemo(
        () => (statsData?.team?.team_id ? getNbaTeamLogoUrl(statsData.team.team_id) : null),
        [statsData?.team?.team_id],
    )

    function toggleSeason(season: string) {
        setSelectedSeasons(prev => {
            if (prev.includes(season)) {
                if (prev.length === 1) return prev
                return prev.filter(s => s !== season)
            }
            const next = [...prev, season]
            return SEASONS.filter(s => next.includes(s))
        })
    }

    function toggleAllSeasons() {
        setSelectedSeasons(prev => (prev.length === SEASONS.length ? ['2025-26'] : [...SEASONS]))
    }

    function saveCurrentView() {
        if (!statsData) return
        openGrafanaCreateDashboard()
    }

    return (
        <div style={{ display: 'flex', height: '100%', minHeight: 0 }}>
            {/* ── Sidebar ── */}
            <aside style={{
                width: 280, flexShrink: 0, borderRight: '1px solid var(--border)',
                display: 'flex', flexDirection: 'column', overflow: 'hidden',
            }}>
                <div style={{ padding: '16px 14px 10px', borderBottom: '1px solid var(--border)' }}>
                    <p style={{ fontSize: '0.7rem', color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
                        Select a team to view game logs.
                    </p>
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
                                setShowStatPad(false)
                                setActiveMetricKey('points')
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
                        <div
                            style={{
                                marginBottom: 24,
                                border: '1px solid var(--border)',
                                borderRadius: 'var(--r-md)',
                                background: 'linear-gradient(135deg, color-mix(in srgb, var(--bg-panel) 90%, #0B1220 10%), var(--bg-panel))',
                                padding: '18px 20px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                gap: 14,
                                flexWrap: 'wrap',
                            }}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', gap: 22 }}>
                                <div
                                    style={{
                                        width: 'clamp(146px, 18vw, 186px)',
                                        height: 'clamp(92px, 12vw, 122px)',
                                        borderRadius: 18,
                                        border: '1px solid color-mix(in srgb, var(--border-mid) 84%, white 16%)',
                                        background: 'linear-gradient(145deg, color-mix(in srgb, var(--bg-elevated) 94%, white 6%), color-mix(in srgb, var(--bg-panel) 90%, black 10%))',
                                        boxShadow: '0 14px 32px rgba(0,0,0,0.28)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        overflow: 'hidden',
                                        padding: '6px 10px',
                                    }}
                                >
                                    {selectedTeamLogoUrl ? (
                                        <img
                                            src={selectedTeamLogoUrl}
                                            alt={`${statsData.team.full_name} logo`}
                                            style={{
                                                width: '100%',
                                                height: '100%',
                                                objectFit: 'contain',
                                                filter: 'drop-shadow(0 2px 8px rgba(0,0,0,0.35))',
                                            }}
                                        />
                                    ) : (
                                        <NbaTeamLogo team={statsData.team.team_id} altLabel={statsData.team.full_name} size={108} />
                                    )}
                                </div>
                                <div>
                                    <p
                                        style={{
                                            fontFamily: 'var(--font-display)',
                                            fontWeight: 800,
                                            fontSize: '2rem',
                                            color: 'var(--text-1)',
                                            letterSpacing: '0.01em',
                                            lineHeight: 1.05,
                                            marginBottom: 10,
                                        }}
                                    >
                                        {statsData.team.full_name}
                                    </p>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                                        <span
                                            style={{
                                                borderRadius: 999,
                                                border: '1px solid var(--border-mid)',
                                                background: 'var(--bg-elevated)',
                                                color: 'var(--text-2)',
                                                padding: '4px 10px',
                                                fontSize: '0.74rem',
                                                fontWeight: 700,
                                                fontFamily: 'var(--font-mono)',
                                            }}
                                        >
                                            USA
                                        </span>
                                        <span
                                            style={{
                                                borderRadius: 999,
                                                border: `1px solid ${ACCENT}66`,
                                                background: `${ACCENT}14`,
                                                color: ACCENT,
                                                padding: '4px 10px',
                                                fontSize: '0.74rem',
                                                fontWeight: 700,
                                                fontFamily: 'var(--font-mono)',
                                            }}
                                        >
                                            {statsData.team.abbreviation}
                                        </span>
                                        <span
                                            style={{
                                                borderRadius: 999,
                                                border: '1px solid var(--border-mid)',
                                                background: 'var(--bg-elevated)',
                                                color: 'var(--text-3)',
                                                padding: '4px 10px',
                                                fontSize: '0.74rem',
                                                fontWeight: 700,
                                                fontFamily: 'var(--font-mono)',
                                            }}
                                        >
                                            {seasonLabel}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <button
                                onClick={saveCurrentView}
                                style={{
                                    padding: '7px 13px',
                                    borderRadius: 'var(--r-sm)',
                                    border: `1px solid ${ACCENT}`,
                                    background: `${ACCENT}12`,
                                    color: ACCENT,
                                    fontSize: '0.76rem',
                                    fontWeight: 700,
                                    fontFamily: 'var(--font-mono)',
                                    cursor: 'pointer',
                                }}
                            >
                                Create Dashboard
                            </button>
                        </div>

                        {/* Game-log filters */}
                        <p className="section-label" style={{ color: ACCENT, marginBottom: 10 }}>Game Log Filters</p>
                        <div style={{
                            display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center',
                            background: 'var(--bg-panel)', border: '1px solid var(--border)',
                            borderRadius: 'var(--r-md)', padding: '10px 12px', marginBottom: 20,
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                                <span style={{ fontSize: '0.72rem', color: 'var(--text-3)', fontWeight: 600 }}>Seasons</span>
                                <button
                                    onClick={toggleAllSeasons}
                                    style={{
                                        padding: '5px 10px', borderRadius: 16, cursor: 'pointer',
                                        border: `1px solid ${allSeasonsSelected ? ACCENT : 'var(--border)'}`,
                                        background: allSeasonsSelected ? `${ACCENT}20` : 'var(--bg-base)',
                                        color: allSeasonsSelected ? ACCENT : 'var(--text-2)',
                                        fontSize: '0.72rem', fontWeight: 700, fontFamily: 'var(--font-mono)',
                                    }}
                                >
                                    All seasons
                                </button>
                                {SEASONS.map(s => {
                                    const active = selectedSeasons.includes(s)
                                    return (
                                        <button
                                            key={s}
                                            onClick={() => toggleSeason(s)}
                                            style={{
                                                padding: '5px 10px', borderRadius: 16, cursor: 'pointer',
                                                border: `1px solid ${active ? ACCENT : 'var(--border)'}`,
                                                background: active ? `${ACCENT}20` : 'var(--bg-base)',
                                                color: active ? ACCENT : 'var(--text-2)',
                                                fontSize: '0.72rem', fontWeight: 700, fontFamily: 'var(--font-mono)',
                                            }}
                                        >
                                            {s}
                                        </button>
                                    )
                                })}
                            </div>
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
                            {(hasActiveFilters || hasSeasonScopeFilter) ? 'Filtered Record' : 'Season Record'}
                        </p>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10, marginBottom: showStatPad ? 12 : 28 }}>
                            <RecordCard label="Record" value={`${displayedRecord.wins}-${displayedRecord.losses}`} />
                            <RecordCard label="Games" value={displayedRecord.games} />
                            <RecordCard label="Win %" value={displayedRecord.games > 0 ? ((displayedRecord.wins / displayedRecord.games) * 100).toFixed(1) + '%' : '—'} />
                            <button
                                onClick={() => setShowStatPad(prev => !prev)}
                                style={{
                                    minHeight: 86,
                                    display: 'flex',
                                    flexDirection: 'column',
                                    justifyContent: 'space-between',
                                    textAlign: 'left',
                                    background: showStatPad ? `${ACCENT}14` : 'var(--bg-panel)',
                                    border: `1px solid ${showStatPad ? ACCENT : 'var(--border)'}`,
                                    borderRadius: 'var(--r-md)',
                                    padding: '14px 16px',
                                    cursor: 'pointer',
                                    transition: 'border-color 0.15s ease, background 0.15s ease',
                                }}
                            >
                                <span style={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: showStatPad ? ACCENT : 'var(--text-2)' }}>
                                    Season Stat Pad
                                </span>
                                <div>
                                    <p style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.98rem', color: 'var(--text-1)', margin: '0 0 4px' }}>
                                        {showStatPad ? 'Hide advanced breakdown' : 'Open advanced breakdown'}
                                    </p>
                                    <p style={{ fontSize: '0.72rem', color: 'var(--text-3)', margin: 0 }}>
                                        10 filter-aware summary metrics in an inline table.
                                    </p>
                                </div>
                            </button>
                        </div>

                        {showStatPad && (
                            <motion.div
                                initial={{ opacity: 0, y: 8 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.18 }}
                                style={{
                                    marginBottom: 28,
                                    background: 'var(--bg-panel)',
                                    border: '1px solid var(--border)',
                                    borderRadius: 'var(--r-md)',
                                    padding: '14px',
                                }}
                            >
                                <div
                                    style={{
                                        display: 'flex',
                                        alignItems: 'flex-start',
                                        justifyContent: 'space-between',
                                        gap: 12,
                                        flexWrap: 'wrap',
                                        marginBottom: 14,
                                    }}
                                >
                                    <div>
                                        <p style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: ACCENT, marginBottom: 4 }}>
                                            Inline Stat Pad
                                        </p>
                                        <p style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-1)', margin: 0 }}>
                                            {activeMetric?.tableLabel ?? 'Season metrics'}
                                        </p>
                                        <p style={{ fontSize: '0.78rem', color: 'var(--text-3)', margin: '6px 0 0' }}>
                                            {activeMetric?.detail ?? 'Extra team metrics update automatically with the active season and game-log filters.'}
                                        </p>
                                    </div>
                                    <div
                                        style={{
                                            minWidth: 180,
                                            padding: '10px 12px',
                                            borderRadius: 'var(--r-sm)',
                                            border: `1px solid ${ACCENT}33`,
                                            background: `${ACCENT}10`,
                                        }}
                                    >
                                        <p style={{ fontSize: '0.66rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: ACCENT, marginBottom: 4 }}>
                                            Selected Readout
                                        </p>
                                        <p style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '1rem', color: 'var(--text-1)', margin: 0 }}>
                                            {activeMetric?.perGame ?? '—'}
                                            <span style={{ color: 'var(--text-3)', fontSize: '0.72rem', fontWeight: 600, marginLeft: 6 }}>
                                                {activeMetric?.perGame === '—' ? 'in sample' : 'per game'}
                                            </span>
                                        </p>
                                        <p style={{ fontSize: '0.72rem', color: 'var(--text-3)', margin: '4px 0 0' }}>
                                            {activeMetric?.totalOrSample ?? '—'}
                                        </p>
                                    </div>
                                </div>

                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>
                                    {statPadMetrics.map(metric => {
                                        const isActive = metric.key === activeMetric?.key
                                        return (
                                            <button
                                                key={metric.key}
                                                onClick={() => setActiveMetricKey(metric.key)}
                                                style={{
                                                    padding: '7px 11px',
                                                    borderRadius: 999,
                                                    border: `1px solid ${isActive ? ACCENT : 'var(--border)'}`,
                                                    background: isActive ? `${ACCENT}18` : 'var(--bg-base)',
                                                    color: isActive ? ACCENT : 'var(--text-2)',
                                                    fontSize: '0.72rem',
                                                    fontWeight: 700,
                                                    fontFamily: 'var(--font-mono)',
                                                    cursor: 'pointer',
                                                }}
                                            >
                                                {metric.chipLabel}
                                            </button>
                                        )
                                    })}
                                </div>

                                <div style={{ overflowX: 'auto' }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 700 }}>
                                        <thead>
                                            <tr style={{ borderBottom: '1px solid var(--border)' }}>
                                                {['Metric', 'Per game', 'Total / Sample', 'What it shows'].map(header => (
                                                    <th
                                                        key={header}
                                                        style={{
                                                            padding: '10px 12px',
                                                            textAlign: header === 'Metric' || header === 'What it shows' ? 'left' : 'right',
                                                            fontSize: '0.68rem',
                                                            fontWeight: 700,
                                                            textTransform: 'uppercase',
                                                            letterSpacing: '0.07em',
                                                            color: 'var(--text-2)',
                                                        }}
                                                    >
                                                        {header}
                                                    </th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {statPadMetrics.map((metric, index) => {
                                                const isActive = metric.key === activeMetric?.key
                                                return (
                                                    <tr
                                                        key={metric.key}
                                                        style={{
                                                            borderBottom: index < statPadMetrics.length - 1 ? '1px solid var(--border)' : 'none',
                                                            background: isActive ? `${ACCENT}08` : 'transparent',
                                                        }}
                                                    >
                                                        <td style={{ padding: '10px 12px', fontSize: '0.8rem', fontWeight: 700, color: isActive ? ACCENT : 'var(--text-1)' }}>
                                                            {metric.tableLabel}
                                                        </td>
                                                        <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: '0.8rem', fontFamily: 'var(--font-mono)', color: 'var(--text-1)' }}>
                                                            {metric.perGame}
                                                        </td>
                                                        <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>
                                                            {metric.totalOrSample}
                                                        </td>
                                                        <td style={{ padding: '10px 12px', fontSize: '0.76rem', color: 'var(--text-3)' }}>
                                                            {metric.detail}
                                                        </td>
                                                    </tr>
                                                )
                                            })}
                                        </tbody>
                                    </table>
                                </div>

                                <p style={{ fontSize: '0.72rem', color: 'var(--text-3)', margin: '12px 2px 0' }}>
                                    Positioning note: keeping the stat pad directly under the core record cards makes the extra metrics feel attached to the season summary without pushing the game log too far down.
                                </p>
                            </motion.div>
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
                                                <td style={{ padding: '8px 10px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-1)', fontWeight: 600 }}>
                                                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                                                        <span>{g.location}</span>
                                                        <NbaTeamLogo team={g.opponent} altLabel={g.opponent} size={18} />
                                                        <span>{g.opponent}</span>
                                                    </span>
                                                </td>
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
                                        ? `No games found for the selected filters in ${seasonLabel}.`
                                        : `No games found for this team in ${seasonLabel}.`}
                                </p>
                            </div>
                        )}
                    </motion.div>
                )}
            </div>
        </div>
    )
}
