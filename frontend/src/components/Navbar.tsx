import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import SportsMark from './SportsMark'
import type { NavItem } from '../types'
import { useSportContext } from '../context/SportContext'
import { isLiveDataSelection, type SportId } from '../config/sports'
import styles from './Navbar.module.css'

const NAV_ITEMS: NavItem[] = [
  {
    id: 'pulse',
    label: 'Pulse',
    path: '/pulse',
    description: 'Sports news & daily intelligence',
    color: 'var(--accent)',
    subItems: [
      { label: 'Daily Brief',    path: '/pulse/brief',    description: 'AI-curated game intelligence for today' },
      { label: 'Top Stories',   path: '/pulse/news',     description: 'Latest sports news and injury reports' },
      { label: 'Match Previews',path: '/pulse/previews', description: 'Pre-game context and risk signals' },
    ],
  },
  {
    id: 'arena',
    label: 'Arena',
    path: '/arena',
    description: 'Predictions & model analysis',
    color: 'var(--accent-arena)',
    subItems: [
      { label: "Today's Picks",   path: '/arena/predictions', description: "Model consensus for today's games" },
      { label: 'Match Deep Dive', path: '/arena/deep-dive',   description: 'SHAP explainability + feature snapshots' },
      { label: 'Model Performance',path:'/arena/performance', description: 'Accuracy, Brier score, confidence' },
    ],
  },
  {
    id: 'lab',
    label: 'Lab',
    path: '/lab',
    description: 'Data exploration & monitoring',
    color: 'var(--accent-lab)',
    subItems: [
      { label: 'Data Quality',  path: '/lab/quality',  description: 'Row counts, checks and team metrics' },
      { label: 'Pipeline Runs', path: '/lab/pipeline', description: 'Recent ingestion and feature runs' },
      { label: 'MLOps Monitor', path: '/lab/mlops',    description: 'Drift alerts and retrain policy' },
    ],
  },
  {
    id: 'dashboard',
    label: 'Dashboard',
    path: '/dashboard',
    description: 'Created Arena dashboards and chart views',
    color: 'var(--accent-dashboard)',
    subItems: [],
  },
  {
    id: 'scribble',
    label: 'Scribble',
    path: '/scribble',
    description: 'Raw data playground & SQL lab',
    color: 'var(--accent-scrib)',
    subItems: [
      { label: 'SQL Lab',       path: '/scribble', description: 'Query raw tables directly' },
      { label: 'Notebooks',     path: '/scribble', description: 'Saved analysis playgrounds' },
      { label: 'Feature Maker', path: '/scribble', description: 'Create custom data attributes' },
    ],
  },
  {
    id: 'chatbot',
    label: 'Chatbot',
    path: '/chatbot',
    description: 'AI data assistant',
    color: 'var(--accent-chat)',
    subItems: [
      { label: 'Data Inquiry',  path: '/chatbot?intent=data-inquiry',  description: 'Ask questions about live stats' },
      { label: 'Model Insight', path: '/chatbot/model-insight', description: 'Understand prediction factors' },
      { label: 'Draft Help',    path: '/chatbot/draft-help',    description: 'Compare player valuations' },
    ],
  },
]

interface NavbarProps {
  systemStatus: 'healthy' | 'degraded' | 'error' | 'loading'
  theme: 'dark' | 'light'
  onToggleTheme: () => void
}

