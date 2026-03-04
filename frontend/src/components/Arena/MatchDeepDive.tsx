import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useMatches, useGamePrediction } from '../../hooks/useApi'
import type { DashboardCreateRouteState, MatchRow, ModelPrediction, ShapFactor } from '../../types'

const ACCENT = '#0E8ED8'
const SEASONS = ['2025-26', '2024-25', '2023-24']

const MODEL_LABELS: Record<string, string> = {
  ensemble: 'Ensemble',
  xgboost: 'XGBoost',
  lgbm: 'LightGBM',
  logistic_regression: 'Logistic',
}

function fmtDate(iso: string): string {
  try { return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }
  catch { return iso }
}

function ShapBar({ value, maxAbs }: { value: number; maxAbs: number }) {
  const pct = maxAbs > 0 ? Math.abs(value) / maxAbs * 100 : 0
  const isPos = value >= 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%' }}>
      {/* Negative side */}
      <div style={{ flex: 1, display: 'flex', justifyContent: 'flex-end' }}>
        {!isPos && (
          <div style={{ width: `${pct}%`, height: 6, background: 'var(--error)', borderRadius: '2px 0 0 2px' }} />
        )}
      </div>
      {/* Centre axis */}
      <div style={{ width: 1, height: 12, background: 'var(--border-mid)', flexShrink: 0 }} />
      {/* Positive side */}
      <div style={{ flex: 1 }}>
        {isPos && (
          <div style={{ width: `${pct}%`, height: 6, background: ACCENT, borderRadius: '0 2px 2px 0' }} />
        )}
      </div>
    </div>
  )
}

function GameRow({ match, isSelected, onClick }: { match: MatchRow; isSelected: boolean; onClick: () => void }) {
  const completed = match.winner_team_id != null
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
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
        <span style={{
          fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '0.82rem',
          color: isSelected ? ACCENT : 'var(--text-1)',
        }}>
          {match.home_team} vs {match.away_team}
        </span>
        {completed && match.home_score != null && (
          <span style={{ fontSize: '0.72rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', flexShrink: 0 }}>
            {match.home_score}–{match.away_score}
          </span>
        )}
      </div>
      <p style={{ fontSize: '0.7rem', color: 'var(--text-3)', margin: '2px 0 0', fontFamily: 'var(--font-mono)' }}>
        {fmtDate(match.game_date)} · {match.season}
      </p>
    </button>
  )
}

