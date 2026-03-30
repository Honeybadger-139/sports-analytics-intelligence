import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useDashboard } from '../hooks/useDashboard'
import type { DashboardItem, DashboardSource } from '../types'
import { findSportOption } from '../config/sports'
import {
  getDashboardPresetUrls,
  getDashboardToolLabel,
  openGrafanaCreateDashboard,
} from '../utils/grafana'

const ACCENT = '#D97706'

const SOURCE_META: Record<DashboardSource, { label: string; color: string; section: string }> = {
  'arena/todays-picks': { label: "Upcoming Picks", color: '#06C5F8', section: 'Arena' },
  'arena/match-deep-dive': { label: 'Match Deep Dive', color: '#38BDF8', section: 'Arena' },
  'arena/model-performance': { label: 'Model Performance', color: '#0EA5E9', section: 'Arena' },
  'arena/player-stats': { label: 'Player Stats', color: '#22D3EE', section: 'Arena' },
  'arena/team-stats': { label: 'Team Stats', color: '#0891B2', section: 'Arena' },
  'dashboard/custom': { label: 'Custom Builder', color: '#F97316', section: 'Dashboard' },
}

interface ExternalDashboardCard {
  id: string
  title: string
  description: string
  highlights: string[]
  url: string | null
  accentColor: string
  icon: string
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

function MetabaseCard({ card, toolLabel }: { card: ExternalDashboardCard; toolLabel: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ translateY: -2 }}
      transition={{ duration: 0.18 }}
      style={{
        background: 'var(--bg-panel)',
        border: '1px solid var(--border)',
        borderTop: `3px solid ${card.accentColor}`,
        borderRadius: 'var(--r-md)',
        padding: '20px 20px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        cursor: 'default',
      }}
    >
      {/* Icon + Title */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div
          style={{
            width: 38,
            height: 38,
            borderRadius: 10,
            background: `${card.accentColor}18`,
            border: `1px solid ${card.accentColor}30`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1.1rem',
            flexShrink: 0,
          }}
        >
          {card.icon}
        </div>
        <div>
          <p style={{ fontSize: '0.95rem', fontWeight: 800, color: 'var(--text-1)', lineHeight: 1.3, marginBottom: 4 }}>
            {card.title}
          </p>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-2)', lineHeight: 1.5 }}>
            {card.description}
          </p>
        </div>
      </div>

      {/* Highlights */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {card.highlights.map(h => (
          <span
            key={h}
            style={{
              padding: '3px 9px',
              borderRadius: 999,
              border: `1px solid ${card.accentColor}30`,
              background: `${card.accentColor}0e`,
              fontSize: '0.68rem',
              color: card.accentColor,
              fontFamily: 'var(--font-mono)',
              fontWeight: 600,
            }}
          >
            {h}
          </span>
        ))}
      </div>

      {/* CTA */}
      <button
        onClick={() => {
          if (card.url) {
            window.open(card.url, '_blank', 'noopener,noreferrer')
          } else {
            openGrafanaCreateDashboard()
          }
        }}
        style={{
          marginTop: 'auto',
          padding: '9px 14px',
          borderRadius: 'var(--r-sm)',
          border: `1px solid ${card.accentColor}`,
          background: card.url ? `${card.accentColor}18` : 'transparent',
          color: card.accentColor,
          fontSize: '0.78rem',
          fontWeight: 800,
          cursor: 'pointer',
          letterSpacing: '0.02em',
        }}
      >
        {card.url ? `Open Dashboard →` : `Create In ${toolLabel}`}
      </button>
    </motion.div>
  )
}

