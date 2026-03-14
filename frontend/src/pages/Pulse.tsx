import { lazy, Suspense } from 'react'
import { motion } from 'framer-motion'
import { useNavigate, useLocation } from 'react-router-dom'
import ErrorBoundary from '../components/ErrorBoundary'
import SkeletonCard from '../components/SkeletonCard'

const DailyBrief    = lazy(() => import('../components/Pulse/DailyBrief'))
const TopStories    = lazy(() => import('../components/Pulse/TopStories'))
const MatchPreviews = lazy(() => import('../components/Pulse/MatchPreviews'))

const ACCENT = '#D4551F'

const TABS = [
  {
    id: 'brief',
    path: '/pulse/brief',
    label: 'Daily Brief',
    desc: "AI-curated game intelligence for today's matchups, grounded in cited sources",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden>
        <rect x="1.5" y="2" width="12" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
        <line x1="4" y1="5.5" x2="11" y2="5.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
        <line x1="4" y1="8" x2="11" y2="8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
        <line x1="4" y1="10.5" x2="8" y2="10.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    id: 'news',
    path: '/pulse/news',
    label: 'Top Stories',
    desc: 'Latest sports news, injury reports, and team updates from trusted feeds',
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden>
        <path d="M2 3.5h11M2 6.5h7M2 9.5h9M2 12.5h5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    id: 'previews',
    path: '/pulse/previews',
    label: 'Match Previews',
    desc: 'Pre-game context, risk signals, and narrative summaries for upcoming games',
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden>
        <circle cx="7.5" cy="7.5" r="6" stroke="currentColor" strokeWidth="1.3"/>
        <path d="M5.5 5.5L9.5 7.5L5.5 9.5V5.5Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
      </svg>
    ),
  },
]

function LoadingFallback() {
  return (
    <div style={{ maxWidth: 'var(--content-w)', margin: '0 auto', padding: '28px', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
      <SkeletonCard height={200} />
      <SkeletonCard height={200} />
      <SkeletonCard height={200} />
    </div>
  )
}

export default function Pulse() {
  const navigate = useNavigate()
  const location = useLocation()

  const activePath = location.pathname
  const activeTab  = TABS.find(t => activePath.startsWith(t.path))

  return (
    <div className="page-shell" style={{ display: 'flex', flexDirection: 'column' }}>
      {/* ── Top bar ── */}
      <div style={{
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg-surface)',
        paddingTop: 20,
        flexShrink: 0,
      }}>
        <div style={{ maxWidth: 'var(--content-w)', margin: '0 auto', padding: '0 28px' }}>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 32, marginBottom: 0 }}>
            {/* Title */}
            <div style={{ paddingBottom: 16 }}>
              <p style={{ fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: ACCENT, marginBottom: 2 }}>
                Pulse
              </p>
              <h1 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-1)', margin: 0, fontFamily: 'var(--font-display)' }}>
                Sports news &amp; game intelligence
              </h1>
            </div>

            {/* Tab nav */}
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
                      background: 'transparent',
                      border: 'none',
                      borderBottom: isActive ? `2px solid ${ACCENT}` : '2px solid transparent',
                      color: isActive ? ACCENT : 'var(--text-2)',
                      fontFamily: 'var(--font-ui)',
                      fontSize: '0.82rem',
                      fontWeight: isActive ? 700 : 500,
                      cursor: 'pointer',
                      transition: 'color 0.15s, border-color 0.15s',
                      borderRadius: 0,
                      whiteSpace: 'nowrap',
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
          /* ── Landing ── */
          <div style={{ maxWidth: 'var(--content-w)', margin: '0 auto', padding: '40px 28px' }}>
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
              <p style={{ color: 'var(--text-2)', fontSize: '0.9rem', marginBottom: 24 }}>
                Sports news, daily intelligence briefs, and pre-game context — grounded in cited sources.
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
            <ErrorBoundary section={`Pulse · ${activeTab.label}`}>
              <Suspense fallback={<LoadingFallback />}>
                {activeTab.id === 'brief'    && <DailyBrief />}
                {activeTab.id === 'news'     && <TopStories />}
                {activeTab.id === 'previews' && <MatchPreviews />}
              </Suspense>
            </ErrorBoundary>
          </motion.div>
        )}
      </div>
    </div>
  )
}
