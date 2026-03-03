import { useState } from 'react'
import { motion } from 'framer-motion'
import TableBrowser   from '../components/Scribble/TableBrowser'
import SqlLab         from '../components/Scribble/SqlLab'
import NotebooksPanel from '../components/Scribble/NotebooksPanel'

type Tab = 'explorer' | 'sql' | 'notebooks'

const TABS: { id: Tab; label: string; icon: string; description: string }[] = [
  { id: 'explorer',   label: 'Explorer',   icon: '🗄️', description: 'Browse raw Postgres tables' },
  { id: 'sql',        label: 'SQL Lab',    icon: '⌨️', description: 'Ad-hoc SELECT queries' },
  { id: 'notebooks',  label: 'Notebooks',  icon: '📓', description: 'Saved queries & logic' },
]

export default function Scribble() {
  const [activeTab, setActiveTab] = useState<Tab>('explorer')
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
    <div className="page-shell scribble-shell">
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
          style={{ height: '100%' }}
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
        </motion.div>
      </div>
    </div>
  )
}
