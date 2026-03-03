import { useState } from 'react'
import { motion } from 'framer-motion'
import { useTableList, useTableRows } from '../../hooks/useScribble'
import DataTable from '../Scribble/DataTable'
import type { RawTableMeta } from '../../types'

const ACCENT   = '#8B5CF6'
const SEASONS  = ['2025-26', '2024-25', '2023-24']
const PAGE_SIZES = [25, 50, 100]

const DERIVED_TABLES = [
  { table: 'match_features', label: 'Match Features',    hint: 'SELECT * FROM match_features LIMIT 20', description: 'ML-ready feature vectors per game — rolling averages, win rates, home/away differentials.' },
  { table: 'predictions',    label: 'Predictions',       hint: 'SELECT * FROM predictions ORDER BY predicted_at DESC LIMIT 20', description: 'Model output — predicted winner, confidence score and model version per game.' },
  { table: 'bets',           label: 'Bets',              hint: 'SELECT * FROM bets ORDER BY placed_at DESC LIMIT 20', description: 'Bet tracker linked to predictions — tracks expected value, stake and settlement.' },
]

export default function LabRawExplorer() {
  const [season,   setSeason]   = useState('2025-26')
  const [selected, setSelected] = useState<string | null>(null)
  const [offset,   setOffset]   = useState(0)
  const [limit,    setLimit]    = useState(50)

  const { data: tableList, loading: listLoading } = useTableList(season)
  const { data: tableRows, loading: rowsLoading } = useTableRows(selected, season, limit, offset)

  function selectTable(table: string) {
    setSelected(table)
    setOffset(0)
  }

  const columns = tableRows?.rows.length ? Object.keys(tableRows.rows[0]) : []

  return (
    <div className="explorer-layout">
      {/* ── Sidebar ── */}
      <aside className="explorer-sidebar">
        <div className="explorer-sidebar-header">
          <p className="scribble-label">Season</p>
          <select
            className="scribble-select"
            value={season}
            onChange={e => { setSeason(e.target.value); setSelected(null); setOffset(0) }}
          >
            {SEASONS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        {/* Ingestion source tables */}
        <div className="explorer-section-header">
          <span className="explorer-section-dot" style={{ background: ACCENT }} />
          <span className="explorer-section-title">Ingestion Sources</span>
          <span className="explorer-section-count">
            {listLoading ? '…' : (tableList?.tables.length ?? 0)}
          </span>
        </div>
        <p className="explorer-section-desc">Live data loaded directly from the NBA API pipeline.</p>

        {listLoading ? (
          <div className="explorer-table-loading">
            {[...Array(6)].map((_, i) => <div key={i} className="skeleton-row" />)}
          </div>
        ) : (
          <div className="explorer-table-list">
            {(tableList?.tables ?? []).map((t: RawTableMeta) => (
              <button
                key={t.table}
                className={`explorer-table-btn ${selected === t.table ? 'active' : ''}`}
                onClick={() => selectTable(t.table)}
                style={selected === t.table ? { borderColor: ACCENT, background: 'rgba(139,92,246,0.07)' } : {}}
              >
                <div className="explorer-table-btn-top">
                  <span className="explorer-table-name">{t.label}</span>
                  <span className="explorer-row-badge" style={selected === t.table ? { background: 'rgba(139,92,246,0.15)', color: ACCENT } : {}}>
                    {t.row_count.toLocaleString()}
                  </span>
                </div>
                <p className="explorer-table-desc">{t.description}</p>
                {t.season_filter_supported && (
                  <span className="explorer-season-tag" style={{ borderColor: 'rgba(139,92,246,0.3)', color: ACCENT }}>Season filter</span>
                )}
              </button>
            ))}
          </div>
        )}

        {/* Derived tables */}
        <div className="explorer-section-header" style={{ marginTop: 20 }}>
          <span className="explorer-section-dot" style={{ background: 'var(--text-3)' }} />
          <span className="explorer-section-title">Derived &amp; Features</span>
          <span className="explorer-section-count">{DERIVED_TABLES.length}</span>
        </div>
        <p className="explorer-section-desc">Computed by the ML pipeline. Query via Scribble → SQL Lab.</p>

        <div className="explorer-table-list">
          {DERIVED_TABLES.map(t => (
            <div key={t.table} className="explorer-derived-card" title={`Run in SQL Lab:\n${t.hint}`}>
              <div className="explorer-table-btn-top">
                <span className="explorer-table-name">{t.label}</span>
                <span className="explorer-derived-badge">
                  <svg width="9" height="9" viewBox="0 0 9 9" fill="none" aria-hidden>
                    <path d="M1 8L8 1M8 1H3.5M8 1V5.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  SQL Lab
                </span>
              </div>
              <p className="explorer-table-desc">{t.description}</p>
              <code className="explorer-derived-hint">{t.hint}</code>
            </div>
          ))}
        </div>
      </aside>

      {/* ── Main ── */}
      <div className="explorer-main">
        {!selected ? (
          <motion.div className="explorer-empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <div className="explorer-empty-icon">🗄️</div>
            <p className="explorer-empty-title">Select a table</p>
            <p className="explorer-empty-desc">
              Pick an <strong>Ingestion Source</strong> on the left to browse its rows live.<br />
              <strong>Derived &amp; Feature</strong> tables are query-only — use the Scribble SQL Lab.
            </p>
          </motion.div>
        ) : (
          <motion.div
            key={selected}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="explorer-rows-view"
          >
            <div className="explorer-rows-header">
              <div>
                <h2 className="explorer-rows-title">{tableRows?.table ?? selected}</h2>
                <p className="explorer-rows-meta">
                  {tableRows
                    ? `${tableRows.total.toLocaleString()} total rows · Season ${tableRows.season ?? 'all'}`
                    : 'Loading…'}
                </p>
              </div>
              <div className="explorer-rows-controls">
                <label className="scribble-label" style={{ margin: 0 }}>Rows</label>
                <select
                  className="scribble-select scribble-select--sm"
                  value={limit}
                  onChange={e => { setLimit(Number(e.target.value)); setOffset(0) }}
                >
                  {PAGE_SIZES.map(n => <option key={n} value={n}>{n}</option>)}
                </select>
              </div>
            </div>

            <DataTable
              columns={columns}
              rows={tableRows?.rows ?? []}
              total={tableRows?.total}
              offset={offset}
              limit={limit}
              onPageChange={setOffset}
              loading={rowsLoading}
              accent={ACCENT}
            />
          </motion.div>
        )}
      </div>
    </div>
  )
}
