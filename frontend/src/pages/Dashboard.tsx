import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useDashboard } from '../hooks/useDashboard'
import type { DashboardCreateRouteState, DashboardItem, DashboardSource } from '../types'

const ACCENT = '#D97706'

const SOURCE_META: Record<DashboardSource, { label: string; color: string; section: string }> = {
  'arena/todays-picks': { label: "Today's Picks", color: '#06C5F8', section: 'Arena' },
  'arena/match-deep-dive': { label: 'Match Deep Dive', color: '#38BDF8', section: 'Arena' },
  'arena/model-performance': { label: 'Model Performance', color: '#0EA5E9', section: 'Arena' },
  'arena/player-stats': { label: 'Player Stats', color: '#22D3EE', section: 'Arena' },
  'arena/team-stats': { label: 'Team Stats', color: '#0891B2', section: 'Arena' },
  'dashboard/custom': { label: 'Custom Builder', color: '#F97316', section: 'Dashboard' },
}

function fmtDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function DashboardCard({
  item,
  onOpen,
  onRemove,
}: {
  item: DashboardItem
  onOpen: (item: DashboardItem) => void
  onRemove: (id: string) => void
}) {
  const meta = SOURCE_META[item.source] ?? { label: 'Unknown', color: '#64748B', section: 'Arena' }
  const isCustom = item.source === 'dashboard/custom'

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        background: 'var(--bg-panel)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--r-md)',
        padding: '16px 18px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
        <span
          style={{
            padding: '4px 10px',
            borderRadius: 20,
            background: `${meta.color}20`,
            color: meta.color,
            fontSize: '0.68rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.07em',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {meta.section} · {meta.label}
        </span>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
          {fmtDateTime(item.savedAt)}
        </span>
      </div>

      <div>
        <p style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-1)', marginBottom: 6 }}>{item.title}</p>
        {item.note && (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-2)', lineHeight: 1.55 }}>{item.note}</p>
        )}
      </div>

      {!!item.stats?.length && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {item.stats.map((stat, idx) => (
            <span
              key={`${stat.label}_${idx}`}
              style={{
                padding: '4px 8px',
                borderRadius: 8,
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                color: stat.color ?? 'var(--text-2)',
                fontSize: '0.72rem',
                fontFamily: 'var(--font-mono)',
              }}
            >
              <strong style={{ color: 'var(--text-1)' }}>{stat.label}:</strong> {stat.value}
            </span>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, marginTop: 'auto' }}>
        <button
          onClick={() => onOpen(item)}
          style={{
            padding: '7px 12px',
            borderRadius: 'var(--r-sm)',
            border: '1px solid var(--border)',
            background: 'var(--bg-elevated)',
            color: 'var(--text-1)',
            fontSize: '0.76rem',
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          {isCustom ? 'Open Builder' : 'Open Source'}
        </button>
        <button
          onClick={() => onRemove(item.id)}
          style={{
            padding: '7px 12px',
            borderRadius: 'var(--r-sm)',
            border: '1px solid rgba(255,76,106,0.35)',
            background: 'rgba(255,76,106,0.08)',
            color: 'var(--error)',
            fontSize: '0.76rem',
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          Remove
        </button>
      </div>
    </motion.div>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { items, removeItem, clearAll } = useDashboard()
  const [sourceFilter, setSourceFilter] = useState<'all' | DashboardSource>('all')

  const sourceOptions = useMemo(() => {
    return Object.keys(SOURCE_META) as DashboardSource[]
  }, [])

  const filteredItems = useMemo(() => {
    if (sourceFilter === 'all') return items
    return items.filter(item => item.source === sourceFilter)
  }, [items, sourceFilter])

  return (
    <div className="page-shell">
      <div style={{ maxWidth: 'var(--content-w)', margin: '0 auto', padding: '32px 28px 56px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14, alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: 22 }}>
          <div>
            <p style={{ fontSize: '0.72rem', color: ACCENT, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>
              Dashboard
            </p>
            <h1 style={{ fontSize: '1.42rem', fontWeight: 800, color: 'var(--text-1)', marginBottom: 8, fontFamily: 'var(--font-display)' }}>
              Created Dashboards
            </h1>
            <p style={{ fontSize: '0.86rem', color: 'var(--text-2)', lineHeight: 1.5, maxWidth: 720 }}>
              Review all previously created dashboards first, then open the dedicated create page to build a new one from Arena context or raw tables.
            </p>
          </div>

          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
              onClick={() => navigate('/dashboard/create')}
              style={{
                padding: '7px 12px',
                borderRadius: 'var(--r-sm)',
                border: `1px solid ${ACCENT}`,
                background: `${ACCENT}15`,
                color: ACCENT,
                fontSize: '0.76rem',
                fontWeight: 800,
                cursor: 'pointer',
              }}
            >
              Create Dashboard
            </button>
            {!!items.length && (
              <button
                onClick={clearAll}
                style={{
                  padding: '7px 12px',
                  borderRadius: 'var(--r-sm)',
                  border: '1px solid rgba(255,76,106,0.35)',
                  background: 'rgba(255,76,106,0.08)',
                  color: 'var(--error)',
                  fontSize: '0.76rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                Clear All
              </button>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 20 }}>
          <button
            onClick={() => setSourceFilter('all')}
            style={{
              padding: '6px 12px',
              borderRadius: 16,
              border: `1px solid ${sourceFilter === 'all' ? ACCENT : 'var(--border)'}`,
              background: sourceFilter === 'all' ? `${ACCENT}20` : 'var(--bg-panel)',
              color: sourceFilter === 'all' ? ACCENT : 'var(--text-2)',
              fontSize: '0.72rem',
              fontWeight: 700,
              fontFamily: 'var(--font-mono)',
              cursor: 'pointer',
            }}
          >
            All ({items.length})
          </button>

          {sourceOptions.map(source => {
            const count = items.filter(item => item.source === source).length
            const active = sourceFilter === source
            return (
              <button
                key={source}
                onClick={() => setSourceFilter(source)}
                style={{
                  padding: '6px 12px',
                  borderRadius: 16,
                  border: `1px solid ${active ? SOURCE_META[source].color : 'var(--border)'}`,
                  background: active ? `${SOURCE_META[source].color}20` : 'var(--bg-panel)',
                  color: active ? SOURCE_META[source].color : 'var(--text-2)',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  fontFamily: 'var(--font-mono)',
                  cursor: 'pointer',
                }}
              >
                {SOURCE_META[source].label} ({count})
              </button>
            )
          })}
        </div>

        {filteredItems.length === 0 ? (
          <div
            style={{
              border: '1px solid var(--border)',
              borderRadius: 'var(--r-md)',
              background: 'var(--bg-panel)',
              padding: '34px 24px',
              textAlign: 'center',
            }}
          >
            <p style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-1)', marginBottom: 8 }}>
              {items.length === 0 ? 'No dashboards created yet' : 'No created items for this filter'}
            </p>
            <p style={{ fontSize: '0.84rem', color: 'var(--text-2)', marginBottom: 14 }}>
              Open Arena pages and use the <strong>Create Dashboard</strong> button on any view.
            </p>
            <button
              onClick={() => navigate('/arena/deep-dive')}
              style={{
                padding: '8px 14px',
                borderRadius: 'var(--r-sm)',
                border: `1px solid ${ACCENT}`,
                background: `${ACCENT}15`,
                color: ACCENT,
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              Open Arena
            </button>
            <button
              onClick={() => navigate('/dashboard/create')}
              style={{
                marginLeft: 8,
                padding: '8px 14px',
                borderRadius: 'var(--r-sm)',
                border: `1px solid ${ACCENT}`,
                background: `${ACCENT}12`,
                color: ACCENT,
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              Create Dashboard
            </button>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
            {filteredItems.map(item => (
              <DashboardCard
                key={item.id}
                item={item}
                onOpen={(selectedItem) => {
                  if (selectedItem.source === 'dashboard/custom') {
                    const state: DashboardCreateRouteState = { fromItem: selectedItem }
                    navigate('/dashboard/create', { state })
                    return
                  }
                  navigate(selectedItem.route)
                }}
                onRemove={removeItem}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
