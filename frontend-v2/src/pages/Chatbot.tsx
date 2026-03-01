import { motion } from 'framer-motion'

export default function Chatbot() {
  return (
    <div className="page-shell">
      <motion.div
        className="stub-page"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="stub-icon" style={{ background: 'rgba(245,158,11,0.1)', color: '#F59E0B' }}>
          💬
        </div>
        <p className="overview-eyebrow" style={{ color: '#F59E0B' }}>Coming Soon</p>
        <h1 className="stub-title">Chatbot</h1>
        <p className="stub-desc">
          An AI-powered data assistant. Ask plain-English questions about any game, team, player,
          or model outcome and get answers synthesised directly from your live Postgres datasets.
        </p>
        <div className="stub-subitems">
          {['Natural Language Queries', 'Live Data Context', 'Game Summaries', 'Model Explainer', 'Trend Detector'].map(t => (
            <span key={t} className="stub-tag">{t}</span>
          ))}
        </div>
        <div className="stub-wip">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 1v3M7 10v3M1 7h3M10 7h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
            <circle cx="7" cy="7" r="2.5" stroke="currentColor" strokeWidth="1.3"/>
          </svg>
          Backend integration in progress
        </div>
      </motion.div>
    </div>
  )
}
