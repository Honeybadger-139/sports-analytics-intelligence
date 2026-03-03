import { useEffect, useRef } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

interface PgTableRefProps {
  open: boolean
  onClose: () => void
}

interface TableEntry {
  name: string
  rows: string
  description: string
  columns: string[]
  starterQuery: string
}

const SOURCE_TABLES: TableEntry[] = [
  {
    name: 'matches',
    rows: '906',
    description: 'Raw game schedule and completed results.',
    columns: ['game_id', 'game_date', 'season', 'home_team_id', 'away_team_id', 'home_score', 'away_score', 'winner_team_id', 'is_completed', 'venue'],
    starterQuery: `SELECT
  m.game_id,
  m.game_date,
  ht.abbreviation AS home_team,
  at.abbreviation AS away_team,
  m.home_score,
  m.away_score,
  m.season
FROM matches m
JOIN teams ht ON ht.team_id = m.home_team_id
JOIN teams at ON at.team_id = m.away_team_id
WHERE m.is_completed = TRUE
ORDER BY m.game_date DESC
LIMIT 20`,
  },
  {
    name: 'teams',
    rows: '30',
    description: 'NBA team dimension — 30 teams, rarely changes.',
    columns: ['team_id', 'abbreviation', 'full_name', 'city', 'conference', 'division'],
    starterQuery: `SELECT
  team_id,
  abbreviation,
  full_name,
  city
FROM teams
ORDER BY full_name`,
  },
  {
    name: 'players',
    rows: '674',
    description: 'Player master roster with team mapping.',
    columns: ['player_id', 'full_name', 'team_id', 'position', 'is_active'],
    starterQuery: `SELECT
  p.player_id,
  p.full_name,
  t.abbreviation AS team,
  p.position
FROM players p
JOIN teams t ON t.team_id = p.team_id
WHERE p.is_active = TRUE
ORDER BY t.abbreviation, p.full_name
LIMIT 50`,
  },
  {
    name: 'team_game_stats',
    rows: '1,812',
    description: 'Per-game team box score stats.',
    columns: ['game_id', 'team_id', 'points', 'rebounds', 'assists', 'steals', 'blocks', 'turnovers', 'field_goal_pct', 'three_point_pct', 'free_throw_pct'],
    starterQuery: `SELECT
  m.game_date,
  t.abbreviation            AS team,
  tgs.points,
  tgs.assists,
  tgs.rebounds,
  ROUND(tgs.field_goal_pct::numeric * 100, 1) AS fg_pct,
  ROUND(tgs.three_point_pct::numeric * 100, 1) AS three_pct
FROM team_game_stats tgs
JOIN teams   t ON t.team_id = tgs.team_id
JOIN matches m ON m.game_id = tgs.game_id
WHERE m.is_completed = TRUE
ORDER BY tgs.points DESC
LIMIT 25`,
  },
  {
    name: 'player_game_stats',
    rows: '19,664',
    description: 'Per-game individual player stats. Largest table.',
    columns: ['game_id', 'player_id', 'team_id', 'points', 'assists', 'rebounds', 'steals', 'blocks', 'minutes', 'field_goal_pct', 'three_point_pct', 'plus_minus'],
    starterQuery: `SELECT
  p.full_name       AS player,
  t.abbreviation    AS team,
  pgs.points,
  pgs.assists,
  pgs.rebounds,
  pgs.minutes,
  m.game_date
FROM player_game_stats pgs
JOIN players p  ON p.player_id = pgs.player_id
JOIN teams   t  ON t.team_id   = pgs.team_id
JOIN matches m  ON m.game_id   = pgs.game_id
WHERE m.is_completed = TRUE
  AND pgs.minutes::numeric > 0
ORDER BY pgs.points DESC
LIMIT 25`,
  },
  {
    name: 'player_season_stats',
    rows: '543',
    description: 'Season totals per player — divide by games_played for per-game averages.',
    columns: ['player_id', 'team_id', 'season', 'games_played', 'points', 'assists', 'rebounds', 'steals', 'blocks', 'field_goal_pct', 'three_point_pct', 'minutes'],
    starterQuery: `SELECT
  p.full_name  AS player,
  t.abbreviation AS team,
  pss.season,
  pss.games_played,
  ROUND(pss.points::numeric   / NULLIF(pss.games_played,0), 1) AS pts_per_game,
  ROUND(pss.assists::numeric  / NULLIF(pss.games_played,0), 1) AS ast_per_game,
  ROUND(pss.rebounds::numeric / NULLIF(pss.games_played,0), 1) AS reb_per_game,
  ROUND(pss.field_goal_pct::numeric * 100, 1)                  AS fg_pct
FROM player_season_stats pss
JOIN players p ON p.player_id = pss.player_id
JOIN teams   t ON t.team_id   = pss.team_id
WHERE pss.season = '2024-25'
  AND pss.games_played > 0
ORDER BY pss.points DESC
LIMIT 30`,
  },
]

