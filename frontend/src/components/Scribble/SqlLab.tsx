import { useState, useEffect, type KeyboardEvent } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useSqlQuery, useViews } from '../../hooks/useScribble'
import DataTable from './DataTable'
import PgCheatSheet from './PgCheatSheet'
import PgTableRef from './PgTableRef'
import CreateViewModal from './CreateViewModal'
import ViewListPanel from './ViewListPanel'
import SqlAiChat from './SqlAiChat'

const ACCENT = '#0F9D75'

const EXAMPLE_QUERIES = [
  {
    label: 'Recent matches',
    sql: `SELECT
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
    label: 'Top scorers',
    sql: `SELECT
  p.full_name           AS player_name,
  t.abbreviation        AS team,
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
    label: 'Team win rates',
    sql: `SELECT
  t.abbreviation AS team,
  t.full_name,
  COUNT(*)       AS games,
  SUM(CASE
    WHEN m.home_team_id = t.team_id AND m.home_score > m.away_score THEN 1
    WHEN m.away_team_id = t.team_id AND m.away_score > m.home_score THEN 1
    ELSE 0
  END) AS wins,
  ROUND(
    SUM(CASE
      WHEN m.home_team_id = t.team_id AND m.home_score > m.away_score THEN 1
      WHEN m.away_team_id = t.team_id AND m.away_score > m.home_score THEN 1
      ELSE 0
    END)::numeric / NULLIF(COUNT(*), 0) * 100, 1
  ) AS win_pct
FROM teams t
JOIN matches m
  ON m.home_team_id = t.team_id OR m.away_team_id = t.team_id
WHERE m.season = '2024-25'
  AND m.is_completed = TRUE
GROUP BY t.team_id, t.abbreviation, t.full_name
ORDER BY wins DESC`,
  },
  {
    label: 'Season player stats',
    sql: `SELECT
  p.full_name                                                  AS player_name,
  t.abbreviation                                               AS team,
  pss.season,
  pss.games_played,
  ROUND(pss.points::numeric    / NULLIF(pss.games_played, 0), 1) AS pts_per_game,
  ROUND(pss.assists::numeric   / NULLIF(pss.games_played, 0), 1) AS ast_per_game,
  ROUND(pss.rebounds::numeric  / NULLIF(pss.games_played, 0), 1) AS reb_per_game,
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

interface SqlLabProps {
  /** Called when user wants to save the current query as a notebook */
  onSaveRequest: (sql: string) => void
}

export default function SqlLab({ onSaveRequest }: SqlLabProps) {
  const [sql, setSql] = useState(() => {
    const preloaded = sessionStorage.getItem('scribble_load_sql')
    if (preloaded) { sessionStorage.removeItem('scribble_load_sql'); return preloaded }
    return EXAMPLE_QUERIES[0].sql
  })
  const [cheatSheetOpen, setCheatSheetOpen] = useState(false)
  const [tableRefOpen, setTableRefOpen] = useState(false)
  const [createViewOpen, setCreateViewOpen] = useState(false)
  const [viewListOpen, setViewListOpen] = useState(false)
  const [aiChatOpen, setAiChatOpen] = useState(false)
  const { result, loading, error, run, clear } = useSqlQuery()
  const { create: createView, refresh: refreshViews } = useViews()

  useEffect(() => {
    function onLoad(e: Event) {
      const detail = (e as CustomEvent<string>).detail
      if (detail) { setSql(detail); clear() }
    }
    window.addEventListener('scribble:load-sql', onLoad)
    return () => window.removeEventListener('scribble:load-sql', onLoad)
  }, [clear])

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      run(sql)
    }
    // Tab → 2 spaces
    if (e.key === 'Tab') {
      e.preventDefault()
      const el = e.currentTarget
      const start = el.selectionStart
      const end = el.selectionEnd
      const next = sql.substring(0, start) + '  ' + sql.substring(end)
      setSql(next)
      requestAnimationFrame(() => {
        el.selectionStart = el.selectionEnd = start + 2
      })
    }
  }

  function loadExample(q: (typeof EXAMPLE_QUERIES)[0]) {
    setSql(q.sql)
    clear()
  }

  return (
    <>
      <PgCheatSheet open={cheatSheetOpen} onClose={() => setCheatSheetOpen(false)} />
      <PgTableRef open={tableRefOpen} onClose={() => setTableRefOpen(false)} />
      {createViewOpen && (
        <CreateViewModal
          initialSql={sql}
          onConfirm={async (payload) => { await createView(payload); await refreshViews() }}
          onClose={() => setCreateViewOpen(false)}
        />
      )}
      <ViewListPanel open={viewListOpen} onClose={() => setViewListOpen(false)} />
      <SqlAiChat
        open={aiChatOpen}
        onClose={() => setAiChatOpen(false)}
        onLoadSql={(sql) => { setSql(sql); clear(); setAiChatOpen(false) }}
      />

      <div className="sql-lab-layout">
        {/* Editor pane */}
        <div className="sql-editor-pane">

          {/* ── Row 1: title + example queries + save + run ── */}
          <div className="sql-editor-header">
            <span className="sql-editor-title">PostgreSQL Editor</span>

            <div className="sql-editor-actions">
              <div className="sql-example-group">
                {EXAMPLE_QUERIES.map(q => (
                  <button
                    key={q.label}
                    className="sql-example-btn"
                    onClick={() => loadExample(q)}
                  >
                    {q.label}
                  </button>
                ))}
              </div>
              <button
                className="sql-save-btn"
                onClick={() => onSaveRequest(sql)}
                title="Save as notebook"
              >
                <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                  <rect x="1" y="1" width="11" height="11" rx="2" stroke="currentColor" strokeWidth="1.2" />
                  <path d="M4 1v3.5a.5.5 0 00.5.5h4a.5.5 0 00.5-.5V1" stroke="currentColor" strokeWidth="1.2" />
                  <path d="M3 8h7M3 10h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                </svg>
                Save
              </button>
              <button
                className="sql-run-btn"
                onClick={() => run(sql)}
                disabled={!sql.trim() || loading}
              >
                {loading ? (
                  <>
                    <div className="sql-run-spinner" />
                    Running…
                  </>
                ) : (
                  <>
                    <svg width="11" height="13" viewBox="0 0 11 13" fill="currentColor">
                      <path d="M1 1l9 5.5L1 12V1z" />
                    </svg>
                    Run
                    <kbd>⌘↵</kbd>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* ── Row 2: reference toolbar ── */}
          <div className="sql-ref-toolbar">
            <button
              className={`sql-ref-btn${cheatSheetOpen ? ' active' : ''}`}
              onClick={() => { setCheatSheetOpen(v => !v); setTableRefOpen(false); setViewListOpen(false) }}
              title="PostgreSQL syntax reference"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
                <circle cx="6" cy="6" r="5.25" stroke="currentColor" strokeWidth="1.2" />
                <path d="M6 8.5V7.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                <path d="M6 3.5v2.7" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
              </svg>
              PG Reference
            </button>

            <button
              className={`sql-ref-btn sql-ref-btn--tables${tableRefOpen ? ' active' : ''}`}
              onClick={() => { setTableRefOpen(v => !v); setCheatSheetOpen(false); setViewListOpen(false) }}
              title="Available tables &amp; quick-start queries"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
                <rect x="1" y="1" width="10" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.2" />
                <path d="M1 4.5h10M4.5 4.5v6.5" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
              </svg>
              Available Tables
            </button>

            <button
              className={`sql-ref-btn sql-ref-btn--viewlist${viewListOpen ? ' active' : ''}`}
              onClick={() => { setViewListOpen(v => !v); setTableRefOpen(false); setCheatSheetOpen(false) }}
              title="Browse your saved PostgreSQL views"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
                <rect x="1" y="2" width="10" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.2" />
                <path d="M1 5h10" stroke="currentColor" strokeWidth="1.1" />
                <circle cx="10" cy="1.5" r="2" fill="var(--accent-green)" />
              </svg>
              View List
            </button>

            <button
              className="sql-ref-btn sql-ref-btn--create-view"
              onClick={() => { setCreateViewOpen(true); setCheatSheetOpen(false); setTableRefOpen(false); setViewListOpen(false) }}
              title="Save current query as a PostgreSQL view"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
                <rect x="1" y="1" width="10" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.2" />
                <path d="M1 4.5h10M4.5 4.5v6.5" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
                <path d="M7.5 2v3M6 3.5h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
              </svg>
              + Create View
            </button>

            {/* AI SQL chat — visually separated on the far right */}
            <button
              className={`sql-ref-btn sql-ref-btn--ai${aiChatOpen ? ' active' : ''}`}
              onClick={() => { setAiChatOpen(v => !v); setCheatSheetOpen(false); setTableRefOpen(false); setViewListOpen(false) }}
              title="AI SQL Assistant — describe what you need in plain English"
            >
              <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden>
                <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.2" />
                <path d="M4.5 6.5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5c0 1-.6 1.87-1.5 2.26V10h-2V8.76A2.5 2.5 0 014.5 6.5z" stroke="currentColor" strokeWidth="1.1" strokeLinejoin="round" fill="none" />
                <circle cx="7" cy="11.5" r=".7" fill="currentColor" />
              </svg>
              AI Help
            </button>
          </div>

          <div className="sql-editor-body">
            <div className="sql-line-nums" aria-hidden>
              {sql.split('\n').map((_, i) => (
                <span key={i}>{i + 1}</span>
              ))}
            </div>
            <textarea
              className="sql-textarea"
              value={sql}
              onChange={e => { setSql(e.target.value); clear() }}
              onKeyDown={handleKeyDown}
              spellCheck={false}
              placeholder="SELECT * FROM matches LIMIT 10"
            />
          </div>

          <div className="sql-editor-footer">
            <span className="sql-hint">
              <kbd>⌘</kbd><kbd>↵</kbd> run &nbsp;·&nbsp; <kbd>Tab</kbd> indent &nbsp;·&nbsp; max 500 rows returned
            </span>
            {result && (
              <span className="sql-elapsed">
                {result.elapsed_ms.toFixed(1)} ms · {result.row_count} rows
              </span>
            )}
          </div>
        </div>

        {/* Results pane */}
        <div className="sql-results-pane">
          <AnimatePresence mode="wait">
            {error && (
              <motion.div
                key="error"
                className="sql-error-box"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.3" />
                  <path d="M7 4v3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                  <circle cx="7" cy="10" r="0.7" fill="currentColor" />
                </svg>
                <pre className="sql-error-text">{error}</pre>
              </motion.div>
            )}

            {!error && result && (
              <motion.div
                key="results"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="sql-results-inner"
              >
                <div className="sql-results-header">
                  <span className="sql-results-title">Results</span>
                  <span className="sql-results-meta" style={{ color: ACCENT }}>
                    {result.row_count} rows · {result.elapsed_ms.toFixed(1)} ms
                  </span>
                </div>
                <DataTable
                  columns={result.columns}
                  rows={result.rows}
                  loading={loading}
                  accent={ACCENT}
                />
              </motion.div>
            )}

            {!error && !result && !loading && (
              <motion.div
                key="idle"
                className="sql-idle"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                <div className="sql-idle-icon">▶</div>
                <p>Run a query to see results here</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </>
  )
}
