import { lazy, Suspense } from 'react'
import { motion } from 'framer-motion'
import { useNavigate, useLocation } from 'react-router-dom'

const TodaysPicks = lazy(() => import('../components/Arena/TodaysPicks'))
const DeepDive = lazy(() => import('../components/Arena/DeepDive'))
const ModelPerformance = lazy(() => import('../components/Arena/ModelPerformance'))

const ACCENT = '#0E8ED8'

const TABS = [
  {
    id: 'predictions',
    path: '/arena/predictions',
    label: "Today's Picks",
    desc: "Model ensemble consensus for today's NBA matchups with confidence scores",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden>
        <circle cx="7.5" cy="7.5" r="6" stroke="currentColor" strokeWidth="1.3" />
        <path d="M5 7.5L7 9.5L10.5 5.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    id: 'deep-dive',
    path: '/arena/deep-dive',
    label: 'Deep Dive',
    desc: 'Explore match predictions, player stats, and team analytics in depth',
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden>
        <circle cx="6.5" cy="6.5" r="5" stroke="currentColor" strokeWidth="1.3" />
        <path d="M10.5 10.5L13.5 13.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: 'performance',
    path: '/arena/performance',
    label: 'Model Performance',
    desc: 'Track accuracy, Brier score, and average confidence across all models for the season',
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden>
        <path d="M2 11L5 7L8 9L11 4L13 6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="13" cy="6" r="1.2" fill="currentColor" />
      </svg>
    ),
  },
]

function LoadingFallback() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 240, color: 'var(--text-2)', gap: 10, fontSize: '0.85rem' }}>
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ animation: 'spin 1s linear infinite' }}>
        <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="28" strokeDashoffset="10" />
      </svg>
      Loading…
    </div>
  )
}

export default function Arena() {
  const navigate = useNavigate()
  const location = useLocation()

  const activePath = location.pathname
  const activeTab = TABS.find(t => activePath.startsWith(t.path))

  return (
    <div className="page-shell full-height">
      {/* ── Top bar ── */}
      <div style={{
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg-surface)',
        paddingTop: 20,
        flexShrink: 0,
      }}>
        <div style={{ maxWidth: 'var(--content-w)', margin: '0 auto', padding: '0 28px' }}>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 32, marginBottom: 0 }}>
            <div style={{ paddingBottom: 16 }}>
              <p style={{ fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: ACCENT, marginBottom: 2 }}>
                Arena
              </p>
              <h1 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-1)', margin: 0, fontFamily: 'var(--font-display)' }}>
                Predictions &amp; model analysis
              </h1>
            </div>

            <nav style={{ display: 'flex', gap: 2, marginLeft: 'auto' }}>
              {TABS.map(tab => {
                const isActive = activePath.startsWith(tab.path)
                return (
                  <button
                    key={tab.id}
                    onClick={() => navigate(tab.path)}
                    title={tab.desc}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 7,
                      padding: '10px 16px',
                      background: 'transparent', border: 'none',
                      borderBottom: isActive ? `2px solid ${ACCENT}` : '2px solid transparent',
                      color: isActive ? ACCENT : 'var(--text-2)',
                      fontFamily: 'var(--font-ui)', fontSize: '0.82rem',
                      fontWeight: isActive ? 700 : 500,
                      cursor: 'pointer', transition: 'color 0.15s, border-color 0.15s',
                      borderRadius: 0, whiteSpace: 'nowrap',
                    }}
                    onMouseEnter={e => { if (!isActive) e.currentTarget.style.color = 'var(--text-1)' }}
                    onMouseLeave={e => { if (!isActive) e.currentTarget.style.color = 'var(--text-2)' }}
                  >
                    <span style={{ opacity: isActive ? 1 : 0.6 }}>{tab.icon}</span>
                    {tab.label}
                  </button>
                )
              })}
            </nav>
          </div>
        </div>
      </div>

      {/* ── Content ── */}
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        {!activeTab ? (
          <div style={{ maxWidth: 'var(--content-w)', margin: '0 auto', padding: '40px 28px' }}>
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
              <p style={{ color: 'var(--text-2)', fontSize: '0.9rem', marginBottom: 24 }}>
                The prediction engine. Run models, analyse game outcomes, and track model performance.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
                {TABS.map(tab => (
                  <button
                    key={tab.path}
                    onClick={() => navigate(tab.path)}
                    style={{
                      textAlign: 'left', background: 'var(--bg-panel)',
                      border: '1px solid var(--border)', borderRadius: 'var(--r-lg)',
                      padding: '20px 22px', cursor: 'pointer', transition: 'border-color 0.15s ease',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.borderColor = ACCENT)}
                    onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, color: ACCENT }}>
                      {tab.icon}
                      <p style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-1)', margin: 0 }}>{tab.label}</p>
                    </div>
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-2)', lineHeight: 1.5, margin: 0 }}>{tab.desc}</p>
                  </button>
                ))}
              </div>
            </motion.div>
          </div>
        ) : (
          <motion.div
            key={activeTab.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            style={{ height: '100%' }}
          >
            <Suspense fallback={<LoadingFallback />}>
              {activeTab.id === 'predictions' && <TodaysPicks />}
              {activeTab.id === 'deep-dive' && <DeepDive />}
              {activeTab.id === 'performance' && <ModelPerformance />}
            </Suspense>
          </motion.div>
        )}
      </div>
    </div>
  )
}
