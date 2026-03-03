import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import SportsMark from './SportsMark'
import type { NavItem } from '../types'

const NAV_ITEMS: NavItem[] = [
  {
    id: 'pulse',
    label: 'Pulse',
    path: '/pulse',
    description: 'Sports news & daily intelligence',
    color: '#FF5C1A',
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
    description: 'Predictions & bankroll analysis',
    color: '#06C5F8',
    subItems: [
      { label: "Today's Picks",  path: '/arena/predictions', description: "Model consensus for today's games" },
      { label: 'Match Deep Dive',path: '/arena/deep-dive',   description: 'SHAP explainability + feature snapshots' },
      { label: 'Model Performance',path:'/arena/performance',description: 'Accuracy, Brier score, confidence' },
      { label: 'Bankroll',       path: '/arena/bankroll',    description: 'Bet history, PnL and ROI tracking' },
    ],
  },
  {
    id: 'lab',
    label: 'Lab',
    path: '/lab',
    description: 'Data exploration & monitoring',
    color: '#8B5CF6',
    subItems: [
      { label: 'Raw Explorer',  path: '/lab/raw',      description: 'Browse all raw database tables' },
      { label: 'Data Quality',  path: '/lab/quality',  description: 'Row counts, checks and team metrics' },
      { label: 'Pipeline Runs', path: '/lab/pipeline', description: 'Recent ingestion and feature runs' },
      { label: 'MLOps Monitor', path: '/lab/mlops',    description: 'Drift alerts and retrain policy' },
    ],
  },
  {
    id: 'scribble',
    label: 'Scribble',
    path: '/scribble',
    description: 'Raw data playground & SQL lab',
    color: '#10B981',
    subItems: [],
  },
  {
    id: 'chatbot',
    label: 'Chatbot',
    path: '/chatbot',
    description: 'AI data assistant',
    color: '#F59E0B',
    subItems: [],
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
  const navRef    = useRef<HTMLElement>(null)

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
      <nav className="navbar" ref={navRef}>
        {/* Logo */}
        <button className="navbar-logo" onClick={() => navigate('/')} aria-label="Go to Overview">
          <SportsMark size={38} />
        </button>

        {/* Primary nav */}
        <div className="navbar-nav">
          {NAV_ITEMS.map(item => {
            const isActive = activeSection === item.id
            const isOpen   = openId === item.id
            const hasMenu  = item.subItems.length > 0

            return (
              <button
                key={item.id}
                className={`nav-item ${isActive ? 'active' : ''} ${isOpen ? 'open' : ''}`}
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
                  className="nav-item-dot"
                  style={{ background: item.color, opacity: isActive || isOpen ? 1 : 0.4 }}
                />
                {item.label}
                {item.badge && (
                  <span style={{
                    fontSize: '0.6rem',
                    fontWeight: 700,
                    padding: '1px 6px',
                    borderRadius: '999px',
                    background: 'rgba(255,177,0,0.15)',
                    color: '#FFB100',
                    letterSpacing: '0.06em',
                    lineHeight: 1.6,
                  }}>
                    {item.badge}
                  </span>
                )}
                {hasMenu && (
                  <svg className="nav-item-chevron" viewBox="0 0 12 12" fill="none">
                    <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </button>
            )
          })}
        </div>

        {/* Right side */}
        <div className="navbar-right">
          <div className={pillClass}>
            <span className="dot" />
            {pillLabel}
          </div>
          <button className="theme-btn" onClick={onToggleTheme} aria-label="Toggle theme">
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

      {/* Mega menu flyout */}
      <AnimatePresence>
        {openItem && (
          <motion.div
            className="mega-menu-overlay"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
          >
            <div className="mega-menu-inner">
              <div className="mega-menu-header">
                <span
                  className="mega-menu-title"
                  style={{ color: openItem.color }}
                >
                  {openItem.label}
                </span>
                <span className="mega-menu-desc">{openItem.description}</span>
              </div>
              <div className="mega-menu-grid">
                {openItem.subItems.map(sub => (
                  <button
                    key={sub.path}
                    className="mega-sub-item"
                    onClick={() => { navigate(sub.path); close() }}
                    style={{ '--card-border-hover': openItem.color } as React.CSSProperties}
                  >
                    <span className="mega-sub-item-label">{sub.label}</span>
                    <span className="mega-sub-item-desc">{sub.description}</span>
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
