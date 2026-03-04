import { useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import DragDropChartBuilder from '../components/Dashboard/DragDropChartBuilder'
import { useDashboard } from '../hooks/useDashboard'
import type { DashboardBuilderConfig, DashboardCreateRouteState, DashboardCreateTemplate, DashboardSource } from '../types'

const ACCENT = '#F97316'

const SOURCE_LABEL: Record<DashboardSource, string> = {
  'arena/todays-picks': "Today's Picks",
  'arena/match-deep-dive': 'Match Deep Dive',
  'arena/model-performance': 'Model Performance',
  'arena/player-stats': 'Player Stats',
  'arena/team-stats': 'Team Stats',
  'dashboard/custom': 'Custom',
}

function buildTemplateFromState(state: DashboardCreateRouteState): DashboardCreateTemplate | null {
  if (state.template) return state.template
  if (!state.fromItem) return null

  return {
    source: state.fromItem.source,
    route: state.fromItem.route,
    title: state.fromItem.title,
    note: state.fromItem.note,
    tags: state.fromItem.tags,
    stats: state.fromItem.stats,
    builderDefaults: state.fromItem.builder,
  }
}

export default function DashboardCreate() {
  const navigate = useNavigate()
  const location = useLocation()
  const routeState = (location.state ?? {}) as DashboardCreateRouteState
  const template = useMemo(() => buildTemplateFromState(routeState), [routeState])

  const [title, setTitle] = useState(template?.title ?? 'Custom Dashboard')
  const [note, setNote] = useState(template?.note ?? '')
  const [builderConfig, setBuilderConfig] = useState<DashboardBuilderConfig>({
    season: template?.builderDefaults?.season ?? '2025-26',
    tableName: template?.builderDefaults?.tableName ?? 'matches',
    chartType: template?.builderDefaults?.chartType ?? 'bar',
    dimensionField: template?.builderDefaults?.dimensionField ?? '',
    metrics: template?.builderDefaults?.metrics ?? [],
    filters: template?.builderDefaults?.filters ?? [],
    filteredRowCount: 0,
    groupedRowCount: 0,
  })
  const { addItem } = useDashboard()

  const source = template?.source ?? 'dashboard/custom'
  const sourceLabel = SOURCE_LABEL[source]
  const trimmedTitle = title.trim()
  const canSave = trimmedTitle.length > 0
  const builderKey = `${source}_${template?.route ?? 'custom'}_${template?.builderDefaults?.tableName ?? 'matches'}`

  function saveDashboard() {
    if (!canSave) return

    addItem({
      source,
      route: template?.route ?? '/dashboard/create',
      title: trimmedTitle,
      note: note.trim() || undefined,
      tags: template?.tags,
      stats: template?.stats,
      builder: builderConfig,
    })
    navigate('/dashboard')
  }

  return (
    <div className="page-shell">
      <div style={{ maxWidth: 'var(--content-w)', margin: '0 auto', padding: '32px 28px 56px' }}>
        <div style={{ marginBottom: 18 }}>
          <button
            onClick={() => navigate('/dashboard')}
            style={{
              border: '1px solid var(--border)',
              background: 'var(--bg-panel)',
              color: 'var(--text-2)',
              borderRadius: 'var(--r-sm)',
              padding: '6px 10px',
              fontSize: '0.72rem',
              cursor: 'pointer',
              marginBottom: 10,
            }}
          >
            Back to Dashboards
          </button>

          <p style={{ fontSize: '0.72rem', color: ACCENT, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>
            Create Dashboard
          </p>
          <h1 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-1)', marginBottom: 8, fontFamily: 'var(--font-display)' }}>
            Dashboard Builder
          </h1>
          <p style={{ fontSize: '0.86rem', color: 'var(--text-2)', lineHeight: 1.5, maxWidth: 760 }}>
            Build a dashboard for <strong>{sourceLabel}</strong> using raw table fields, multiple aggregates, and filters.
          </p>
        </div>

        <div
          style={{
            border: '1px solid var(--border)',
            borderRadius: 'var(--r-md)',
            background: 'var(--bg-panel)',
            padding: '16px 18px',
            marginBottom: 18,
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: 12,
          }}
        >
          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 700 }}>
              Dashboard Title
            </span>
            <input
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="Enter dashboard title"
              style={{
                borderRadius: 'var(--r-sm)',
                border: '1px solid var(--border)',
                background: 'var(--bg-elevated)',
                color: 'var(--text-1)',
                padding: '8px 10px',
                fontSize: '0.84rem',
              }}
            />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 700 }}>
              Notes
            </span>
            <input
              value={note}
              onChange={e => setNote(e.target.value)}
              placeholder="Optional context for this dashboard"
              style={{
                borderRadius: 'var(--r-sm)',
                border: '1px solid var(--border)',
                background: 'var(--bg-elevated)',
                color: 'var(--text-1)',
                padding: '8px 10px',
                fontSize: '0.84rem',
              }}
            />
          </label>

          {!!template?.stats?.length && (
            <div style={{ gridColumn: '1 / -1', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {template.stats.map((stat, idx) => (
                <span
                  key={`${stat.label}_${idx}`}
                  style={{
                    borderRadius: 999,
                    border: '1px solid var(--border)',
                    background: 'var(--bg-elevated)',
                    padding: '4px 10px',
                    fontSize: '0.72rem',
                    color: 'var(--text-2)',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {stat.label}: {stat.value}
                </span>
              ))}
            </div>
          )}
        </div>

        <DragDropChartBuilder
          key={builderKey}
          initialConfig={template?.builderDefaults}
          onConfigChange={setBuilderConfig}
        />

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button
            onClick={() => navigate('/dashboard')}
            style={{
              border: '1px solid var(--border)',
              background: 'var(--bg-panel)',
              color: 'var(--text-2)',
              borderRadius: 'var(--r-sm)',
              padding: '8px 12px',
              fontSize: '0.76rem',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={saveDashboard}
            disabled={!canSave}
            style={{
              border: `1px solid ${canSave ? ACCENT : 'var(--border)'}`,
              background: canSave ? `${ACCENT}18` : 'var(--bg-panel)',
              color: canSave ? ACCENT : 'var(--text-3)',
              borderRadius: 'var(--r-sm)',
              padding: '8px 14px',
              fontSize: '0.76rem',
              fontWeight: 800,
              cursor: canSave ? 'pointer' : 'not-allowed',
            }}
          >
            Create Dashboard
          </button>
        </div>
      </div>
    </div>
  )
}
