import { useEffect, useRef } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

interface PgCheatSheetProps {
  open: boolean
  onClose: () => void
}

const SECTIONS = [
  {
    id: 'select',
    title: 'SELECT Basics',
    icon: '📋',
    entries: [
      {
        label: 'Basic SELECT',
        code: `SELECT col1, col2
FROM table_name
WHERE condition
ORDER BY col1 DESC
LIMIT 100;`,
      },
      {
        label: 'Distinct values',
        code: `SELECT DISTINCT t.abbreviation
FROM player_game_stats pgs
JOIN teams t ON t.team_id = pgs.team_id;`,
      },
      {
        label: 'Column aliases',
        code: `SELECT p.full_name AS player,
       pgs.points   AS pts
FROM player_game_stats pgs
JOIN players p ON p.player_id = pgs.player_id;`,
      },
      {
        label: 'Conditional (CASE)',
        code: `SELECT p.full_name,
  pgs.points,
  CASE
    WHEN pgs.points >= 30 THEN 'Elite'
    WHEN pgs.points >= 20 THEN 'Strong'
    ELSE 'Solid'
  END AS tier
FROM player_game_stats pgs
JOIN players p ON p.player_id = pgs.player_id
ORDER BY pgs.points DESC
LIMIT 20;`,
      },
    ],
  },
  {
    id: 'filter',
    title: 'Filtering & Sorting',
    icon: '🔍',
    entries: [
      {
        label: 'WHERE operators',
        code: `WHERE pgs.points > 20
  AND t.abbreviation = 'LAL'
  AND m.game_date BETWEEN '2025-01-01' AND '2025-12-31'
  AND p.full_name LIKE '%James%'
  AND pss.season IN ('2024-25', '2025-26')
  AND p.position IS NOT NULL`,
      },
      {
        label: 'NULL checks',
        code: `WHERE column IS NULL
WHERE column IS NOT NULL`,
      },
      {
        label: 'ORDER + LIMIT',
        code: `ORDER BY pgs.points DESC, pgs.assists DESC
LIMIT 25 OFFSET 50   -- page 3`,
      },
    ],
  },
  {
    id: 'joins',
    title: 'JOINs',
    icon: '🔗',
    entries: [
      {
        label: 'INNER JOIN',
        code: `SELECT p.full_name, m.game_date, pgs.points
FROM player_game_stats pgs
INNER JOIN players p ON p.player_id = pgs.player_id
INNER JOIN matches  m ON m.game_id  = pgs.game_id
LIMIT 20;`,
      },
      {
        label: 'LEFT JOIN (keep all left rows)',
        code: `SELECT t.abbreviation, m.game_date, m.home_score
FROM teams t
LEFT JOIN matches m ON m.home_team_id = t.team_id
ORDER BY m.game_date DESC
LIMIT 20;`,
      },
      {
        label: 'Self JOIN (teammates)',
        code: `SELECT a.full_name AS player_a, b.full_name AS player_b
FROM players a
JOIN players b ON a.team_id = b.team_id
WHERE a.player_id < b.player_id
LIMIT 20;`,
      },
    ],
  },
  {
    id: 'aggregates',
    title: 'GROUP BY & Aggregates',
    icon: '📊',
    entries: [
      {
        label: 'Basic aggregation',
        code: `SELECT t.abbreviation AS team,
  COUNT(*)                AS games,
  AVG(pgs.points)         AS avg_pts,
  MAX(pgs.points)         AS max_pts,
  SUM(pgs.points)         AS total_pts,
  ROUND(AVG(pgs.points),1) AS avg_pts_r
FROM player_game_stats pgs
JOIN teams t ON t.team_id = pgs.team_id
GROUP BY t.abbreviation
ORDER BY avg_pts DESC;`,
      },
      {
        label: 'HAVING (filter groups)',
        code: `SELECT t.abbreviation AS team, COUNT(*) AS games
FROM player_game_stats pgs
JOIN teams t ON t.team_id = pgs.team_id
GROUP BY t.abbreviation
HAVING COUNT(*) > 50;`,
      },
      {
        label: 'ROLLUP (subtotals)',
        code: `SELECT m.season, t.abbreviation,
       ROUND(AVG(pgs.points),1) AS avg_pts
FROM player_game_stats pgs
JOIN teams   t ON t.team_id = pgs.team_id
JOIN matches m ON m.game_id = pgs.game_id
GROUP BY ROLLUP(m.season, t.abbreviation);`,
      },
    ],
  },
  {
    id: 'window',
    title: 'Window Functions',
    icon: '🪟',
    entries: [
      {
        label: 'Syntax template',
        code: `function_name() OVER (
  PARTITION BY col   -- optional grouping
  ORDER BY col DESC  -- optional ordering
  ROWS BETWEEN ...   -- optional frame
)`,
      },
      {
        label: 'ROW_NUMBER / RANK / DENSE_RANK',
        code: `SELECT p.full_name, pgs.points,
  ROW_NUMBER() OVER (ORDER BY pgs.points DESC) AS row_num,
  RANK()       OVER (ORDER BY pgs.points DESC) AS rank,
  DENSE_RANK() OVER (ORDER BY pgs.points DESC) AS dense_rank
FROM player_game_stats pgs
JOIN players p ON p.player_id = pgs.player_id
LIMIT 20;`,
      },
      {
        label: 'Top-N per group (best game per team)',
        code: `SELECT * FROM (
  SELECT p.full_name, t.abbreviation AS team, pgs.points,
    ROW_NUMBER() OVER (
      PARTITION BY pgs.team_id
      ORDER BY pgs.points DESC
    ) AS rn
  FROM player_game_stats pgs
  JOIN players p ON p.player_id = pgs.player_id
  JOIN teams   t ON t.team_id   = pgs.team_id
) ranked
WHERE rn <= 3;`,
      },
      {
        label: 'LAG / LEAD (prev/next row)',
        code: `SELECT game_date, home_score,
  LAG(home_score)  OVER (ORDER BY game_date) AS prev_game_score,
  LEAD(home_score) OVER (ORDER BY game_date) AS next_game_score
FROM matches
WHERE home_team_id = (SELECT team_id FROM teams WHERE abbreviation = 'LAL')
ORDER BY game_date;`,
      },
      {
        label: 'Running total / 7-game rolling avg',
        code: `SELECT m.game_date, pgs.points,
  SUM(pgs.points) OVER (ORDER BY m.game_date) AS running_total,
  ROUND(AVG(pgs.points) OVER (
    ORDER BY m.game_date
    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
  ), 1) AS rolling_7g_avg
FROM player_game_stats pgs
JOIN matches m ON m.game_id = pgs.game_id
JOIN players p ON p.player_id = pgs.player_id
WHERE p.full_name = 'LeBron James'
ORDER BY m.game_date;`,
      },
      {
        label: 'NTILE (buckets/percentiles)',
        code: `SELECT p.full_name, pgs.points,
  NTILE(4) OVER (ORDER BY pgs.points DESC) AS quartile
FROM player_game_stats pgs
JOIN players p ON p.player_id = pgs.player_id
ORDER BY pgs.points DESC
LIMIT 50;`,
      },
    ],
  },
  {
    id: 'cte',
    title: 'CTEs (WITH clause)',
    icon: '🧱',
    entries: [
      {
        label: 'Basic CTE',
        code: `WITH top_scorers AS (
  SELECT player_id, AVG(points) AS avg_pts
  FROM player_game_stats
  GROUP BY player_id
  HAVING AVG(points) > 20
)
SELECT p.full_name, ROUND(ts.avg_pts::numeric, 1) AS avg_pts
FROM top_scorers ts
JOIN players p ON p.player_id = ts.player_id
ORDER BY ts.avg_pts DESC;`,
      },
      {
        label: 'Multiple CTEs',
        code: `WITH
home_wins AS (
  SELECT home_team_id AS team_id, COUNT(*) AS wins
  FROM matches
  WHERE home_score > away_score
  GROUP BY home_team_id
),
away_wins AS (
  SELECT away_team_id AS team_id, COUNT(*) AS wins
  FROM matches
  WHERE away_score > home_score
  GROUP BY away_team_id
)
SELECT t.abbreviation,
  COALESCE(h.wins,0) + COALESCE(a.wins,0) AS total_wins
FROM teams t
LEFT JOIN home_wins h ON h.team_id = t.team_id
LEFT JOIN away_wins a ON a.team_id = t.team_id
ORDER BY total_wins DESC;`,
      },
    ],
  },
  {
    id: 'functions',
    title: 'Useful Functions',
    icon: '🔧',
    entries: [
      {
        label: 'String functions',
        code: `UPPER(col)               -- 'nba' → 'NBA'
LOWER(col)               -- 'NBA' → 'nba'
LENGTH(col)              -- character count
TRIM(col)                -- remove leading/trailing spaces
SUBSTRING(col, 1, 3)     -- first 3 chars
CONCAT(first, ' ', last) -- join strings
REPLACE(col, 'old','new')
col LIKE '%James%'       -- pattern match (slow on large tables)`,
      },
      {
        label: 'Numeric functions',
        code: `ROUND(avg_pts, 2)    -- 2 decimal places
CEIL(value)          -- round up
FLOOR(value)         -- round down
ABS(value)           -- absolute value
POWER(base, exp)     -- base^exp
SQRT(value)          -- square root`,
      },
      {
        label: 'Date / time functions',
        code: `NOW()                          -- current timestamp
CURRENT_DATE                   -- today's date
game_date::date                -- cast to date
DATE_TRUNC('month', game_date) -- first of month
DATE_PART('year',  game_date)  -- extract year
DATE_PART('month', game_date)  -- extract month
AGE(game_date)                 -- interval from now
game_date + INTERVAL '7 days'  -- date arithmetic`,
      },
      {
        label: 'NULL handling',
        code: `COALESCE(col, 0)         -- first non-null value
NULLIF(col, 0)           -- return NULL if equal
col IS NULL
col IS NOT NULL`,
      },
      {
        label: 'Type casting',
        code: `col::int                 -- cast to integer
col::float               -- cast to float
col::text                -- cast to text
col::date                -- cast to date
CAST(col AS NUMERIC)     -- SQL standard cast`,
      },
    ],
  },
  {
    id: 'explain',
    title: 'Query Analysis',
    icon: '⚡',
    entries: [
      {
        label: 'EXPLAIN (query plan)',
        code: `EXPLAIN
SELECT pgs.*
FROM player_game_stats pgs
JOIN teams t ON t.team_id = pgs.team_id
WHERE t.abbreviation = 'LAL';`,
      },
      {
        label: 'EXPLAIN ANALYZE (run + timing)',
        code: `EXPLAIN (ANALYZE, BUFFERS)
SELECT p.full_name, AVG(pgs.points)
FROM player_game_stats pgs
JOIN players p ON p.player_id = pgs.player_id
GROUP BY p.full_name;`,
      },
      {
        label: 'Check table size',
        code: `SELECT
  relname AS table,
  pg_size_pretty(pg_total_relation_size(relid)) AS size
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC;`,
      },
    ],
  },
]

