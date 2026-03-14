import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useMatches, useGamePrediction } from '../hooks/useApi'
import { useSportContext } from '../context/SportContext'
import type { ShapFactor } from '../types'

const ACCENT = '#3B82F6'
const SEASONS = ['2025-26', '2024-25', '2023-24']

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '—'
  return `${(v * 100).toFixed(1)}%`
}

function isShapFactor(value: unknown): value is ShapFactor {
  if (!value || typeof value !== 'object') return false
  const row = value as Record<string, unknown>
  return typeof row.feature === 'string' && typeof row.shap_value === 'number'
}

function normalizeExplanation(explanation: unknown): Record<string, ShapFactor[]> {
  if (!explanation || typeof explanation !== 'object') return {}
  const payload = explanation as Record<string, unknown>

  if (Array.isArray(payload.all_factors)) {
    const model = typeof payload.model_name === 'string' ? payload.model_name : 'xgboost'
    return { [model]: payload.all_factors.filter(isShapFactor) }
  }

  const byModel: Record<string, ShapFactor[]> = {}
  for (const [model, factors] of Object.entries(payload)) {
    if (!Array.isArray(factors)) continue
    const valid = factors.filter(isShapFactor)
    if (valid.length > 0) byModel[model] = valid
  }
  return byModel
}

function fmtGameLabel(home: string, away: string, isoDate: string): string {
  const date = new Date(isoDate)
  const stamp = Number.isNaN(date.getTime())
    ? isoDate
    : date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  return `${away} @ ${home} · ${stamp}`
}

function FactorBar({ value, maxAbs }: { value: number; maxAbs: number }) {
  const width = maxAbs > 0 ? Math.min(100, (Math.abs(value) / maxAbs) * 100) : 0
  const color = value >= 0 ? 'var(--success)' : 'var(--error)'
  return (
    <div style={{ background: 'var(--bg-elevated)', borderRadius: 6, overflow: 'hidden', height: 8 }}>
      <div style={{ width: `${width}%`, background: color, height: '100%' }} />
    </div>
  )
}

