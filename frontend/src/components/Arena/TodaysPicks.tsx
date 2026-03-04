import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useTodaysPredictions } from '../../hooks/useApi'
import type { DashboardCreateRouteState, ModelPrediction, TodayGamePrediction } from '../../types'

const ACCENT = '#0E8ED8'

const MODEL_ORDER  = ['ensemble', 'xgboost', 'lgbm', 'logistic_regression']
const MODEL_LABELS: Record<string, string> = {
  ensemble:            'Ensemble',
  xgboost:             'XGBoost',
  lgbm:                'LightGBM',
  logistic_regression: 'Logistic',
}
const MODEL_COLORS: Record<string, string> = {
  ensemble:            '#06C5F8',
  xgboost:             '#8B5CF6',
  lgbm:                '#10B981',
  logistic_regression: '#FFB100',
}

function ProbBar({ homeProb, color = ACCENT }: { homeProb: number; color?: string }) {
  const pct = homeProb * 100
  return (
    <div style={{ width: '100%' }}>
      <div style={{ height: 5, background: 'var(--border)', borderRadius: 3, overflow: 'hidden', display: 'flex' }}>
        <div style={{ width: `${pct}%`, background: color, borderRadius: '3px 0 0 3px', transition: 'width 0.5s ease' }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 3 }}>
        <span style={{ fontSize: '0.65rem', fontFamily: 'var(--font-mono)', color: homeProb >= 0.5 ? color : 'var(--text-3)', fontWeight: homeProb >= 0.5 ? 700 : 400 }}>
          {pct.toFixed(0)}%
        </span>
        <span style={{ fontSize: '0.65rem', fontFamily: 'var(--font-mono)', color: homeProb < 0.5 ? color : 'var(--text-3)', fontWeight: homeProb < 0.5 ? 700 : 400 }}>
          {(100 - pct).toFixed(0)}%
        </span>
      </div>
    </div>
  )
}

function GameCard({
  game,
  index,
  onSave,
}: {
  game: TodayGamePrediction
  index: number
  onSave: (game: TodayGamePrediction) => void
}) {
  const preds = game.predictions ?? {}
  const models = MODEL_ORDER.filter(m => m in preds)

  const ensemble = preds.ensemble as ModelPrediction | undefined
  const bestPick = ensemble
    ? ensemble.home_win_prob >= 0.5
      ? { team: game.home_team, prob: ensemble.home_win_prob }
      : { team: game.away_team, prob: ensemble.away_win_prob }
    : null

  const confidence = ensemble?.confidence
  const confColor = confidence == null ? 'var(--text-3)' :
    confidence >= 0.65 ? 'var(--success)' :
    confidence >= 0.55 ? 'var(--warning)' : 'var(--error)'

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: index * 0.06 }}
      style={{
        background: 'var(--bg-panel)', border: '1px solid var(--border)',
        borderRadius: 'var(--r-md)', overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div style={{
        padding: '14px 20px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '1.05rem', color: 'var(--text-1)', letterSpacing: '0.04em' }}>
            {game.home_team}
          </span>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>vs</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '1.05rem', color: 'var(--text-1)', letterSpacing: '0.04em' }}>
            {game.away_team}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onSave(game)
            }}
            style={{
              padding: '3px 9px',
              borderRadius: 20,
              border: '1px solid var(--border)',
              background: 'var(--bg-elevated)',
              color: 'var(--text-2)',
              fontSize: '0.68rem',
              fontWeight: 700,
              fontFamily: 'var(--font-mono)',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            Create Dashboard
          </button>
          {bestPick && (
            <span style={{
              padding: '3px 10px', borderRadius: 20,
              background: `${ACCENT}15`, color: ACCENT,
              fontSize: '0.7rem', fontWeight: 700, fontFamily: 'var(--font-mono)',
              letterSpacing: '0.04em', whiteSpace: 'nowrap',
            }}>
              ★ {bestPick.team}
            </span>
          )}
          {confidence != null && (
            <span style={{
              padding: '3px 9px', borderRadius: 20,
              background: 'var(--bg-elevated)', color: confColor,
              fontSize: '0.7rem', fontWeight: 700, fontFamily: 'var(--font-mono)',
            }}>
              {(confidence * 100).toFixed(1)}% conf
            </span>
          )}
        </div>
      </div>

      {/* Label row */}
      <div style={{ padding: '10px 20px 4px', display: 'flex', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Home</span>
        <span style={{ fontSize: '0.68rem', color: 'var(--text-3)' }}>Win probability by model</span>
        <span style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Away</span>
      </div>

      {/* Per-model bars */}
      <div style={{ padding: '6px 20px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {models.length === 0 && (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-3)', textAlign: 'center', padding: '8px 0' }}>No predictions available</p>
        )}
        {models.map(modelKey => {
          const pred = preds[modelKey] as ModelPrediction
          const color = MODEL_COLORS[modelKey] ?? ACCENT
          return (
            <div key={modelKey} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{
                minWidth: 64, fontSize: '0.68rem', fontWeight: 600,
                color, fontFamily: 'var(--font-mono)', flexShrink: 0,
              }}>
                {MODEL_LABELS[modelKey] ?? modelKey}
              </span>
              <div style={{ flex: 1 }}>
                <ProbBar homeProb={pred.home_win_prob} color={color} />
              </div>
            </div>
          )
        })}
      </div>

      <div style={{ padding: '8px 20px', borderTop: '1px solid var(--border)', background: 'var(--bg-elevated)' }}>
        <span style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: 'var(--text-3)' }}>{game.game_id}</span>
      </div>
    </motion.div>
  )
}

