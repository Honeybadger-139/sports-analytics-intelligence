import { useState } from 'react'
import { motion } from 'framer-motion'
import { useTableList, useTableRows } from '../../hooks/useScribble'
import DataTable from './DataTable'
import type { RawTableMeta } from '../../types'

const SEASONS = ['2025-26', '2024-25', '2023-24']
const PAGE_SIZES = [25, 50, 100]
const ACCENT = '#10B981'

export default function TableBrowser() {
  const [season, setSeason] = useState('2025-26')
  const [selected, setSelected] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const [limit, setLimit] = useState(50)

  const { data: tableList, loading: listLoading } = useTableList(season)
  const { data: tableRows, loading: rowsLoading } = useTableRows(selected, season, limit, offset)

  function selectTable(table: string) {
    setSelected(table)
    setOffset(0)
  }

  const columns = tableRows?.rows.length ? Object.keys(tableRows.rows[0]) : []

  return (
    <div className="explorer-layout">
      {/* Sidebar — table list */}
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

        <p className="scribble-label" style={{ marginTop: 16 }}>Tables</p>

        {listLoading ? (
          <div className="explorer-table-loading">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="skeleton-row" />
            ))}
          </div>
        ) : (
          <div className="explorer-table-list">
            {(tableList?.tables ?? []).map((t: RawTableMeta) => (
              <button
                key={t.table}
                className={`explorer-table-btn ${selected === t.table ? 'active' : ''}`}
                onClick={() => selectTable(t.table)}
              >
                <div className="explorer-table-btn-top">
                  <span className="explorer-table-name">{t.label}</span>
                  <span className="explorer-row-badge">{t.row_count.toLocaleString()}</span>
                </div>
                <p className="explorer-table-desc">{t.description}</p>
                {t.season_filter_supported && (
                  <span className="explorer-season-tag">Season filter</span>
                )}
              </button>
            ))}
          </div>
        )}
      </aside>

      {/* Main — rows */}
      <div className="explorer-main">
        {!selected ? (
          <motion.div
            className="explorer-empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <div className="explorer-empty-icon">🗄️</div>
            <p className="explorer-empty-title">Select a table</p>
            <p className="explorer-empty-desc">
              Choose any of the 6 raw Postgres tables on the left to browse its rows.
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
            {/* Row view header */}
            <div className="explorer-rows-header">
              <div>
                <h2 className="explorer-rows-title">{tableRows?.table ?? selected}</h2>
                <p className="explorer-rows-meta">
                  {tableRows ? `${tableRows.total.toLocaleString()} total rows · Season ${tableRows.season ?? 'all'}` : 'Loading…'}
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