const DERIVED_TABLES: TableEntry[] = [
  {
    name: 'match_features',
    rows: 'computed',
    description: 'ML-ready feature vectors — rolling win rates, point differentials, rest days, home/away flags.',
    columns: ['game_id', 'team_id', 'win_pct_last_5', 'win_pct_last_10', 'avg_point_diff_last_5', 'avg_point_diff_last_10', 'h2h_win_pct', 'days_rest', 'is_back_to_back', 'is_home'],
    starterQuery: `SELECT
  m.game_date,
  ht.abbreviation              AS home_team,
  at.abbreviation              AS away_team,
  hf.win_pct_last_10           AS home_win_pct_l10,
  af.win_pct_last_10           AS away_win_pct_l10,
  hf.avg_point_diff_last_5     AS home_pt_diff_l5,
  af.avg_point_diff_last_5     AS away_pt_diff_l5,
  hf.days_rest                 AS home_rest,
  af.days_rest                 AS away_rest
FROM matches m
JOIN match_features hf ON hf.game_id = m.game_id AND hf.is_home = TRUE
JOIN match_features af ON af.game_id = m.game_id AND af.is_home = FALSE
JOIN teams ht ON ht.team_id = m.home_team_id
JOIN teams at ON at.team_id = m.away_team_id
WHERE m.is_completed = TRUE
ORDER BY m.game_date DESC
LIMIT 20`,
  },
  {
    name: 'predictions',
    rows: 'computed',
    description: 'Model output — home/away win probabilities, confidence score and correctness flag.',
    columns: ['game_id', 'model_name', 'home_win_prob', 'away_win_prob', 'confidence', 'predicted_at', 'was_correct'],
    starterQuery: `SELECT
  m.game_date,
  ht.abbreviation                           AS home_team,
  at.abbreviation                           AS away_team,
  ROUND(pr.home_win_prob::numeric * 100, 1) AS home_win_prob_pct,
  ROUND(pr.away_win_prob::numeric * 100, 1) AS away_win_prob_pct,
  ROUND(pr.confidence::numeric * 100, 1)   AS confidence_pct,
  pr.model_name,
  pr.was_correct
FROM predictions pr
JOIN matches m  ON m.game_id   = pr.game_id
JOIN teams ht   ON ht.team_id  = m.home_team_id
JOIN teams at   ON at.team_id  = m.away_team_id
ORDER BY pr.predicted_at DESC
LIMIT 20`,
  },
  {
    name: 'bets',
    rows: 'computed',
    description: 'Bet tracker — stake, Kelly fraction, model probability, result and P&L.',
    columns: ['game_id', 'bet_type', 'selection', 'odds', 'stake', 'kelly_fraction', 'model_probability', 'result', 'pnl', 'placed_at', 'settled_at'],
    starterQuery: `SELECT
  b.game_id,
  b.selection,
  b.odds::numeric             AS odds,
  b.stake::numeric            AS stake,
  b.kelly_fraction::numeric   AS kelly_f,
  b.model_probability::numeric AS model_prob,
  b.result,
  b.pnl::numeric              AS pnl,
  b.placed_at::date           AS bet_date
FROM bets b
ORDER BY b.placed_at DESC
LIMIT 20`,
  },
]