function SectionHeader({ label, count, color = 'var(--text-3)' }: { label: string; count?: number; color?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
      <span style={{ fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color, fontFamily: 'var(--font-mono)' }}>
        {label}
      </span>
      {count !== undefined && (
        <span style={{
          padding: '1px 7px', borderRadius: 999,
          background: 'var(--bg-elevated)', border: '1px solid var(--border)',
          fontSize: '0.65rem', color: 'var(--text-3)', fontFamily: 'var(--font-mono)',
        }}>
          {count}
        </span>
      )}
      <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
    </div>
  )
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
  const sportOption = findSportOption(item.sport ?? 'nba')
  const leagueLabel = sportOption.leagues.find(league => league.id === (item.league ?? 'nba'))?.label ?? (item.league ?? 'nba')

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
        <span style={{
          padding: '4px 10px', borderRadius: 20,
          background: `${meta.color}20`, color: meta.color,
          fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase',
          letterSpacing: '0.07em', fontFamily: 'var(--font-mono)',
        }}>
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
        {(item.sport || item.league || item.season) && (
          <p style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginTop: 6, fontFamily: 'var(--font-mono)' }}>
            {sportOption.label} · {leagueLabel} · {item.season ?? '2025-26'}
          </p>
        )}
      </div>

      {!!item.stats?.length && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {item.stats.map((stat, idx) => (
            <span key={`${stat.label}_${idx}`} style={{
              padding: '4px 8px', borderRadius: 8,
              background: 'var(--bg-elevated)', border: '1px solid var(--border)',
              color: stat.color ?? 'var(--text-2)', fontSize: '0.72rem', fontFamily: 'var(--font-mono)',
            }}>
              <strong style={{ color: 'var(--text-1)' }}>{stat.label}:</strong> {stat.value}
            </span>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, marginTop: 'auto' }}>
        <button
          onClick={() => onOpen(item)}
          style={{
            padding: '7px 12px', borderRadius: 'var(--r-sm)',
            border: '1px solid var(--border)', background: 'var(--bg-elevated)',
            color: 'var(--text-1)', fontSize: '0.76rem', fontWeight: 700, cursor: 'pointer',
          }}
        >
          {isCustom ? 'Open Builder' : 'Open Source'}
        </button>
        <button
          onClick={() => onRemove(item.id)}
          style={{
            padding: '7px 12px', borderRadius: 'var(--r-sm)',
            border: '1px solid rgba(255,76,106,0.35)', background: 'rgba(255,76,106,0.08)',
            color: 'var(--error)', fontSize: '0.76rem', fontWeight: 700, cursor: 'pointer',
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
  const dashboardToolLabel = getDashboardToolLabel()
  const dashboardPresetUrls = getDashboardPresetUrls()

  const sourceOptions = useMemo(() => Object.keys(SOURCE_META) as DashboardSource[], [])

  const filteredItems = useMemo(() => {
    if (sourceFilter === 'all') return items
    return items.filter(item => item.source === sourceFilter)
  }, [items, sourceFilter])

  const analyticsCards = useMemo<ExternalDashboardCard[]>(() => [
    {
      id: 'team-standings',
      title: 'NBA Team Standings 2025-26',
      description: 'Full W-L records, win percentages, and points-per-game breakdown across all 30 NBA teams.',
      highlights: ['Win % ranking', 'W-L record', 'Pts/game'],
      url: dashboardPresetUrls.standings,
      accentColor: '#06C5F8',
      icon: '🏆',
    },
    {
      id: 'player-leaderboard',
      title: 'NBA Player Leaderboard 2025-26',
      description: 'Top scorers, assist leaders, and rebounders with full season stats for all active players.',
      highlights: ['Top scorers (PPG)', 'Assist leaders', 'Full stats table'],
      url: dashboardPresetUrls.players,
      accentColor: '#22D3EE',
      icon: '🏀',
    },
    {
      id: 'match-results',
      title: 'NBA Match Results & Trends',
      description: 'Recent game results, team scoring trends, and home vs away win rate analysis.',
      highlights: ['Last 30 results', 'Scoring trend', 'Home vs Away %'],
      url: dashboardPresetUrls.matches,
      accentColor: '#38BDF8',
      icon: '📊',
    },
  ], [dashboardPresetUrls.standings, dashboardPresetUrls.players, dashboardPresetUrls.matches])

  const operationalCards = useMemo<ExternalDashboardCard[]>(() => [
    {
      id: 'prediction-performance',
      title: 'Prediction Performance',
      description: 'Track model accuracy over time, confidence calibration, and prediction volume by day.',
      highlights: ['Rolling accuracy', 'Confidence bands', 'Daily volume'],
      url: dashboardPresetUrls.prediction,
      accentColor: '#A78BFA',
      icon: '🎯',
    },
    {
      id: 'pipeline-health',
      title: 'Pipeline Health',
      description: 'Monitor daily ingestion runs, records inserted per module, and pipeline reliability trends.',
      highlights: ['Run status', 'Records/day', 'Module breakdown'],
      url: dashboardPresetUrls.pipeline,
      accentColor: '#34D399',
      icon: '⚙️',
    },
  ], [dashboardPresetUrls.prediction, dashboardPresetUrls.pipeline])

  return (
    <div className="page-shell">
      <div style={{ maxWidth: 'var(--content-w)', margin: '0 auto', padding: '32px 28px 64px' }}>

        {/* ── Page Header ─────────────────────────────────────────────── */}
        <div style={{
          display: 'flex', justifyContent: 'space-between',
          alignItems: 'flex-start', flexWrap: 'wrap', gap: 16, marginBottom: 36,
        }}>
          <div>
            <p style={{ fontSize: '0.68rem', color: ACCENT, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 6, fontFamily: 'var(--font-mono)' }}>
              Analytics Hub
            </p>
            <h1 style={{ fontSize: '1.6rem', fontWeight: 900, color: 'var(--text-1)', marginBottom: 10, fontFamily: 'var(--font-display)', lineHeight: 1.15 }}>
              Dashboards
            </h1>
            <p style={{ fontSize: '0.86rem', color: 'var(--text-2)', lineHeight: 1.6, maxWidth: 560 }}>
              Pre-built analytics dashboards for NBA stats, player performance, and pipeline monitoring.
              Click any dashboard to open it without signing in.
            </p>
          </div>

          {/* Admin action — clearly separated from public viewer experience */}
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6,
          }}>
            <a
              href={`${String(import.meta.env.VITE_METABASE_URL || 'https://gamethread-metabase-vxjxsnk3gq-uc.a.run.app').replace(/\/$/, '')}/auth/login`}
              target="_blank"
              rel="noreferrer"
              style={{
                padding: '8px 14px',
                borderRadius: 'var(--r-sm)',
                border: '1px solid var(--border)',
                background: 'var(--bg-elevated)',
                color: 'var(--text-2)',
                fontSize: '0.75rem',
                fontWeight: 700,
                cursor: 'pointer',
                textDecoration: 'none',
                whiteSpace: 'nowrap',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <span style={{ fontSize: '0.8rem' }}>🔐</span>
              Admin: Create Dashboard
            </a>
            <p style={{ fontSize: '0.65rem', color: 'var(--text-3)', textAlign: 'right', fontFamily: 'var(--font-mono)', maxWidth: 200 }}>
              Requires {dashboardToolLabel} login to create or edit dashboards
            </p>
          </div>

        </div>

        {/* ── Analytics Dashboards ─────────────────────────────────────── */}
        <section style={{ marginBottom: 40 }}>
          <SectionHeader label="Analytics Dashboards" color="#06C5F8" />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
            {analyticsCards.map(card => (
              <MetabaseCard key={card.id} card={card} toolLabel={dashboardToolLabel} />
            ))}
          </div>
        </section>

        {/* ── Operational Dashboards ───────────────────────────────────── */}
        <section style={{ marginBottom: 48 }}>
          <SectionHeader label="Operational Dashboards" color="#34D399" />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14 }}>
            {operationalCards.map(card => (
              <MetabaseCard key={card.id} card={card} toolLabel={dashboardToolLabel} />
            ))}
          </div>
        </section>

        {/* ── My Saved Views ───────────────────────────────────────────── */}
        <section>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }}>
              <span style={{ fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
                My Saved Views
              </span>
              <span style={{
                padding: '1px 7px', borderRadius: 999,
                background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                fontSize: '0.65rem', color: 'var(--text-3)', fontFamily: 'var(--font-mono)',
              }}>
                {items.length}
              </span>
              <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
            </div>
            {!!items.length && (
              <button
                onClick={clearAll}
                style={{
                  marginLeft: 12, padding: '5px 10px', borderRadius: 'var(--r-sm)',
                  border: '1px solid rgba(255,76,106,0.35)', background: 'rgba(255,76,106,0.08)',
                  color: 'var(--error)', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer',
                }}
              >
                Clear All
              </button>
            )}
          </div>

          {/* Filter tabs */}
          {!!items.length && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 16 }}>
              <button
                onClick={() => setSourceFilter('all')}
                style={{
                  padding: '5px 12px', borderRadius: 16,
                  border: `1px solid ${sourceFilter === 'all' ? ACCENT : 'var(--border)'}`,
                  background: sourceFilter === 'all' ? `${ACCENT}20` : 'var(--bg-panel)',
                  color: sourceFilter === 'all' ? ACCENT : 'var(--text-2)',
                  fontSize: '0.72rem', fontWeight: 700, fontFamily: 'var(--font-mono)', cursor: 'pointer',
                }}
              >
                All ({items.length})
              </button>
              {sourceOptions.map(source => {
                const count = items.filter(item => item.source === source).length
                if (count === 0) return null
                const active = sourceFilter === source
                return (
                  <button
                    key={source}
                    onClick={() => setSourceFilter(source)}
                    style={{
                      padding: '5px 12px', borderRadius: 16,
                      border: `1px solid ${active ? SOURCE_META[source].color : 'var(--border)'}`,
                      background: active ? `${SOURCE_META[source].color}20` : 'var(--bg-panel)',
                      color: active ? SOURCE_META[source].color : 'var(--text-2)',
                      fontSize: '0.72rem', fontWeight: 700, fontFamily: 'var(--font-mono)', cursor: 'pointer',
                    }}
                  >
                    {SOURCE_META[source].label} ({count})
                  </button>
                )
              })}
            </div>
          )}

          {filteredItems.length === 0 ? (
            <div style={{
              border: '1px solid var(--border)', borderRadius: 'var(--r-md)',
              background: 'var(--bg-panel)', padding: '40px 24px', textAlign: 'center',
            }}>
              <div style={{ fontSize: '2rem', marginBottom: 12 }}>📋</div>
              <p style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-1)', marginBottom: 8 }}>
                {items.length === 0 ? 'No saved views yet' : 'No views for this filter'}
              </p>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-2)', marginBottom: 20, maxWidth: 380, margin: '0 auto 20px' }}>
                Navigate to any Arena page and click <strong>Save to Dashboard</strong> to bookmark a view here.
              </p>
              <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
                <button
                  onClick={() => navigate('/arena/deep-dive')}
                  style={{
                    padding: '8px 16px', borderRadius: 'var(--r-sm)',
                    border: `1px solid ${ACCENT}`, background: `${ACCENT}15`,
                    color: ACCENT, fontSize: '0.78rem', fontWeight: 700, cursor: 'pointer',
                  }}
                >
                  Open Arena
                </button>
              </div>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
              {filteredItems.map(item => (
                <DashboardCard
                  key={item.id}
                  item={item}
                  onOpen={(selectedItem) => {
                    if (selectedItem.source === 'dashboard/custom') {
                      openGrafanaCreateDashboard()
                      return
                    }
                    navigate(selectedItem.route)
                  }}
                  onRemove={removeItem}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
