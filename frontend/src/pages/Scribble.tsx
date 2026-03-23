import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import TableBrowser   from '../components/Scribble/TableBrowser'
import SqlLab         from '../components/Scribble/SqlLab'
import NotebooksPanel from '../components/Scribble/NotebooksPanel'

type Tab = 'explorer' | 'sql' | 'notebooks' | 'feature-maker'

const TABS: { id: Tab; label: string; icon: string; description: string }[] = [
  { id: 'explorer',       label: 'Explorer',       icon: '🗄️', description: 'Browse raw Postgres tables' },
  { id: 'sql',            label: 'SQL Lab',         icon: '⌨️', description: 'Ad-hoc SELECT queries' },
  { id: 'notebooks',      label: 'Notebooks',       icon: '📓', description: 'Saved queries & logic' },
  { id: 'feature-maker',  label: 'Feature Maker',   icon: '🔧', description: 'Create custom data attributes' },
]

const VALID_TABS: Tab[] = ['explorer', 'sql', 'notebooks', 'feature-maker']

export default function Scribble() {
  const [searchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState<Tab>(() => {
    const param = searchParams.get('tab') as Tab | null
    return param && VALID_TABS.includes(param) ? param : 'explorer'
  })

  // Sync tab if the user navigates via the navbar mega-menu while already on this page
  useEffect(() => {
    const param = searchParams.get('tab') as Tab | null
    if (param && VALID_TABS.includes(param)) setActiveTab(param)
  }, [searchParams])
  const [pendingSql, setPendingSql] = useState('')

  function handleSaveRequest(sql: string) {
    setPendingSql(sql)
    setActiveTab('notebooks')
  }

  function handleLoadNotebook(sql: string) {
    setPendingSql('')
    setActiveTab('sql')
    // Pass SQL to SqlLab via a key reset trick — handled by SqlLab's own prop
    sessionStorage.setItem('scribble_load_sql', sql)
    window.dispatchEvent(new CustomEvent('scribble:load-sql', { detail: sql }))
  }

  return (
    <div className="page-shell full-height">
      {/* Page header */}
      <div className="scribble-topbar">
        <div className="scribble-topbar-left">
          <div className="scribble-topbar-icon">✏️</div>
          <div>
            <h1 className="scribble-page-title">Scribble</h1>
            <p className="scribble-page-subtitle">Raw data playground · Postgres explorer · SQL Lab</p>
          </div>
        </div>

        {/* Tab switcher */}
        <nav className="scribble-tabs">
          {TABS.map(tab => (
            <button
              key={tab.id}
              className={`scribble-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <span className="scribble-tab-icon">{tab.icon}</span>
              <span className="scribble-tab-label">{tab.label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      <div className="scribble-body">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className="scribble-tab-content"
        >
          {activeTab === 'explorer' && <TableBrowser />}

          {activeTab === 'sql' && (
            <SqlLab onSaveRequest={handleSaveRequest} />
          )}

          {activeTab === 'notebooks' && (
            <NotebooksPanel
              pendingSql={pendingSql}
              onClearPending={() => setPendingSql('')}
              onLoad={handleLoadNotebook}
            />
          )}

          {activeTab === 'feature-maker' && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 12, opacity: 0.6 }}>
              <span style={{ fontSize: 40 }}>🔧</span>
              <p style={{ fontWeight: 600, fontSize: '1.1rem' }}>Feature Maker — Coming Soon</p>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Create custom derived attributes from raw data columns. Use SQL Lab for now.</p>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  )
}
