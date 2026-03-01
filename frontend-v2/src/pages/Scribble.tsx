import { motion } from 'framer-motion'

export default function Scribble() {
  return (
    <div className="page-shell">
      <motion.div
        className="stub-page"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="stub-icon" style={{ background: 'rgba(16,185,129,0.1)', color: '#10B981' }}>
          ✏️
        </div>
        <p className="overview-eyebrow" style={{ color: '#10B981' }}>Coming Soon</p>
        <h1 className="stub-title">Scribble</h1>
        <p className="stub-desc">
          A no-code custom metric and feature builder. Compose new analytics metrics from raw tables,
          test them against historical data, and save them as reusable notebooks.
        </p>
        <div className="stub-subitems">
          {['Metric Builder', 'Feature Lab', 'Saved Notebooks', 'Backtest Runner'].map(t => (
            <span key={t} className="stub-tag">{t}</span>
          ))}
        </div>
        <div className="stub-wip">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 1v3M7 10v3M1 7h3M10 7h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
            <circle cx="7" cy="7" r="2.5" stroke="currentColor" strokeWidth="1.3"/>
          </svg>
          Under active development
        </div>
      </motion.div>
    </div>
  )
}
