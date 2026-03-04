import React, { useState, lazy, Suspense } from 'react'

const MatchDeepDive = lazy(() => import('./MatchDeepDive'))
const PlayerStatsView = lazy(() => import('./PlayerStatsView'))
const TeamStatsView = lazy(() => import('./TeamStatsView'))

const ACCENT = '#0E8ED8'

type DeepDiveMode = 'match' | 'player' | 'team'

const MODES: { id: DeepDiveMode; label: string; desc: string; icon: React.ReactNode }[] = [
    {
        id: 'match',
        label: 'Match Stats',
        desc: 'Game-level box scores, AI predictions & SHAP explainability',
        icon: (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
                <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.2" />
                <path d="M7 4v3l2.5 1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
        ),
    },
    {
        id: 'player',
        label: 'Player Stats',
        desc: 'Search any player to view their game log and season averages',
        icon: (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
                <circle cx="7" cy="5" r="2.5" stroke="currentColor" strokeWidth="1.2" />
                <path d="M2.5 12.5c0-2.5 2-4.5 4.5-4.5s4.5 2 4.5 4.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
            </svg>
        ),
    },
    {
        id: 'team',
        label: 'Team Stats',
        desc: 'Pick a team to see their game log, record, and advanced stats',
        icon: (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
                <rect x="2" y="5" width="10" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.2" />
                <path d="M4.5 5V3.5a2.5 2.5 0 0 1 5 0V5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
            </svg>
        ),
    },
]

function LoadingSub() {
    return (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: 'var(--text-2)', gap: 10, fontSize: '0.85rem' }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ animation: 'spin 1s linear infinite' }}>
                <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="28" strokeDashoffset="10" />
            </svg>
            Loading…
        </div>
    )
}

export default function DeepDive() {
    const [mode, setMode] = useState<DeepDiveMode>('match')

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            {/* ── Mode selector bar ── */}
            <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '12px 28px',
                borderBottom: '1px solid var(--border)',
                background: 'var(--bg-surface)',
                flexShrink: 0,
            }}>
                <span style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-3)', marginRight: 8 }}>
                    Deep Dive Into
                </span>
                {MODES.map(m => {
                    const isActive = m.id === mode
                    return (
                        <button
                            key={m.id}
                            title={m.desc}
                            onClick={() => setMode(m.id)}
                            style={{
                                display: 'flex', alignItems: 'center', gap: 6,
                                padding: '6px 14px', borderRadius: 20,
                                background: isActive ? `${ACCENT}15` : 'transparent',
                                border: `1px solid ${isActive ? ACCENT : 'var(--border)'}`,
                                color: isActive ? ACCENT : 'var(--text-2)',
                                fontFamily: 'var(--font-ui)', fontSize: '0.78rem',
                                fontWeight: isActive ? 700 : 500,
                                cursor: 'pointer', transition: 'all 0.15s ease',
                            }}
                            onMouseEnter={e => {
                                if (!isActive) {
                                    e.currentTarget.style.borderColor = 'var(--text-2)'
                                    e.currentTarget.style.color = 'var(--text-1)'
                                }
                            }}
                            onMouseLeave={e => {
                                if (!isActive) {
                                    e.currentTarget.style.borderColor = 'var(--border)'
                                    e.currentTarget.style.color = 'var(--text-2)'
                                }
                            }}
                        >
                            <span style={{ opacity: isActive ? 1 : 0.6, display: 'flex' }}>{m.icon}</span>
                            {m.label}
                        </button>
                    )
                })}
            </div>

            {/* ── Sub-view ── */}
            <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
                <Suspense fallback={<LoadingSub />}>
                    {mode === 'match' && <MatchDeepDive />}
                    {mode === 'player' && <PlayerStatsView />}
                    {mode === 'team' && <TeamStatsView />}
                </Suspense>
            </div>
        </div>
    )
}
