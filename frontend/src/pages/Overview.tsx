import { useNavigate } from 'react-router-dom'
import { motion, type Variants } from 'framer-motion'
import { useSystemStatus } from '../hooks/useApi'
import { NAV_ITEMS } from '../components/Navbar'
import { findSportOption, isLiveDataSelection } from '../config/sports'
import { useSportContext } from '../context/SportContext'

function fmt(n: number | undefined | null, decimals = 0) {
  if (n == null) return '--'
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: decimals })
}

const stagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.055 } },
}
const fadeUp: Variants = {
  hidden: { opacity: 0, y: 14 },
  show:   { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.25, 0.1, 0.25, 1] } },
}

export default function Overview() {
  const navigate = useNavigate()
  const { data: sys, loading: sysLoading } = useSystemStatus()
  const { selection, setSport, setLeague } = useSportContext()
  const sport = findSportOption(selection.sport)
  const league = sport.leagues.find(item => item.id === selection.league)?.label ?? selection.league
  const isLiveSelection = isLiveDataSelection(selection)

  const statusClass =
    sys?.status === 'healthy'  ? 'status-healthy'  :
    sys?.status === 'error'    ? 'status-error'     :
    sys?.status === 'degraded' ? 'status-degraded'  : ''

  const metrics = [
    {
      label: 'Context',
      value: isLiveSelection ? 'LIVE' : 'COMING SOON',
      meta: `${sport.label} · ${league} · ${selection.season}`,
      accent: isLiveSelection ? '#00D68F' : '#F59E0B',
      valueClass: isLiveSelection ? 'status-healthy' : 'status-degraded',
    },
    {
      label: 'Database',
      value: sysLoading ? '…' : (sys?.database ?? '--').toUpperCase(),
      meta: 'PostgreSQL',
      accent: sys?.status === 'healthy' ? '#00D68F' : sys?.status === 'error' ? '#FF4C6A' : undefined,
      valueClass: statusClass,
    },
    {
      label: 'Pipeline',
      value: sysLoading ? '…' : (sys?.pipeline?.last_status ?? '--').toUpperCase(),
      meta: sys?.pipeline?.last_sync
        ? `Synced ${new Date(sys.pipeline.last_sync).toLocaleTimeString()}`
        : 'No sync yet',
      accent: '#06C5F8',
    },
    {
      label: 'Matches',
      value: isLiveSelection ? (sysLoading ? '…' : fmt(sys?.stats?.matches)) : '—',
      meta: isLiveSelection ? `Season ${selection.season}` : 'Live for Basketball · NBA',
      accent: '#FF5C1A',
      mono: true,
    },
    {
      label: 'Features',
      value: sysLoading ? '…' : fmt(sys?.stats?.features),
      meta: 'Feature rows',
      accent: '#8B5CF6',
      mono: true,
    },
    {
      label: 'Players',
      value: isLiveSelection ? (sysLoading ? '…' : fmt(sys?.stats?.active_players)) : '—',
      meta: isLiveSelection ? 'Active entries' : 'Sport adapters pending',
      accent: '#06C5F8',
      mono: true,
    },
  ]

  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  })

  return (
    <div className="page-shell">
      <div className="page-content">

        {/* Hero */}
        <motion.div
          className="overview-hero"
          variants={stagger}
          initial="hidden"
          animate="show"
        >
          <motion.p className="overview-eyebrow" variants={fadeUp}>
            {today} · {sport.label} · {league} · {selection.season}
          </motion.p>
          <motion.h1 className="overview-title" variants={fadeUp}>
            Sports Analytics<br />Intelligence
          </motion.h1>
          <motion.p className="overview-subtitle" variants={fadeUp}>
            {isLiveSelection
              ? 'Basketball · NBA prediction engine, feature engineering, model monitoring, deep-dive analytics, and AI intelligence.'
              : 'Selected sport/league is in rollout. Core workflows are visible, while live metrics are currently enabled only for Basketball · NBA.'}
          </motion.p>
          {!isLiveSelection && (
            <motion.div
              variants={fadeUp}
              style={{
                marginTop: 14,
                border: '1px solid rgba(245, 158, 11, 0.3)',
                background: 'rgba(245, 158, 11, 0.08)',
                borderRadius: 'var(--r-sm)',
                padding: '10px 12px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 10,
                maxWidth: 760,
              }}
            >
              <span style={{ fontSize: '0.78rem', color: 'var(--warning)' }}>
                Current selection is coming soon. Switch to Basketball · NBA to access all active modules.
              </span>
              <button
                onClick={() => {
                  setSport('nba')
                  setLeague('nba')
                }}
                style={{
                  border: '1px solid rgba(245, 158, 11, 0.45)',
                  background: 'rgba(245, 158, 11, 0.12)',
                  color: 'var(--warning)',
                  borderRadius: 'var(--r-sm)',
                  padding: '6px 10px',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                }}
              >
                Switch To Basketball · NBA
              </button>
            </motion.div>
          )}
        </motion.div>

        {/* Metric cards */}
        <div className="metrics-section">
          <p className="section-label">Live System Metrics</p>
          <motion.div
            className="metrics-grid"
            variants={stagger}
            initial="hidden"
            animate="show"
          >
            {metrics.map(m => (
              <motion.div
                key={m.label}
                className="metric-card"
                variants={fadeUp}
                style={{ '--card-accent': m.accent } as React.CSSProperties}
              >
                <p className="metric-card-label">{m.label}</p>
                <p className={`metric-card-value ${m.mono ? 'mono' : ''} ${m.valueClass ?? ''}`}>
                  {m.value}
                </p>
                <p className="metric-card-meta">{m.meta}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>

        {/* Navigation Directory */}
        <div className="directory-section">
          <p className="section-label">What's in this dashboard</p>

          <motion.div
            className="directory-grid"
            variants={stagger}
            initial="hidden"
            animate="show"
          >
            {NAV_ITEMS.slice(0, 3).map(item => (
              <DirectoryCard key={item.id} item={item} onNavigate={navigate} disabled={!isLiveSelection} />
            ))}
          </motion.div>

          <motion.div
            className="directory-grid-bottom"
            variants={stagger}
            initial="hidden"
            animate="show"
          >
            {NAV_ITEMS.slice(3).map(item => (
              <DirectoryCard key={item.id} item={item} onNavigate={navigate} disabled={!isLiveSelection} />
            ))}
          </motion.div>
        </div>

      </div>
    </div>
  )
}

interface DirectoryCardProps {
  item: (typeof NAV_ITEMS)[0]
  onNavigate: (path: string) => void
  disabled?: boolean
}

function DirectoryCard({ item, onNavigate, disabled = false }: DirectoryCardProps) {
  const isComingSoon = disabled

  const descriptions: Record<string, string> = {
    pulse:   'Daily game intelligence, sports news, injury reports, and pre-game context grounded in cited sources.',
    arena:   'Run model predictions for today\'s games, deep-dive into SHAP explainability, and track ensemble model performance across the season.',
    lab:     'Browse raw Postgres tables, monitor data quality metrics, inspect ingestion pipeline runs, and track MLOps health.',
    dashboard: 'Review and manage created Arena dashboards and chart snapshots from prediction, player, and team analysis views.',
    scribble:'Compose new analytics metrics and features from raw data. Build, test and save custom notebooks — no code required.',
    chatbot: 'Ask plain-English questions about any game, team, player, or model outcome and get AI-summarised answers from your live data.',
  }

  return (
    <motion.div
      className="dir-card"
      variants={fadeUp}
      style={{
        '--card-color': item.color,
        '--card-glow': item.color,
      } as React.CSSProperties}
    >
      <div className="dir-card-top">
        <span className="dir-card-badge">{item.label}</span>
        {isComingSoon && <span className="dir-card-coming">Coming Soon</span>}
      </div>

      <h2 className="dir-card-title">{item.label}</h2>
      <p className="dir-card-desc">{descriptions[item.id]}</p>

      {item.subItems.length > 0 && (
        <div className="dir-subitems">
          {item.subItems.map(sub => (
            <button
              key={sub.path}
              className="dir-subitem"
              onClick={() => {
                if (!isComingSoon) onNavigate(sub.path)
              }}
              style={{
                textAlign: 'left',
                background: 'none',
                border: 'none',
                cursor: isComingSoon ? 'not-allowed' : 'pointer',
                opacity: isComingSoon ? 0.5 : 1,
                padding: '8px 0',
                borderBottom: '1px solid var(--border)',
                width: '100%',
              }}
            >
              <span className="dir-subitem-dot" style={{ background: item.color }} />
              <span>
                <span className="dir-subitem-name">{sub.label}</span>
                {' '}
                <span className="dir-subitem-desc">{sub.description}</span>
              </span>
            </button>
          ))}
        </div>
      )}

      {isComingSoon ? (
        <span
          className="dir-card-link disabled"
          style={{ '--card-color': item.color } as React.CSSProperties}
        >
          In Development
        </span>
      ) : (
        <button
          className="dir-card-link"
          onClick={() => onNavigate(item.path)}
          style={{ '--card-color': item.color } as React.CSSProperties}
        >
          Explore {item.label}
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M2 6h8M6 2l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      )}
    </motion.div>
  )
}
