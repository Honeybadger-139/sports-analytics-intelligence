import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'

const subItems = [
  { label: 'Raw Explorer',  path: '/lab/raw',      desc: 'Browse all raw Postgres tables: matches, teams, players, and game stats with pagination.' },
  { label: 'Data Quality',  path: '/lab/quality',  desc: 'Row counts, ingestion timing, quality checks, and top team performance indicators.' },
  { label: 'Pipeline Runs', path: '/lab/pipeline', desc: 'Recent ingestion and feature engineering run history with status, timing, and errors.' },
  { label: 'MLOps Monitor', path: '/lab/mlops',    desc: 'Model drift detection, monitoring alerts, retrain policy dry-runs, and escalation state.' },
]

export default function Lab() {
  const navigate = useNavigate()
  return (
    <div className="page-shell">
      <div className="page-content">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
          <p className="overview-eyebrow" style={{ color: '#8B5CF6' }}>Section</p>
          <h1 className="overview-title">Lab</h1>
          <p className="overview-subtitle" style={{ marginBottom: 36 }}>
            Data exploration and pipeline monitoring. Inspect every layer of the data stack.
          </p>

          <p className="section-label">Sub-sections</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12, marginBottom: 40 }}>
            {subItems.map(s => (
              <button
                key={s.path}
                onClick={() => navigate(s.path)}
                style={{
                  textAlign: 'left', background: 'var(--bg-panel)', border: '1px solid var(--border)',
                  borderRadius: 'var(--r-lg)', padding: '20px 22px', cursor: 'pointer',
                  transition: 'border-color 0.15s ease',
                }}
                onMouseEnter={e => (e.currentTarget.style.borderColor = '#8B5CF6')}
                onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
              >
                <p style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-1)', marginBottom: 6 }}>{s.label}</p>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-2)', lineHeight: 1.5 }}>{s.desc}</p>
              </button>
            ))}
          </div>

          <div className="stub-wip" style={{ display: 'inline-flex' }}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.3"/>
              <line x1="7" y1="4" x2="7" y2="7.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
              <circle cx="7" cy="10" r="0.7" fill="currentColor"/>
            </svg>
            Content is being migrated from the previous dashboard version
          </div>
        </motion.div>
      </div>
    </div>
  )
}
