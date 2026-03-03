import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useViews } from '../../hooks/useScribble'

interface ViewListPanelProps {
  open: boolean
  onClose: () => void
}

export default function ViewListPanel({ open, onClose }: ViewListPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const { views, loading, drop: dropView, refresh } = useViews()
  const [dropping, setDropping] = useState<string | null>(null)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    if (open) document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  function handleBackdropClick(e: React.MouseEvent) {
    if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
      onClose()
    }
  }

  function loadQuery(viewName: string) {
    const sql = `SELECT *\nFROM "${viewName}"\nLIMIT 50`
    sessionStorage.setItem('scribble_load_sql', sql)
    window.dispatchEvent(new CustomEvent('scribble:load-sql', { detail: sql }))
    onClose()
  }

  async function handleDrop(name: string) {
    if (!window.confirm(`Drop view "${name}"? This cannot be undone.`)) return
    setDropping(name)
    try {
      await dropView(name)
    } finally {
      setDropping(null)
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="pg-cheat-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          onClick={handleBackdropClick}
        >
          <motion.aside
            ref={panelRef}
            className="pg-cheat-panel vlp-panel"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 320, damping: 30 }}
          >
            {/* Header */}
            <div className="pg-cheat-header">
              <div className="pg-cheat-header-left">
                <span className="pg-cheat-header-icon vlp-header-icon">
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                    <rect x="1.5" y="3" width="15" height="12" rx="2" stroke="currentColor" strokeWidth="1.3"/>
                    <path d="M1.5 7h15" stroke="currentColor" strokeWidth="1.2"/>
                    <path d="M6 3v4M12 3v4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
                    <circle cx="13.5" cy="13.5" r="3" fill="var(--accent-green)" opacity=".9"/>
                    <path d="M12 13.5h3M13.5 12v3" stroke="#fff" strokeWidth="1.1" strokeLinecap="round"/>
                  </svg>
                </span>
                <div>
                  <h2 className="pg-cheat-title">View List</h2>
                  <p className="pg-cheat-subtitle">PostgreSQL views created from SQL Lab</p>
                </div>
              </div>
              <div className="vlp-header-actions">
                <button
                  className="vlp-refresh-btn"
                  onClick={refresh}
                  disabled={loading}
                  title="Refresh"
                >
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <path d="M10.5 2.5A5 5 0 1 0 11 6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                    <path d="M8.5 2.5h2v2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </button>
                <button className="pg-cheat-close" onClick={onClose} title="Close (Esc)">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Count bar */}
            <div className="vlp-count-bar">
              <span className="vlp-count-dot" />
              <span className="vlp-count-label">
                {loading ? 'Loading…' : `${views.length} view${views.length !== 1 ? 's' : ''} in public schema`}
              </span>
            </div>

            {/* Body */}
            <div className="pg-cheat-body vlp-body">
              {loading ? (
                <div className="vlp-state-msg">
                  <div className="vlp-spinner" />
                  <span>Loading views…</span>
                </div>
              ) : views.length === 0 ? (
                <div className="vlp-empty">
                  <svg width="44" height="44" viewBox="0 0 44 44" fill="none">
                    <rect x="4" y="8" width="36" height="28" rx="4" stroke="currentColor" strokeWidth="1.4" strokeDasharray="4 3" opacity=".4"/>
                    <path d="M4 16h36" stroke="currentColor" strokeWidth="1.3" opacity=".4"/>
                    <path d="M14 24h16M14 29h10" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" opacity=".3"/>
                    <circle cx="33" cy="33" r="8" fill="var(--accent-green)" opacity=".12"/>
                    <path d="M30 33h6M33 30v6" stroke="var(--accent-green)" strokeWidth="1.6" strokeLinecap="round"/>
                  </svg>
                  <p className="vlp-empty-title">No views yet</p>
                  <p className="vlp-empty-hint">
                    Write a SELECT query in the editor, then click<br/>
                    <strong>+ Create View</strong> in the toolbar to save it.
                  </p>
                </div>
              ) : (
                <div className="vlp-list">
                  {views.map(v => (
                    <div key={v.name} className="vlp-card">

                      {/* Card header row */}
                      <div className="vlp-card-header">
                        <div className="vlp-card-title-row">
                          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="vlp-card-icon">
                            <rect x="1" y="2" width="10" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
                            <path d="M1 5h10" stroke="currentColor" strokeWidth="1.1"/>
                            <circle cx="10.5" cy="1.5" r="2.5" fill="var(--accent-green)"/>
                          </svg>
                          <span className="vlp-card-name">{v.name}</span>
                          <span className="vlp-view-badge">VIEW</span>
                        </div>
                        <div className="vlp-card-actions">
                          <button
                            className="vlp-action-btn vlp-action-btn--load"
                            onClick={() => loadQuery(v.name)}
                            title="Load SELECT * FROM this view into the editor"
                          >
                            <svg width="9" height="10" viewBox="0 0 9 11" fill="currentColor">
                              <path d="M1 1l7 4.5L1 10V1z"/>
                            </svg>
                            Load
                          </button>
                          <button
                            className="vlp-action-btn vlp-action-btn--drop"
                            onClick={() => handleDrop(v.name)}
                            disabled={dropping === v.name}
                            title="Drop this view from PostgreSQL"
                          >
                            {dropping === v.name ? (
                              <span className="vlp-drop-spinner" />
                            ) : (
                              <svg width="10" height="10" viewBox="0 0 12 12" fill="none">
                                <path d="M2 3h8M5 3V2h2v1M10 3l-.7 7.3A1 1 0 018.3 11H3.7a1 1 0 01-1-.7L2 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                              </svg>
                            )}
                            {dropping === v.name ? 'Dropping…' : 'Drop'}
                          </button>
                        </div>
                      </div>

                      {/* Description */}
                      {v.description && (
                        <p className="vlp-card-desc">{v.description}</p>
                      )}

                      {/* SQL preview */}
                      <pre className="vlp-card-sql">{v.sql}</pre>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Footer hint */}
            {!loading && views.length > 0 && (
              <div className="pg-cheat-footer-note">
                <span>💡</span>
                <span>Views are real PostgreSQL views — query them with <code>SELECT * FROM view_name</code> in any SQL tool.</span>
              </div>
            )}
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
