import { useState } from 'react'

interface DataTableProps {
  columns: string[]
  rows: Record<string, unknown>[]
  /** Total rows on the server (for pagination display). Omit for client-side data. */
  total?: number
  /** Currently loaded page offset */
  offset?: number
  /** Page size */
  limit?: number
  onPageChange?: (newOffset: number) => void
  loading?: boolean
  accent?: string
}

function cellStr(val: unknown): string {
  if (val === null || val === undefined) return 'NULL'
  if (typeof val === 'boolean') return val ? 'true' : 'false'
  return String(val)
}

function isNull(val: unknown): boolean {
  return val === null || val === undefined
}

function isNumeric(val: unknown): boolean {
  return typeof val === 'number'
}

export default function DataTable({
  columns,
  rows,
  total,
  offset = 0,
  limit = 50,
  onPageChange,
  loading = false,
  accent = '#10B981',
}: DataTableProps) {
  const [sortCol, setSortCol] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [filter, setFilter] = useState('')

  const hasPagination = total !== undefined && onPageChange !== undefined
  const page = Math.floor(offset / limit)
  const totalPages = total !== undefined ? Math.ceil(total / limit) : 1

  function handleSort(col: string) {
    if (sortCol === col) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortCol(col)
      setSortDir('asc')
    }
  }

  const filteredRows = filter
    ? rows.filter(row =>
        columns.some(col => {
          const v = cellStr(row[col]).toLowerCase()
          return v.includes(filter.toLowerCase())
        })
      )
    : rows

  const sortedRows =
    sortCol !== null
      ? [...filteredRows].sort((a, b) => {
          const av = a[sortCol]
          const bv = b[sortCol]
          if (isNull(av) && isNull(bv)) return 0
          if (isNull(av)) return 1
          if (isNull(bv)) return -1
          const cmp =
            typeof av === 'number' && typeof bv === 'number'
              ? av - bv
              : String(av).localeCompare(String(bv))
          return sortDir === 'asc' ? cmp : -cmp
        })
      : filteredRows

  if (!columns.length) return null

  return (
    <div className="data-table-wrap">
      {/* Toolbar */}
      <div className="data-table-toolbar">
        <div className="data-table-filter">
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <circle cx="5.5" cy="5.5" r="4.5" stroke="currentColor" strokeWidth="1.3" />
            <path d="M9 9l2.5 2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
          <input
            className="data-table-filter-input"
            placeholder="Filter rows…"
            value={filter}
            onChange={e => setFilter(e.target.value)}
          />
          {filter && (
            <button className="data-table-filter-clear" onClick={() => setFilter('')}>×</button>
          )}
        </div>
        <span className="data-table-count" style={{ color: accent }}>
          {filter ? `${sortedRows.length} / ${rows.length}` : rows.length} rows
          {total !== undefined && !filter && ` of ${total.toLocaleString()} total`}
        </span>
      </div>

      {/* Table */}
      <div className="data-table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map(col => (
                <th
                  key={col}
                  className={`data-table-th ${sortCol === col ? 'sorted' : ''}`}
                  onClick={() => handleSort(col)}
                  style={{ '--col-accent': accent } as React.CSSProperties}
                >
                  <span>{col}</span>
                  <span className="sort-icon">
                    {sortCol === col ? (sortDir === 'asc' ? '↑' : '↓') : '⇅'}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={columns.length} className="data-table-loading">
                  <div className="data-table-spinner" style={{ borderTopColor: accent }} />
                  Loading…
                </td>
              </tr>
            ) : sortedRows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="data-table-empty">
                  No rows{filter ? ' matching filter' : ''}
                </td>
              </tr>
            ) : (
              sortedRows.map((row, ri) => (
                <tr key={ri} className="data-table-row">
                  {columns.map(col => {
                    const val = row[col]
                    const str = cellStr(val)
                    return (
                      <td
                        key={col}
                        className={`data-table-td ${isNull(val) ? 'null-cell' : ''} ${isNumeric(val) ? 'num-cell' : ''}`}
                        title={str}
                      >
                        {isNull(val) ? <span className="null-badge">NULL</span> : str}
                      </td>
                    )
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {hasPagination && totalPages > 1 && (
        <div className="data-table-pagination">
          <button
            className="dt-page-btn"
            disabled={page === 0}
            onClick={() => onPageChange(Math.max(0, offset - limit))}
          >
            ← Prev
          </button>
          <span className="dt-page-info">
            Page {page + 1} of {totalPages}
          </span>
          <button
            className="dt-page-btn"
            disabled={offset + limit >= (total ?? 0)}
            onClick={() => onPageChange(offset + limit)}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  )
}
