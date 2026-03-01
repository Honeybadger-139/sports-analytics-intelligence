import { useState, useEffect, type KeyboardEvent } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useSqlQuery } from '../../hooks/useScribble'
import DataTable from './DataTable'

const ACCENT = '#10B981'

const EXAMPLE_QUERIES = [
  {
    label: 'Recent matches',
    sql: 'SELECT game_id, game_date, home_team, away_team, home_score, away_score\nFROM matches\nORDER BY game_date DESC\nLIMIT 20',
  },
  {
    label: 'Top scorers',
    sql: 'SELECT player_name, team_abbreviation, pts, ast, reb\nFROM player_game_stats\nORDER BY pts DESC\nLIMIT 25',
  },
  {
    label: 'Team win rates',
    sql: `SELECT
  t.abbreviation AS team,
  COUNT(*) AS games,
  SUM(CASE WHEN m.home_team_id = t.team_id AND m.home_score > m.away_score THEN 1
           WHEN m.away_team_id = t.team_id AND m.away_score > m.home_score THEN 1
           ELSE 0 END) AS wins
FROM teams t
JOIN matches m ON m.home_team_id = t.team_id OR m.away_team_id = t.team_id
WHERE m.season = '2025-26'
GROUP BY t.team_id, t.abbreviation
ORDER BY wins DESC`,
  },
  {
    label: 'Season player stats',
    sql: 'SELECT player_name, team_abbreviation, season, pts_per_game, ast_per_game, reb_per_game\nFROM player_season_stats\nWHERE season = \'2025-26\'\nORDER BY pts_per_game DESC\nLIMIT 30',
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
  const { result, loading, error, run, clear } = useSqlQuery()

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
    <div className="sql-lab-layout">
      {/* Editor pane */}
      <div className="sql-editor-pane">
        <div className="sql-editor-header">
          <span className="sql-editor-title">SQL Editor</span>
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
  )
}