export default function Navbar({ systemStatus, theme, onToggleTheme }: NavbarProps) {
  const navigate  = useNavigate()
  const location  = useLocation()
  const [openId, setOpenId] = useState<string | null>(null)
  const navRef    = useRef<HTMLDivElement>(null)
  const { selection, sportOptions, leagueOptions, seasonOptions, setSport, setLeague, setSeason } = useSportContext()
  const isLiveContext = isLiveDataSelection(selection)

  const close = useCallback(() => setOpenId(null), [])

  useEffect(() => {
    close()
  }, [location.pathname, close])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (navRef.current && !navRef.current.contains(e.target as Node)) close()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [close])

  const activeSection = location.pathname.split('/')[1] || ''
  const openItem = NAV_ITEMS.find(n => n.id === openId)

  // status-pill is a globally shared class (used in multiple pages)
  const pillClass =
    systemStatus === 'healthy'  ? 'status-pill healthy'  :
    systemStatus === 'error'    ? 'status-pill error'    :
    systemStatus === 'degraded' ? 'status-pill degraded' :
    'status-pill'

  const pillLabel =
    systemStatus === 'healthy'  ? 'Healthy'  :
    systemStatus === 'error'    ? 'Error'    :
    systemStatus === 'degraded' ? 'Degraded' :
    'Connecting'

  return (
    <>
      <div className={styles['navbar-shell']} ref={navRef}>
        <nav className={`${styles.navbar} ${styles['navbar-main']}`}>
          {/* Logo */}
          <button className={styles['navbar-logo']} onClick={() => navigate('/')} aria-label="Go to Overview">
            <SportsMark size={38} />
          </button>

          {/* Primary nav */}
          <div className={styles['navbar-nav']}>
            {NAV_ITEMS.map(item => {
              const isActive = activeSection === item.id
              const isOpen   = openId === item.id
              const hasMenu  = item.subItems.length > 0

              return (
                <button
                  key={item.id}
                  className={[
                    styles['nav-item'],
                    isActive ? styles.active : '',
                    isOpen   ? styles.open   : '',
                  ].join(' ')}
                  onClick={() => {
                    if (hasMenu) {
                      setOpenId(isOpen ? null : item.id)
                    } else {
                      navigate(item.path)
                    }
                  }}
                  style={{ '--item-color': item.color } as React.CSSProperties}
                >
                  <span
                    className={styles['nav-item-dot']}
                    style={{ background: item.color, opacity: isActive || isOpen ? 1 : 0.4 }}
                  />
                  {item.label}
                  {item.badge && (
                    <span style={{
                      fontSize: '0.6rem',
                      fontWeight: 700,
                      padding: '1px 6px',
                      borderRadius: '999px',
                      background: 'color-mix(in srgb, var(--warning) 14%, transparent)',
                      color: 'var(--warning)',
                      letterSpacing: '0.06em',
                      lineHeight: 1.6,
                    }}>
                      {item.badge}
                    </span>
                  )}
                  {hasMenu && (
                    <svg className={styles['nav-item-chevron']} viewBox="0 0 12 12" fill="none">
                      <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </button>
              )
            })}
          </div>

          {/* Right side */}
          <div className={styles['navbar-right']}>
            {/* status-pill stays global — shared class used on other pages too */}
            <div className={pillClass}>
              <span className="dot" />
              {pillLabel}
            </div>
            <button className={styles['theme-btn']} onClick={onToggleTheme} aria-label="Toggle theme">
              {theme === 'dark' ? (
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.4" />
                  <line x1="8" y1="1"  x2="8" y2="3"  stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                  <line x1="8" y1="13" x2="8" y2="15" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                  <line x1="1"  y1="8" x2="3"  y2="8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                  <line x1="13" y1="8" x2="15" y2="8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                  <line x1="3.05" y1="3.05" x2="4.46" y2="4.46" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                  <line x1="11.54" y1="11.54" x2="12.95" y2="12.95" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                  <line x1="12.95" y1="3.05" x2="11.54" y2="4.46" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                  <line x1="4.46" y1="11.54" x2="3.05" y2="12.95" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M13.5 9.5A6 6 0 1 1 6.5 2.5a4.5 4.5 0 0 0 7 7z" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </button>
          </div>
        </nav>

        <div className={styles['navbar-context-row']}>
          <div className={styles['navbar-context-row-inner']}>
            <div className={styles['navbar-context']}>
              <label className={styles['navbar-context-field']}>
                <span>Sport</span>
                <select
                  value={selection.sport}
                  onChange={(e) => setSport(e.target.value as SportId)}
                >
                  {sportOptions.map(option => (
                    <option key={option.id} value={option.id}>
                      {option.shortLabel}
                    </option>
                  ))}
                </select>
              </label>

              <label className={styles['navbar-context-field']}>
                <span>League</span>
                <select
                  value={selection.league}
                  onChange={(e) => setLeague(e.target.value)}
                >
                  {leagueOptions.map(option => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className={styles['navbar-context-field']}>
                <span>Season</span>
                <select
                  value={selection.season}
                  onChange={(e) => setSeason(e.target.value)}
                >
                  {seasonOptions.map(option => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>

              <span className={`${styles['navbar-context-status']} ${isLiveContext ? styles.live : styles.planned}`}>
                {isLiveContext ? 'Live Data' : 'Coming Soon'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Mega menu flyout */}
      <AnimatePresence>
        {openItem && (
          <motion.div
            className={styles['mega-menu-overlay']}
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
          >
            <div className={styles['mega-menu-inner']}>
              <div className={styles['mega-menu-header']}>
                <span
                  className={styles['mega-menu-title']}
                  style={{ color: openItem.color }}
                >
                  {openItem.label}
                </span>
                <span className={styles['mega-menu-desc']}>{openItem.description}</span>
              </div>
              <div className={styles['mega-menu-grid']}>
                {openItem.subItems.map(sub => (
                  <button
                    key={sub.path}
                    className={styles['mega-sub-item']}
                    onClick={() => { navigate(sub.path); close() }}
                    style={{ '--card-border-hover': openItem.color } as React.CSSProperties}
                  >
                    <span className={styles['mega-sub-item-label']}>{sub.label}</span>
                    <span className={styles['mega-sub-item-desc']}>{sub.description}</span>
                  </button>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}

export { NAV_ITEMS }