export default function ModelInsight() {
  const navigate = useNavigate()
  const { selection } = useSportContext()

  const [season, setSeason] = useState(SEASONS.includes(selection.season) ? selection.season : '2025-26')
  const [teamSearch, setTeamSearch] = useState('')
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null)
  const [selectedModel, setSelectedModel] = useState<string>('ensemble')

  const { data: matchesData, loading: matchesLoading } = useMatches(season, 60, teamSearch)
  const matches = matchesData?.matches ?? []

  useEffect(() => {
    if (!matches.length) {
      setSelectedGameId(null)
      return
    }
    const stillExists = selectedGameId && matches.some(match => match.game_id === selectedGameId)
    if (!stillExists) setSelectedGameId(matches[0].game_id)
  }, [matches, selectedGameId])

  const { data: prediction, loading: predLoading, error: predError } = useGamePrediction(selectedGameId)

  const modelNames = useMemo(() => Object.keys(prediction?.predictions ?? {}), [prediction?.predictions])

  useEffect(() => {
    if (!modelNames.length) return
    if (!modelNames.includes(selectedModel)) setSelectedModel(modelNames[0])
  }, [modelNames, selectedModel])

  const currentModelPrediction = prediction?.predictions?.[selectedModel]

  const explanationByModel = useMemo(
    () => normalizeExplanation(prediction?.explanation),
    [prediction?.explanation],
  )
  const factors = explanationByModel[selectedModel] ?? []
  const rankedFactors = useMemo(
    () => [...factors].sort((a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value)).slice(0, 10),
    [factors],
  )
  const maxAbs = rankedFactors.length ? Math.max(...rankedFactors.map(f => Math.abs(f.shap_value))) : 1

  return (
    <div className="page-shell">
      <div style={{ maxWidth: 'var(--content-w)', margin: '0 auto', padding: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 20 }}>
          <div>
            <p style={{ fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: ACCENT, marginBottom: 4 }}>
              Model Insight
            </p>
            <h1 style={{ fontSize: '1.35rem', margin: 0, color: 'var(--text-1)', fontFamily: 'var(--font-display)' }}>
              Interactive Prediction Factor Studio
            </h1>
            <p style={{ marginTop: 8, fontSize: '0.84rem', color: 'var(--text-2)', maxWidth: 760 }}>
              Select a game and model to explore win probabilities, confidence, and top explainability factors.
            </p>
          </div>
          <button
            onClick={() => navigate('/arena/deep-dive')}
            style={{
              padding: '8px 12px',
              borderRadius: 'var(--r-sm)',
              border: `1px solid ${ACCENT}`,
              background: `${ACCENT}16`,
              color: ACCENT,
              fontWeight: 700,
              fontSize: '0.76rem',
              cursor: 'pointer',
            }}
          >
            Open Full Deep Dive
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10, marginBottom: 18 }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-2)', fontWeight: 700 }}>Season</span>
            <select className="scribble-select" value={season} onChange={(e) => setSeason(e.target.value)}>
              {SEASONS.map(item => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-2)', fontWeight: 700 }}>Team Filter</span>
            <input
              className="scribble-input"
              value={teamSearch}
              onChange={(e) => setTeamSearch(e.target.value)}
              placeholder="e.g. LAL, BOS, Denver"
              style={{ fontSize: '0.8rem' }}
            />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-2)', fontWeight: 700 }}>Game</span>
            <select
              className="scribble-select"
              value={selectedGameId ?? ''}
              onChange={(e) => setSelectedGameId(e.target.value || null)}
              disabled={!matches.length}
            >
              {!matches.length && <option value="">No matches found</option>}
              {matches.map(match => (
                <option key={match.game_id} value={match.game_id}>
                  {fmtGameLabel(match.home_team, match.away_team, match.game_date)}
                </option>
              ))}
            </select>
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-2)', fontWeight: 700 }}>Model</span>
            <select
              className="scribble-select"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              disabled={!modelNames.length}
            >
              {!modelNames.length && <option value="">No model data</option>}
              {modelNames.map(model => <option key={model} value={model}>{model}</option>)}
            </select>
          </label>
        </div>

        {matchesLoading && (
          <p style={{ color: 'var(--text-2)', fontSize: '0.84rem', marginBottom: 14 }}>Loading games…</p>
        )}
        {predError && (
          <p style={{ color: 'var(--error)', fontSize: '0.82rem', marginBottom: 14 }}>
            {predError}
          </p>
        )}

        {prediction && !predLoading && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} style={{ display: 'grid', gap: 14 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 10 }}>
              <div style={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', padding: '14px 16px' }}>
                <p style={{ fontSize: '0.68rem', color: 'var(--text-2)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>
                  {prediction.home_team} Win Prob
                </p>
                <p style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '1.25rem', color: 'var(--success)' }}>
                  {fmtPct(currentModelPrediction?.home_win_prob)}
                </p>
              </div>
              <div style={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', padding: '14px 16px' }}>
                <p style={{ fontSize: '0.68rem', color: 'var(--text-2)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>
                  {prediction.away_team} Win Prob
                </p>
                <p style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '1.25rem', color: 'var(--error)' }}>
                  {fmtPct(currentModelPrediction?.away_win_prob)}
                </p>
              </div>
              <div style={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', padding: '14px 16px' }}>
                <p style={{ fontSize: '0.68rem', color: 'var(--text-2)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>
                  Confidence
                </p>
                <p style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '1.25rem', color: 'var(--text-1)' }}>
                  {fmtPct(currentModelPrediction?.confidence)}
                </p>
              </div>
            </div>

            <div style={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', padding: '14px 16px' }}>
              <p style={{ fontSize: '0.75rem', color: ACCENT, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>
                Top Explainability Factors ({selectedModel})
              </p>
              {!rankedFactors.length && (
                <p style={{ color: 'var(--text-2)', fontSize: '0.82rem' }}>
                  No SHAP factors available for this model/game pair.
                </p>
              )}
              {rankedFactors.length > 0 && (
                <div style={{ display: 'grid', gap: 8 }}>
                  {rankedFactors.map(factor => (
                    <div key={factor.feature} style={{ display: 'grid', gridTemplateColumns: '1.1fr 1.3fr auto', gap: 10, alignItems: 'center' }}>
                      <span style={{ color: 'var(--text-1)', fontSize: '0.78rem' }}>
                        {factor.display_name ?? factor.feature}
                      </span>
                      <FactorBar value={factor.shap_value} maxAbs={maxAbs} />
                      <span
                        style={{
                          fontSize: '0.74rem',
                          fontFamily: 'var(--font-mono)',
                          color: factor.shap_value >= 0 ? 'var(--success)' : 'var(--error)',
                          minWidth: 64,
                          textAlign: 'right',
                        }}
                      >
                        {factor.shap_value > 0 ? '+' : ''}{factor.shap_value.toFixed(3)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <p style={{ marginTop: 10, fontSize: '0.72rem', color: 'var(--text-3)' }}>
                Positive values generally push toward home-team win probability; negative values push away.
              </p>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  )
}