export default function MatchDeepDive() {
  const navigate = useNavigate()
  const [season, setSeason] = useState('2025-26')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  // Filters
  const [teamSearch, setTeamSearch] = useState('')
  const [dateMode, setDateMode] = useState<'exact' | 'range' | 'all'>('all')
  const [exactDate, setExactDate] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  const { data: matchData, loading: matchLoading } = useMatches(
    season,
    50,
    teamSearch,
    dateMode === 'exact' ? exactDate : undefined,
    dateMode === 'range' ? startDate : undefined,
    dateMode === 'range' ? endDate : undefined
  )
  const { data: pred, loading: predLoading, error: predError } = useGamePrediction(selectedId)

  const matches = matchData?.matches ?? []
  const selectedMatch = matches.find(m => m.game_id === selectedId) ?? null

  // SHAP factors: flatten per model
  const shapModels = pred ? Object.keys(pred.explanation ?? {}) : []
  const [activeShapModel, setActiveShapModel] = useState<string>('xgboost')

  const shapFactors: ShapFactor[] = pred?.explanation?.[activeShapModel] ?? pred?.explanation?.[shapModels[0]] ?? []
  const maxAbsShap = shapFactors.length
    ? Math.max(...shapFactors.map(f => Math.abs(f.shap_value)))
    : 1

  const predModels = pred ? Object.keys(pred.predictions ?? {}) : []

  function saveCurrentView() {
    if (!pred) return

    const ensemble = pred.predictions?.ensemble ?? Object.values(pred.predictions ?? {})[0]
    const homeProb = ensemble?.home_win_prob
    const awayProb = ensemble?.away_win_prob
    const winnerTeam = (homeProb ?? 0) >= (awayProb ?? 0) ? pred.home_team : pred.away_team
    const winnerProb = (homeProb ?? 0) >= (awayProb ?? 0) ? homeProb : awayProb

    const state: DashboardCreateRouteState = {
      template: {
        source: 'arena/match-deep-dive',
        route: '/arena/deep-dive',
        title: `${pred.home_team} vs ${pred.away_team}`,
        note: `Created from Match Deep Dive (${season})${teamSearch ? ` · team search: ${teamSearch}` : ''}.`,
        tags: [pred.home_team, pred.away_team, season],
        stats: [
          { label: 'Season', value: season },
          { label: 'Predicted Winner', value: winnerTeam },
          { label: 'Win Prob', value: winnerProb != null ? `${(winnerProb * 100).toFixed(1)}%` : '—' },
          { label: 'Date', value: selectedMatch ? fmtDate(selectedMatch.game_date) : '—' },
        ],
        builderDefaults: {
          season,
          tableName: 'team_game_stats',
          chartType: 'line',
          dimensionField: 'game_date',
          metrics: [{ field: 'plus_minus', aggregate: 'avg' }],
          filters: [],
        },
      },
    }
    navigate('/dashboard/create', { state })
  }

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
            onChange={e => { setSeason(e.target.value); setSelectedId(null) }}
            style={{ width: '100%', marginBottom: 12 }}
          >
            {SEASONS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>

          <p style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-2)', marginBottom: 8 }}>Search Team</p>
          <div style={{ position: 'relative', marginBottom: 12 }}>
            <input
              type="text"
              placeholder="Team name or city..."
              value={teamSearch}
              onChange={e => setTeamSearch(e.target.value)}
              className="scribble-input"
              style={{ width: '100%', paddingLeft: 30, fontSize: '0.8rem' }}
            />
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', opacity: 0.5 }}>
              <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </div>

          <p style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-2)', marginBottom: 8 }}>Date Filter</p>
          <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
            {(['all', 'exact', 'range'] as const).map(m => (
              <button
                key={m}
                onClick={() => setDateMode(m)}
                style={{
                  flex: 1, padding: '4px 0', fontSize: '0.65rem', fontWeight: 700,
                  borderRadius: 4, cursor: 'pointer',
                  background: dateMode === m ? `${ACCENT}20` : 'transparent',
                  border: `1px solid ${dateMode === m ? ACCENT : 'var(--border)'}`,
                  color: dateMode === m ? ACCENT : 'var(--text-3)',
                  textTransform: 'capitalize'
                }}
              >
                {m}
              </button>
            ))}
          </div>

          {dateMode === 'exact' && (
            <input
              type="date"
              className="scribble-input"
              value={exactDate}
              onChange={e => setExactDate(e.target.value)}
              style={{ width: '100%', fontSize: '0.8rem' }}
            />
          )}

          {dateMode === 'range' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <input
                type="date"
                className="scribble-input"
                value={startDate}
                onChange={e => setStartDate(e.target.value)}
                style={{ width: '100%', fontSize: '0.8rem' }}
              />
              <input
                type="date"
                className="scribble-input"
                value={endDate}
                onChange={e => setEndDate(e.target.value)}
                style={{ width: '100%', fontSize: '0.8rem' }}
              />
            </div>
          )}
        </div>

        <div style={{ padding: '10px 14px 6px', borderBottom: '1px solid var(--border)' }}>
          <p style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-2)' }}>
            Games {!matchLoading && `(${matches.length})`}
          </p>
        </div>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          {matchLoading && (
            <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[...Array(8)].map((_, i) => <div key={i} style={{ height: 44, borderRadius: 6 }} className="skeleton-row" />)}
            </div>
          )}
          {!matchLoading && matches.length === 0 && (
            <p style={{ padding: '16px 14px', fontSize: '0.8rem', color: 'var(--text-3)' }}>No games for {season}.</p>
          )}
          {!matchLoading && matches.map(m => (
            <GameRow
              key={m.game_id}
              match={m}
              isSelected={selectedId === m.game_id}
              onClick={() => { setSelectedId(m.game_id); setActiveShapModel('xgboost') }}
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
                <circle cx="10" cy="10" r="7.5" stroke="currentColor" strokeWidth="1.4" />
                <path d="M16 16L20 20" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
              </svg>
            </div>
            <p style={{ fontWeight: 700, color: 'var(--text-1)', fontSize: '1rem' }}>Select a game</p>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-2)', maxWidth: 300 }}>
              Pick any game from the sidebar to see model predictions, SHAP factor breakdown, and feature snapshot.
            </p>
          </div>
        )}

        {selectedId && predLoading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-2)', fontSize: '0.85rem' }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ animation: 'spin 1s linear infinite' }}>
              <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="28" strokeDashoffset="10" />
            </svg>
            Loading game data…
          </div>
        )}

        {selectedId && predError && (
          <div style={{ padding: '16px 20px', background: 'rgba(255,76,106,0.07)', border: '1px solid rgba(255,76,106,0.2)', borderRadius: 'var(--r-md)' }}>
            <p style={{ color: 'var(--error)', fontSize: '0.85rem' }}>{predError} — this game may not have model predictions yet.</p>
          </div>
        )}

        {selectedId && pred && !predLoading && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
            {/* Matchup header */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 4 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 900, fontSize: '1.4rem', color: 'var(--text-1)', letterSpacing: '0.04em' }}>
                    {pred.home_team}
                  </span>
                  <span style={{ color: 'var(--text-3)', fontSize: '0.85rem' }}>vs</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 900, fontSize: '1.4rem', color: 'var(--text-1)', letterSpacing: '0.04em' }}>
                    {pred.away_team}
                  </span>
                </div>
                <button
                  onClick={saveCurrentView}
                  style={{
                    padding: '6px 12px',
                    borderRadius: 'var(--r-sm)',
                    border: `1px solid ${ACCENT}`,
                    background: `${ACCENT}12`,
                    color: ACCENT,
                    fontSize: '0.74rem',
                    fontWeight: 700,
                    fontFamily: 'var(--font-mono)',
                    cursor: 'pointer',
                  }}
                >
                  Create Dashboard
                </button>
              </div>
              <p style={{ fontSize: '0.72rem', fontFamily: 'var(--font-mono)', color: 'var(--text-3)' }}>{pred.game_id}</p>
            </div>

            {/* ── Model predictions ── */}
            <p className="section-label" style={{ color: ACCENT, marginBottom: 12 }}>Win Probabilities by Model</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 10, marginBottom: 28 }}>
              {predModels.map(modelKey => {
                const p = pred.predictions[modelKey] as ModelPrediction
                const isHome = p.home_win_prob >= 0.5
                return (
                  <div key={modelKey} style={{
                    background: 'var(--bg-panel)', border: '1px solid var(--border)',
                    borderRadius: 'var(--r-md)', padding: '14px 16px',
                  }}>
                    <p style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-2)', marginBottom: 8 }}>
                      {MODEL_LABELS[modelKey] ?? modelKey}
                    </p>
                    <p style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '1.1rem', color: ACCENT, marginBottom: 2 }}>
                      {isHome ? pred.home_team : pred.away_team}
                    </p>
                    <p style={{ fontSize: '0.78rem', color: 'var(--text-2)', marginBottom: 8 }}>
                      {((isHome ? p.home_win_prob : p.away_win_prob) * 100).toFixed(1)}% win prob
                    </p>
                    <div style={{ height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ width: `${p.home_win_prob * 100}%`, height: '100%', background: ACCENT }} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 3, fontSize: '0.65rem', fontFamily: 'var(--font-mono)', color: 'var(--text-3)' }}>
                      <span>{(p.home_win_prob * 100).toFixed(0)}%</span>
                      <span>{(p.away_win_prob * 100).toFixed(0)}%</span>
                    </div>
                    <p style={{ fontSize: '0.68rem', color: 'var(--text-3)', marginTop: 6 }}>
                      Conf: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>{(p.confidence * 100).toFixed(1)}%</span>
                    </p>
                  </div>
                )
              })}
            </div>

            {/* ── SHAP explanation ── */}
            {shapModels.length > 0 && (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
                  <p className="section-label" style={{ color: ACCENT, margin: 0 }}>SHAP Feature Importance</p>
                  <div style={{ display: 'flex', gap: 4 }}>
                    {shapModels.map(m => (
                      <button
                        key={m}
                        onClick={() => setActiveShapModel(m)}
                        style={{
                          padding: '3px 10px', borderRadius: 20, cursor: 'pointer',
                          background: activeShapModel === m ? `${ACCENT}15` : 'transparent',
                          border: `1px solid ${activeShapModel === m ? ACCENT : 'var(--border)'}`,
                          color: activeShapModel === m ? ACCENT : 'var(--text-2)',
                          fontSize: '0.72rem', fontWeight: 600,
                        }}
                      >
                        {MODEL_LABELS[m] ?? m}
                      </button>
                    ))}
                  </div>
                </div>

                <div style={{
                  background: 'var(--bg-panel)', border: '1px solid var(--border)',
                  borderRadius: 'var(--r-md)', overflow: 'hidden', marginBottom: 20,
                }}>
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 520 }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border)' }}>
                          {['Feature', 'SHAP Value', 'Direction', 'Magnitude'].map(h => (
                            <th key={h} style={{ padding: '9px 14px', textAlign: 'left', fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-2)', whiteSpace: 'nowrap' }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {shapFactors.slice(0, 12).map((f, i) => {
                          const isPos = f.shap_value >= 0
                          return (
                            <tr key={i} style={{ borderBottom: i < shapFactors.length - 1 ? '1px solid var(--border)' : 'none' }}>
                              <td style={{ padding: '9px 14px', fontSize: '0.8rem', fontFamily: 'var(--font-mono)', color: 'var(--text-1)' }}>
                                {f.display_name ?? f.feature}
                              </td>
                              <td style={{ padding: '9px 14px', fontSize: '0.8rem', fontFamily: 'var(--font-mono)', color: isPos ? ACCENT : 'var(--error)', fontWeight: 700 }}>
                                {isPos ? '+' : ''}{f.shap_value.toFixed(4)}
                              </td>
                              <td style={{ padding: '9px 14px' }}>
                                <span style={{
                                  padding: '2px 7px', borderRadius: 20,
                                  background: isPos ? `${ACCENT}15` : 'rgba(255,76,106,0.10)',
                                  color: isPos ? ACCENT : 'var(--error)',
                                  fontSize: '0.68rem', fontWeight: 700,
                                }}>
                                  {isPos ? '↑ Favours home' : '↓ Favours away'}
                                </span>
                              </td>
                              <td style={{ padding: '9px 14px', minWidth: 160 }}>
                                <ShapBar value={f.shap_value} maxAbs={maxAbsShap} />
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 16, fontSize: '0.72rem', color: 'var(--text-3)', marginBottom: 24 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <span style={{ display: 'inline-block', width: 10, height: 4, borderRadius: 1, background: ACCENT }} /> Positive = home advantage
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <span style={{ display: 'inline-block', width: 10, height: 4, borderRadius: 1, background: 'var(--error)' }} /> Negative = away advantage
                  </span>
                </div>
              </>
            )}

            {shapModels.length === 0 && (
              <div style={{
                padding: '16px 20px', background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                borderRadius: 'var(--r-md)', marginBottom: 24,
              }}>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-2)' }}>
                  No SHAP explanation available for this game. Models may not have been run with SHAP enabled.
                </p>
              </div>
            )}
          </motion.div>
        )}
      </div>
    </div>
  )
}