export default function PgCheatSheet({ open, onClose }: PgCheatSheetProps) {
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    if (open) {
      document.addEventListener('keydown', onKey)
    }
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  function handleBackdropClick(e: React.MouseEvent) {
    if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
      onClose()
    }
  }

  function copyCode(code: string) {
    navigator.clipboard.writeText(code).catch(() => {})
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
            className="pg-cheat-panel"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 320, damping: 30 }}
          >
            {/* Header */}
            <div className="pg-cheat-header">
              <div className="pg-cheat-header-left">
                <span className="pg-cheat-header-icon">🐘</span>
                <div>
                  <h2 className="pg-cheat-title">PostgreSQL Cheat Sheet</h2>
                  <p className="pg-cheat-subtitle">Quick syntax reference for this SQL Lab</p>
                </div>
              </div>
              <button className="pg-cheat-close" onClick={onClose} title="Close (Esc)">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                </svg>
              </button>
            </div>

            {/* Nav pills */}
            <div className="pg-cheat-nav">
              {SECTIONS.map(s => (
                <a key={s.id} href={`#pgcs-${s.id}`} className="pg-cheat-nav-pill">
                  {s.icon} {s.title}
                </a>
              ))}
            </div>

            {/* Scrollable content */}
            <div className="pg-cheat-body">
              {SECTIONS.map(section => (
                <section key={section.id} id={`pgcs-${section.id}`} className="pg-cheat-section">
                  <h3 className="pg-cheat-section-title">
                    <span>{section.icon}</span>
                    {section.title}
                  </h3>
                  <div className="pg-cheat-entries">
                    {section.entries.map((entry, idx) => (
                      <div key={idx} className="pg-cheat-entry">
                        <div className="pg-cheat-entry-header">
                          <span className="pg-cheat-entry-label">{entry.label}</span>
                          <button
                            className="pg-cheat-copy-btn"
                            onClick={() => copyCode(entry.code)}
                            title="Copy to clipboard"
                          >
                            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                              <rect x="4" y="4" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.1" />
                              <path d="M1 8V2a1 1 0 011-1h6" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
                            </svg>
                            Copy
                          </button>
                        </div>
                        <pre className="pg-cheat-code"><code>{entry.code}</code></pre>
                      </div>
                    ))}
                  </div>
                </section>
              ))}

              <div className="pg-cheat-footer-note">
                <span>⚡</span>
                <span>SQL Lab runs read-only <strong>SELECT</strong> queries against a live PostgreSQL instance. Max 500 rows · 10s timeout.</span>
              </div>
            </div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