export default function TodaysPicks() {
  const navigate = useNavigate()
  const { data, loading, error, refresh } = useTodaysPredictions()

  const today = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })
  const games  = data?.games ?? []

  function saveGame(game: TodayGamePrediction) {
    const ensemble = game.predictions?.ensemble ?? Object.values(game.predictions ?? {})[0]
    const homeProb = ensemble?.home_win_prob
    const awayProb = ensemble?.away_win_prob
    const confidence = ensemble?.confidence
    const hasHomeEdge = (homeProb ?? 0) >= (awayProb ?? 0)
    const pickTeam = hasHomeEdge ? game.home_team : game.away_team
    const pickProb = hasHomeEdge ? homeProb : awayProb

    const state: DashboardCreateRouteState = {
      template: {
        source: 'arena/todays-picks',
        route: '/arena/predictions',
        title: `${game.home_team} vs ${game.away_team}`,
        note: "Created from Today's Picks for quick recall.",
        tags: [game.home_team, game.away_team, 'today'],
        stats: [
          { label: 'Pick', value: pickTeam },
          { label: 'Win Prob', value: pickProb != null ? `${(pickProb * 100).toFixed(1)}%` : '—' },
          { label: 'Confidence', value: confidence != null ? `${(confidence * 100).toFixed(1)}%` : '—' },
        ],
        builderDefaults: {
          season: '2025-26',
          tableName: 'matches',
          chartType: 'bar',
          dimensionField: 'home_team',
          metrics: [{ field: 'game_id', aggregate: 'count' }],
          filters: [],
        },
      },
    }
    navigate('/dashboard/create', { state })
  }

  return (
    <div style={{ padding: '28px 28px', maxWidth: 'var(--content-w)', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 28, flexWrap: 'wrap' }}>
        <div>
          <p style={{ fontSize: '0.72rem', color: 'var(--text-2)', marginBottom: 2 }}>Today</p>
          <p style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-1)' }}>{today}</p>
        </div>
        {loading && <span style={{ fontSize: '0.78rem', color: 'var(--text-2)', marginLeft: 16 }}>Loading predictions…</span>}
        {error && <span style={{ fontSize: '0.78rem', color: 'var(--error)', marginLeft: 16 }}>{error}</span>}
        <button
          onClick={() => refresh()}
          style={{
            marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6,
            padding: '7px 14px', background: 'var(--bg-panel)',
            border: `1px solid ${ACCENT}`, borderRadius: 'var(--r-sm)',
            color: ACCENT, fontSize: '0.78rem', fontWeight: 600, cursor: 'pointer',
          }}
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
            <path d="M10 6a4 4 0 1 1-1.07-2.72" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
            <path d="M10 2v2.5H7.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Run predictions
        </button>
      </div>

      {/* Summary pills */}
      {data && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          <span style={{ padding: '4px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 20, fontSize: '0.75rem', color: 'var(--text-2)' }}>
            {games.length} game{games.length !== 1 ? 's' : ''} today
          </span>
          {data.persisted_rows > 0 && (
            <span style={{ padding: '4px 12px', background: `${ACCENT}10`, border: `1px solid ${ACCENT}30`, borderRadius: 20, fontSize: '0.75rem', color: ACCENT, fontWeight: 600 }}>
              {data.persisted_rows} predictions saved
            </span>
          )}
        </div>
      )}

      {/* Model legend */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        {MODEL_ORDER.map(m => (
          <div key={m} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: MODEL_COLORS[m] }} />
            <span style={{ fontSize: '0.72rem', color: 'var(--text-2)' }}>{MODEL_LABELS[m]}</span>
          </div>
        ))}
      </div>

      {/* No games */}
      {!loading && !error && games.length === 0 && (
        <div style={{ textAlign: 'center', padding: '48px 0' }}>
          <p style={{ fontSize: '2rem', marginBottom: 10 }}>🏀</p>
          <p style={{ fontWeight: 700, color: 'var(--text-1)', marginBottom: 6 }}>No games scheduled today</p>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-2)' }}>Check back tomorrow or use Match Deep Dive to analyse any past game.</p>
        </div>
      )}

      {/* Skeleton */}
      {loading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 12 }}>
          {[...Array(3)].map((_, i) => (
            <div key={i} style={{ height: 200, background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)' }} className="skeleton-row" />
          ))}
        </div>
      )}

      {/* Game cards */}
      {!loading && games.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 12 }}>
          {games.map((g, i) => (
            <GameCard
              key={g.game_id}
              game={g}
              index={i}
              onSave={saveGame}
            />
          ))}
        </div>
      )}
    </div>
  )
}