export default function PgTableRef({ open, onClose }: PgTableRefProps) {
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    if (open) document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  function handleBackdropClick(e: React.MouseEvent) {
    if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
      onClose()
    }
  }

  function loadQuery(sql: string) {
    sessionStorage.setItem('scribble_load_sql', sql)
    window.dispatchEvent(new CustomEvent('scribble:load-sql', { detail: sql }))
    onClose()
  }

  function copyQuery(sql: string) {
    navigator.clipboard.writeText(sql).catch(() => {})
  }

  function TableCard({ t, derived = false }: { t: TableEntry; derived?: boolean }) {
    return (
      <div className={`pgtr-card${derived ? ' pgtr-card--derived' : ''}`}>
        <div className="pgtr-card-header">
          <div className="pgtr-card-meta">
            <span className="pgtr-table-name">{t.name}</span>
            <span className={`pgtr-rows-badge${derived ? ' pgtr-rows-badge--derived' : ''}`}>
              {t.rows} rows
            </span>
          </div>
          <div className="pgtr-card-actions">
            <button
              className="pgtr-action-btn"
              onClick={() => copyQuery(t.starterQuery)}
              title="Copy starter query"
            >
              <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
                <rect x="4" y="4" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.1" />
                <path d="M1 8V2a1 1 0 011-1h6" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
              </svg>
              Copy
            </button>
            <button
              className="pgtr-action-btn pgtr-action-btn--load"
              onClick={() => loadQuery(t.starterQuery)}
              title="Load into SQL Editor"
            >
              <svg width="11" height="11" viewBox="0 0 11 13" fill="currentColor">
                <path d="M1 1l9 5.5L1 12V1z" />
              </svg>
              Load
            </button>
          </div>
        </div>

        <p className="pgtr-card-desc">{t.description}</p>

        <div className="pgtr-columns">
          {t.columns.map(col => (
            <code key={col} className="pgtr-col-chip">{col}</code>
          ))}
        </div>
      </div>
    )
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="pg-cheat-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          onClick={handleBackdropClick}
        >
          <motion.aside
            ref={panelRef}
            className="pg-cheat-panel pgtr-panel"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 320, damping: 30 }}
          >
            {/* Header */}
            <div className="pg-cheat-header">
              <div className="pg-cheat-header-left">
                <span className="pg-cheat-header-icon">🗄️</span>
                <div>
                  <h2 className="pg-cheat-title">Available Tables</h2>
                  <p className="pg-cheat-subtitle">Click Load to open a query in the editor</p>
                </div>
              </div>
              <button className="pg-cheat-close" onClick={onClose} title="Close (Esc)">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                </svg>
              </button>
            </div>

            {/* Scrollable body */}
            <div className="pg-cheat-body">

              {/* Ingestion source tables */}
              <div className="pgtr-group-header">
                <span className="pgtr-group-dot pgtr-group-dot--source" />
                <span className="pgtr-group-label">Ingestion Sources</span>
                <span className="pgtr-group-count">{SOURCE_TABLES.length}</span>
              </div>
              <p className="pgtr-group-desc">Loaded directly from the NBA API pipeline. Browsable in the Explorer tab.</p>
              <div className="pgtr-cards">
                {SOURCE_TABLES.map(t => <TableCard key={t.name} t={t} />)}
              </div>

              {/* Derived tables */}
              <div className="pgtr-group-header" style={{ marginTop: 22 }}>
                <span className="pgtr-group-dot pgtr-group-dot--derived" />
                <span className="pgtr-group-label">Derived &amp; Features</span>
                <span className="pgtr-group-count">{DERIVED_TABLES.length}</span>
              </div>
              <p className="pgtr-group-desc">Computed by the ML pipeline. SQL Lab only — not in Explorer.</p>
              <div className="pgtr-cards">
                {DERIVED_TABLES.map(t => <TableCard key={t.name} t={t} derived />)}
              </div>

              <div className="pg-cheat-footer-note" style={{ marginTop: 16 }}>
                <span>💡</span>
                <span>Use <strong>Load</strong> to paste a starter query into the editor, then modify as needed.</span>
              </div>
            </div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
