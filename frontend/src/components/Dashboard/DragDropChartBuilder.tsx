import { useEffect, useMemo, useState } from 'react'
import { useTableList, useTableRows } from '../../hooks/useScribble'
import type {
  DashboardAggregateOp,
  DashboardBuilderConfig,
  DashboardBuilderFilter,
  DashboardBuilderMetric,
  DashboardChartType,
  DashboardFilterOp,
} from '../../types'

const ACCENT = '#F97316'
const CHART_COLORS = ['#F97316', '#06C5F8', '#22D3EE', '#A78BFA', '#00D68F', '#F43F5E']

interface MetricConfig {
  id: string
  field: string
  aggregate: DashboardAggregateOp
}

interface FilterConfig {
  id: string
  field: string
  op: DashboardFilterOp
  value: string
}

interface AggregatePoint {
  key: string
  metrics: number[]
}

function uid(prefix: string): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}_${crypto.randomUUID()}`
  }
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

function parseNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value === 'string') {
    const cleaned = value.replace(/,/g, '').trim()
    if (!cleaned) return null
    const n = Number(cleaned)
    return Number.isFinite(n) ? n : null
  }
  return null
}

function metricLabel(metric: MetricConfig): string {
  return `${metric.aggregate.toUpperCase()}(${metric.field})`
}

function isRowPassingFilter(row: Record<string, unknown>, filter: DashboardBuilderFilter): boolean {
  if (!filter.field || !filter.value.trim()) return true
  const raw = row[filter.field]
  const left = raw === null || raw === undefined ? '' : String(raw)
  const right = filter.value.trim()

  if (filter.op === 'contains') {
    return left.toLowerCase().includes(right.toLowerCase())
  }
  if (filter.op === 'eq') return left === right
  if (filter.op === 'neq') return left !== right

  const lNum = parseNumber(raw)
  const rNum = parseNumber(right)
  if (lNum === null || rNum === null) return false

  if (filter.op === 'gt') return lNum > rNum
  if (filter.op === 'gte') return lNum >= rNum
  if (filter.op === 'lt') return lNum < rNum
  return lNum <= rNum
}

function computeMetric(rows: Record<string, unknown>[], metric: DashboardBuilderMetric): number {
  if (metric.aggregate === 'count') {
    return rows.reduce((total, row) => {
      const value = row[metric.field]
      return value === null || value === undefined || value === '' ? total : total + 1
    }, 0)
  }

  const nums = rows
    .map(row => parseNumber(row[metric.field]))
    .filter((n): n is number => n !== null)

  if (!nums.length) return 0
  if (metric.aggregate === 'sum') return nums.reduce((a, b) => a + b, 0)
  if (metric.aggregate === 'avg') return nums.reduce((a, b) => a + b, 0) / nums.length
  if (metric.aggregate === 'min') return Math.min(...nums)
  return Math.max(...nums)
}

function compactNumber(value: number): string {
  if (!Number.isFinite(value)) return '0'
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return value.toFixed(1)
}

function renderBarChart(points: AggregatePoint[], metrics: MetricConfig[]) {
  const width = 900
  const height = 330
  const left = 56
  const right = 20
  const top = 16
  const bottom = 56
  const plotW = width - left - right
  const plotH = height - top - bottom
  const maxVal = Math.max(1, ...points.flatMap(p => p.metrics))
  const groupWidth = points.length ? plotW / points.length : plotW

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 330 }}>
      <line x1={left} y1={top + plotH} x2={left + plotW} y2={top + plotH} stroke="var(--border)" />
      <line x1={left} y1={top} x2={left} y2={top + plotH} stroke="var(--border)" />
      {points.map((point, i) => {
        const metricW = Math.max(6, (groupWidth * 0.78) / Math.max(metrics.length, 1))
        const startX = left + i * groupWidth + (groupWidth - metricW * metrics.length) / 2
        return (
          <g key={`bar_grp_${point.key}_${i}`}>
            {point.metrics.map((value, mIdx) => {
              const h = (value / maxVal) * plotH
              const x = startX + mIdx * metricW
              const y = top + plotH - h
              return (
                <rect
                  key={`bar_${i}_${mIdx}`}
                  x={x}
                  y={y}
                  width={Math.max(4, metricW - 2)}
                  height={h}
                  rx={2}
                  fill={CHART_COLORS[mIdx % CHART_COLORS.length]}
                  opacity={0.92}
                />
              )
            })}
            <text
              x={left + i * groupWidth + groupWidth / 2}
              y={top + plotH + 16}
              textAnchor="middle"
              fontSize="10"
              fill="var(--text-3)"
              fontFamily="var(--font-mono)"
            >
              {point.key.slice(0, 12)}
            </text>
          </g>
        )
      })}
      {[0, 0.25, 0.5, 0.75, 1].map(tick => {
        const y = top + plotH - plotH * tick
        return (
          <g key={`y_tick_${tick}`}>
            <line x1={left} y1={y} x2={left + plotW} y2={y} stroke="var(--border)" strokeOpacity={0.4} />
            <text x={left - 8} y={y + 4} textAnchor="end" fontSize="10" fill="var(--text-3)" fontFamily="var(--font-mono)">
              {compactNumber(maxVal * tick)}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

function renderLineOrAreaChart(points: AggregatePoint[], metrics: MetricConfig[], area = false) {
  const width = 900
  const height = 330
  const left = 56
  const right = 20
  const top = 16
  const bottom = 56
  const plotW = width - left - right
  const plotH = height - top - bottom
  const maxVal = Math.max(1, ...points.flatMap(p => p.metrics))
  const denom = Math.max(1, points.length - 1)

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 330 }}>
      <line x1={left} y1={top + plotH} x2={left + plotW} y2={top + plotH} stroke="var(--border)" />
      <line x1={left} y1={top} x2={left} y2={top + plotH} stroke="var(--border)" />
      {metrics.map((metric, mIdx) => {
        const color = CHART_COLORS[mIdx % CHART_COLORS.length]
        const coords = points.map((point, i) => {
          const x = left + (i / denom) * plotW
          const y = top + plotH - (point.metrics[mIdx] / maxVal) * plotH
          return { x, y }
        })
        const linePath = coords.map((c, i) => `${i === 0 ? 'M' : 'L'}${c.x},${c.y}`).join(' ')
        const areaPath = `${linePath} L${left + plotW},${top + plotH} L${left},${top + plotH} Z`
        return (
          <g key={`ln_${metric.id}`}>
            {area && <path d={areaPath} fill={color} opacity={0.16} />}
            <path d={linePath} fill="none" stroke={color} strokeWidth={2.6} strokeLinecap="round" />
            {coords.map((c, i) => (
              <circle key={`pt_${metric.id}_${i}`} cx={c.x} cy={c.y} r={3.1} fill={color} />
            ))}
          </g>
        )
      })}
      {points.map((point, i) => {
        const x = left + (i / denom) * plotW
        return (
          <text
            key={`x_tick_${point.key}_${i}`}
            x={x}
            y={top + plotH + 16}
            textAnchor="middle"
            fontSize="10"
            fill="var(--text-3)"
            fontFamily="var(--font-mono)"
          >
            {point.key.slice(0, 12)}
          </text>
        )
      })}
      {[0, 0.25, 0.5, 0.75, 1].map(tick => {
        const y = top + plotH - plotH * tick
        return (
          <g key={`y_tick_ln_${tick}`}>
            <line x1={left} y1={y} x2={left + plotW} y2={y} stroke="var(--border)" strokeOpacity={0.4} />
            <text x={left - 8} y={y + 4} textAnchor="end" fontSize="10" fill="var(--text-3)" fontFamily="var(--font-mono)">
              {compactNumber(maxVal * tick)}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

function renderPieChart(points: AggregatePoint[], metric: MetricConfig | null) {
  if (!metric) return null

  const width = 900
  const height = 330
  const cx = 230
  const cy = 166
  const r = 110
  const values = points.map(p => p.metrics[0] ?? 0).map(v => (v < 0 ? 0 : v))
  const total = values.reduce((a, b) => a + b, 0)
  let angle = -Math.PI / 2

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 330 }}>
      {points.map((point, i) => {
        const value = values[i] ?? 0
        if (!total || value <= 0) return null
        const arc = (value / total) * Math.PI * 2
        const startX = cx + Math.cos(angle) * r
        const startY = cy + Math.sin(angle) * r
        angle += arc
        const endX = cx + Math.cos(angle) * r
        const endY = cy + Math.sin(angle) * r
        const large = arc > Math.PI ? 1 : 0
        const path = `M ${cx} ${cy} L ${startX} ${startY} A ${r} ${r} 0 ${large} 1 ${endX} ${endY} Z`

        return <path key={`pie_${point.key}_${i}`} d={path} fill={CHART_COLORS[i % CHART_COLORS.length]} opacity={0.9} />
      })}

      <text x={cx} y={cy} textAnchor="middle" fontFamily="var(--font-mono)" fill="var(--text-1)" fontSize="11">
        {metricLabel(metric)}
      </text>
      <text x={cx} y={cy + 16} textAnchor="middle" fontFamily="var(--font-mono)" fill="var(--text-3)" fontSize="10">
        {compactNumber(total)}
      </text>

      {points.slice(0, 10).map((point, i) => {
        const y = 42 + i * 25
        const value = values[i] ?? 0
        const pct = total ? ((value / total) * 100).toFixed(1) : '0.0'
        return (
          <g key={`pie_leg_${point.key}_${i}`}>
            <rect x={460} y={y - 9} width={12} height={12} fill={CHART_COLORS[i % CHART_COLORS.length]} rx={2} />
            <text x={478} y={y} fontSize="11" fill="var(--text-2)" fontFamily="var(--font-mono)">
              {point.key.slice(0, 24)} · {pct}%
            </text>
          </g>
        )
      })}
    </svg>
  )
}

interface DragDropChartBuilderProps {
  initialConfig?: Partial<DashboardBuilderConfig>
  onConfigChange?: (config: DashboardBuilderConfig) => void
}

const SEASONS = ['2025-26', '2024-25', '2023-24']

function withMetricIds(metrics: DashboardBuilderMetric[]): MetricConfig[] {
  return metrics.map(metric => ({ ...metric, id: uid('metric') }))
}

function withFilterIds(filters: DashboardBuilderFilter[]): FilterConfig[] {
  return filters.map(filter => ({ ...filter, id: uid('flt') }))
}

export default function DragDropChartBuilder({ initialConfig, onConfigChange }: DragDropChartBuilderProps) {
  const [season, setSeason] = useState(initialConfig?.season ?? '2025-26')
  const [tableName, setTableName] = useState<string | null>(initialConfig?.tableName ?? 'matches')
  const [chartType, setChartType] = useState<DashboardChartType>(initialConfig?.chartType ?? 'bar')
  const [dimensionField, setDimensionField] = useState(initialConfig?.dimensionField ?? '')
  const [metrics, setMetrics] = useState<MetricConfig[]>(withMetricIds(initialConfig?.metrics ?? []))
  const [filters, setFilters] = useState<FilterConfig[]>(withFilterIds(initialConfig?.filters ?? []))

  const { data: tableList, loading: tablesLoading } = useTableList(season)
  const { data: tableRows, loading: rowsLoading } = useTableRows(tableName, season, 300, 0)

  const columns = useMemo(() => {
    const firstRow = tableRows?.rows?.[0]
    return firstRow ? Object.keys(firstRow) : []
  }, [tableRows])

  const numericColumns = useMemo(() => {
    return columns.filter(col => (tableRows?.rows ?? []).some(row => parseNumber(row[col]) !== null))
  }, [columns, tableRows])

  const normalizedFilters = useMemo<DashboardBuilderFilter[]>(
    () => filters.map(filter => ({ field: filter.field, op: filter.op, value: filter.value })),
    [filters],
  )

  const normalizedMetrics = useMemo<DashboardBuilderMetric[]>(
    () => metrics.map(metric => ({ field: metric.field, aggregate: metric.aggregate })),
    [metrics],
  )

  const filteredRows = useMemo(() => {
    const rows = tableRows?.rows ?? []
    const activeFilters = normalizedFilters.filter(f => f.field && f.value.trim())
    if (!activeFilters.length) return rows
    return rows.filter(row => activeFilters.every(filter => isRowPassingFilter(row, filter)))
  }, [tableRows, normalizedFilters])

  const aggregatePoints = useMemo<AggregatePoint[]>(() => {
    if (!dimensionField || !normalizedMetrics.length) return []
    const groups = new Map<string, Record<string, unknown>[]>()
    for (const row of filteredRows) {
      const rawKey = row[dimensionField]
      const key = rawKey === null || rawKey === undefined || rawKey === '' ? '(empty)' : String(rawKey)
      const existing = groups.get(key)
      if (existing) existing.push(row)
      else groups.set(key, [row])
    }

    return Array.from(groups.entries())
      .map(([key, rows]) => ({
        key,
        metrics: normalizedMetrics.map(metric => computeMetric(rows, metric)),
      }))
      .slice(0, 30)
  }, [dimensionField, normalizedMetrics, filteredRows])

  function onDragStartField(e: React.DragEvent<HTMLButtonElement>, field: string) {
    e.dataTransfer.setData('text/plain', field)
    e.dataTransfer.effectAllowed = 'copy'
  }

  function onDropDimension(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    const field = e.dataTransfer.getData('text/plain')
    if (!field) return
    setDimensionField(field)
  }

  function onDropMetric(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    const field = e.dataTransfer.getData('text/plain')
    if (!field) return
    const defaultAgg: DashboardAggregateOp = numericColumns.includes(field) ? 'sum' : 'count'
    setMetrics(prev => [...prev, { id: uid('metric'), field, aggregate: defaultAgg }])
  }

  function removeMetric(id: string) {
    setMetrics(prev => prev.filter(metric => metric.id !== id))
  }

  function addFilter() {
    const field = columns[0] ?? ''
    setFilters(prev => [...prev, { id: uid('flt'), field, op: 'eq', value: '' }])
  }

  function updateFilter(id: string, patch: Partial<FilterConfig>) {
    setFilters(prev => prev.map(filter => (filter.id === id ? { ...filter, ...patch } : filter)))
  }

  function removeFilter(id: string) {
    setFilters(prev => prev.filter(filter => filter.id !== id))
  }

  function clearBuilder() {
    setDimensionField('')
    setMetrics([])
    setFilters([])
  }

  const chartRenderer = useMemo(() => {
    if (!aggregatePoints.length || !metrics.length) return null
    if (chartType === 'bar') return renderBarChart(aggregatePoints, metrics)
    if (chartType === 'line') return renderLineOrAreaChart(aggregatePoints, metrics, false)
    if (chartType === 'area') return renderLineOrAreaChart(aggregatePoints, metrics, true)
    return renderPieChart(
      aggregatePoints.map(point => ({ ...point, metrics: [point.metrics[0] ?? 0] })),
      metrics[0] ?? null,
    )
  }, [aggregatePoints, chartType, metrics])

  useEffect(() => {
    const tables = tableList?.tables ?? []
    if (!tables.length) return
    if (!tableName || !tables.some(table => table.table === tableName)) {
      setTableName(tables[0].table)
    }
  }, [tableList, tableName])

  useEffect(() => {
    if (!onConfigChange) return
    onConfigChange({
      season,
      tableName,
      chartType,
      dimensionField,
      metrics: normalizedMetrics,
      filters: normalizedFilters,
      filteredRowCount: filteredRows.length,
      groupedRowCount: aggregatePoints.length,
    })
  }, [
    aggregatePoints.length,
    chartType,
    dimensionField,
    filteredRows.length,
    normalizedFilters,
    normalizedMetrics,
    onConfigChange,
    season,
    tableName,
  ])

  const helperMessage = !dimensionField
    ? 'Drag a field to the X-Axis drop zone.'
    : !metrics.length
      ? 'Drag one or more fields to the Metrics drop zone and select aggregates.'
      : aggregatePoints.length === 0
        ? 'No grouped data after applying filters.'
        : null

  return (
    <section
      style={{
        marginBottom: 24,
        border: '1px solid var(--border)',
        borderRadius: 'var(--r-md)',
        background: 'var(--bg-panel)',
        padding: '18px 18px 16px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: 14 }}>
        <div>
          <p style={{ fontSize: '0.72rem', color: ACCENT, fontWeight: 700, letterSpacing: '0.09em', textTransform: 'uppercase', marginBottom: 4 }}>
            Create Dashboard
          </p>
          <h2 style={{ fontSize: '1.06rem', fontWeight: 800, color: 'var(--text-1)', marginBottom: 6 }}>
            Drag &amp; Drop Chart Builder
          </h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-2)', maxWidth: 760 }}>
            Drag fields into X-Axis and Metrics, pick chart type, stack multiple aggregates, and add row-level filters.
          </p>
        </div>
        <button
          onClick={clearBuilder}
          style={{
            padding: '7px 12px',
            borderRadius: 'var(--r-sm)',
            border: '1px solid var(--border)',
            background: 'var(--bg-elevated)',
            color: 'var(--text-2)',
            fontSize: '0.76rem',
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          Reset Builder
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 12 }}>
        <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: 12, background: 'var(--bg-elevated)' }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: '0.66rem', color: 'var(--text-3)', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                Season
              </span>
              <select
                value={season}
                onChange={e => {
                  setSeason(e.target.value)
                  setDimensionField('')
                  setMetrics([])
                  setFilters([])
                }}
                style={{ minWidth: 110, padding: '6px 8px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-panel)', color: 'var(--text-1)' }}
              >
                {SEASONS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>

            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: '0.66rem', color: 'var(--text-3)', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                Table
              </span>
              <select
                value={tableName ?? ''}
                onChange={e => {
                  setTableName(e.target.value)
                  setDimensionField('')
                  setMetrics([])
                  setFilters([])
                }}
                style={{ minWidth: 180, padding: '6px 8px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-panel)', color: 'var(--text-1)' }}
              >
                {(tableList?.tables ?? []).map(t => (
                  <option key={t.table} value={t.table}>{t.label} ({t.table})</option>
                ))}
              </select>
            </label>

            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: '0.66rem', color: 'var(--text-3)', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                Chart Type
              </span>
              <select
                value={chartType}
                onChange={e => setChartType(e.target.value as DashboardChartType)}
                style={{ minWidth: 120, padding: '6px 8px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-panel)', color: 'var(--text-1)' }}
              >
                <option value="bar">Bar</option>
                <option value="line">Line</option>
                <option value="area">Area</option>
                <option value="pie">Pie</option>
              </select>
            </label>
          </div>

          <div
            onDragOver={e => e.preventDefault()}
            onDrop={onDropDimension}
            style={{
              border: `1px dashed ${dimensionField ? ACCENT : 'var(--border)'}`,
              borderRadius: 10,
              padding: '10px 12px',
              marginBottom: 10,
              background: dimensionField ? `${ACCENT}12` : 'var(--bg-panel)',
            }}
          >
            <p style={{ margin: 0, fontSize: '0.69rem', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>
              X-Axis (drop field)
            </p>
            <p style={{ margin: '6px 0 0', fontSize: '0.83rem', color: dimensionField ? ACCENT : 'var(--text-2)', fontFamily: 'var(--font-mono)' }}>
              {dimensionField || 'Drop any field here'}
            </p>
          </div>

          <div
            onDragOver={e => e.preventDefault()}
            onDrop={onDropMetric}
            style={{
              border: `1px dashed ${metrics.length ? ACCENT : 'var(--border)'}`,
              borderRadius: 10,
              padding: '10px 12px',
              marginBottom: 10,
              background: metrics.length ? `${ACCENT}10` : 'var(--bg-panel)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center', marginBottom: 8 }}>
              <p style={{ margin: 0, fontSize: '0.69rem', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>
                Metrics + Aggregates (drop field)
              </p>
            </div>

            {!metrics.length && (
              <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-2)' }}>Drop one or more fields here.</p>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {metrics.map((metric, idx) => (
                <div key={metric.id} style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.9fr auto', gap: 6 }}>
                  <select
                    value={metric.field}
                    onChange={e => {
                      const field = e.target.value
                      const defaultAgg: DashboardAggregateOp = numericColumns.includes(field) ? 'sum' : 'count'
                      setMetrics(prev => prev.map(m => (m.id === metric.id ? { ...m, field, aggregate: defaultAgg } : m)))
                    }}
                    style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-panel)', color: 'var(--text-1)' }}
                  >
                    {columns.map(col => <option key={`metric_col_${metric.id}_${col}`} value={col}>{col}</option>)}
                  </select>
                  <select
                    value={metric.aggregate}
                    onChange={e => setMetrics(prev => prev.map(m => (m.id === metric.id ? { ...m, aggregate: e.target.value as DashboardAggregateOp } : m)))}
                    style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-panel)', color: 'var(--text-1)' }}
                  >
                    {(['sum', 'avg', 'min', 'max', 'count'] as DashboardAggregateOp[]).map(op => (
                      <option key={`agg_${op}`} value={op}>{op.toUpperCase()}</option>
                    ))}
                  </select>
                  <button
                    onClick={() => removeMetric(metric.id)}
                    style={{
                      border: '1px solid rgba(255,76,106,0.35)',
                      background: 'rgba(255,76,106,0.09)',
                      color: 'var(--error)',
                      borderRadius: 8,
                      padding: '6px 10px',
                      cursor: 'pointer',
                      fontWeight: 700,
                    }}
                  >
                    Remove
                  </button>
                  <span style={{ fontSize: '0.69rem', color: CHART_COLORS[idx % CHART_COLORS.length], fontFamily: 'var(--font-mono)' }}>
                    {metricLabel(metric)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div style={{ border: '1px solid var(--border)', borderRadius: 10, padding: '10px 12px', background: 'var(--bg-panel)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <p style={{ margin: 0, fontSize: '0.69rem', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>
                Filters
              </p>
              <button
                onClick={addFilter}
                disabled={!columns.length}
                style={{
                  border: '1px solid var(--border)',
                  background: 'var(--bg-elevated)',
                  color: 'var(--text-2)',
                  borderRadius: 8,
                  padding: '4px 8px',
                  cursor: 'pointer',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                }}
              >
                + Add Filter
              </button>
            </div>

            {!filters.length && <p style={{ margin: 0, color: 'var(--text-2)', fontSize: '0.8rem' }}>No filters applied.</p>}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {filters.map(filter => (
                <div key={filter.id} style={{ display: 'grid', gridTemplateColumns: '1fr 0.8fr 1fr auto', gap: 6 }}>
                  <select
                    value={filter.field}
                    onChange={e => updateFilter(filter.id, { field: e.target.value })}
                    style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-elevated)', color: 'var(--text-1)' }}
                  >
                    {columns.map(col => <option key={`flt_col_${filter.id}_${col}`} value={col}>{col}</option>)}
                  </select>
                  <select
                    value={filter.op}
                    onChange={e => updateFilter(filter.id, { op: e.target.value as DashboardFilterOp })}
                    style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-elevated)', color: 'var(--text-1)' }}
                  >
                    <option value="eq">=</option>
                    <option value="neq">≠</option>
                    <option value="contains">contains</option>
                    <option value="gt">&gt;</option>
                    <option value="gte">≥</option>
                    <option value="lt">&lt;</option>
                    <option value="lte">≤</option>
                  </select>
                  <input
                    value={filter.value}
                    onChange={e => updateFilter(filter.id, { value: e.target.value })}
                    placeholder="Value"
                    style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-elevated)', color: 'var(--text-1)' }}
                  />
                  <button
                    onClick={() => removeFilter(filter.id)}
                    style={{
                      border: '1px solid rgba(255,76,106,0.35)',
                      background: 'rgba(255,76,106,0.09)',
                      color: 'var(--error)',
                      borderRadius: 8,
                      padding: '6px 8px',
                      cursor: 'pointer',
                      fontWeight: 700,
                    }}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: 12, background: 'var(--bg-elevated)' }}>
          <p style={{ marginTop: 0, marginBottom: 8, fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-3)' }}>
            Fields (drag from here)
          </p>
          {tablesLoading || rowsLoading ? (
            <p style={{ color: 'var(--text-2)', fontSize: '0.82rem' }}>Loading table fields…</p>
          ) : (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', maxHeight: 190, overflow: 'auto', paddingRight: 6 }}>
              {columns.map((field) => {
                const isNumeric = numericColumns.includes(field)
                return (
                  <button
                    key={`field_${field}`}
                    draggable
                    onDragStart={e => onDragStartField(e, field)}
                    style={{
                      border: `1px solid ${isNumeric ? 'rgba(34,211,238,0.4)' : 'var(--border)'}`,
                      background: isNumeric ? 'rgba(34,211,238,0.08)' : 'var(--bg-panel)',
                      color: isNumeric ? '#22D3EE' : 'var(--text-2)',
                      borderRadius: 999,
                      padding: '6px 10px',
                      fontSize: '0.72rem',
                      fontFamily: 'var(--font-mono)',
                      cursor: 'grab',
                    }}
                  >
                    {field}
                    <span style={{ marginLeft: 6, color: 'var(--text-3)' }}>{isNumeric ? '123' : 'abc'}</span>
                  </button>
                )
              })}
            </div>
          )}

          <div style={{ marginTop: 12, border: '1px solid var(--border)', borderRadius: 10, background: 'var(--bg-panel)', minHeight: 360, overflow: 'hidden' }}>
            <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-2)' }}>
                <strong style={{ color: 'var(--text-1)' }}>{aggregatePoints.length}</strong> grouped rows ·{' '}
                <strong style={{ color: 'var(--text-1)' }}>{filteredRows.length}</strong> filtered rows
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {metrics.map((metric, idx) => (
                  <span
                    key={`legend_${metric.id}`}
                    style={{
                      fontSize: '0.68rem',
                      borderRadius: 999,
                      border: '1px solid var(--border)',
                      padding: '3px 8px',
                      color: CHART_COLORS[idx % CHART_COLORS.length],
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {metricLabel(metric)}
                  </span>
                ))}
              </div>
            </div>

            {helperMessage ? (
              <div style={{ display: 'grid', placeItems: 'center', minHeight: 300, padding: 12, textAlign: 'center' }}>
                <p style={{ margin: 0, color: 'var(--text-2)', fontSize: '0.84rem' }}>{helperMessage}</p>
              </div>
            ) : (
              <div style={{ padding: '8px 10px 0' }}>{chartRenderer}</div>
            )}
          </div>

          {chartType === 'pie' && metrics.length > 1 && (
            <p style={{ marginTop: 8, marginBottom: 0, fontSize: '0.74rem', color: 'var(--text-3)' }}>
              Pie chart currently uses the first metric only. Reorder metrics by removing and re-adding.
            </p>
          )}
        </div>
      </div>
    </section>
  )
}
