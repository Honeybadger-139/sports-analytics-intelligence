import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useNotebooks } from '../../hooks/useScribble'
import type { SavedNotebook } from '../../types'

const ACCENT = '#10B981'

interface NotebooksPanelProps {
  /** Pre-filled SQL when saving from SQL Lab */
  pendingSql: string
  onClearPending: () => void
  /** Load a saved query into SQL Lab */
  onLoad: (sql: string) => void
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function NotebooksPanel({ pendingSql, onClearPending, onLoad }: NotebooksPanelProps) {
  const { notebooks, save, remove } = useNotebooks()
  const [showSaveForm, setShowSaveForm] = useState(!!pendingSql)
  const [saveName, setSaveName] = useState('')
  const [saveDesc, setSaveDesc] = useState('')
  const [saveSql, setSaveSql] = useState(pendingSql)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  function openSaveForm(sql = '') {
    setSaveSql(sql)
    setSaveName('')
    setSaveDesc('')
    setShowSaveForm(true)
  }

  function handleSave() {
    if (!saveSql.trim()) return
    save(saveName, saveDesc, saveSql)
    setShowSaveForm(false)
    setSaveName('')
    setSaveDesc('')
    setSaveSql('')
    onClearPending()
  }

  function handleLoad(nb: SavedNotebook) {
    onLoad(nb.sql)
  }

  return (
    <div className="notebooks-layout">
      {/* Header */}
      <div className="notebooks-header">
        <div>
          <h2 className="notebooks-title">Saved Notebooks</h2>
          <p className="notebooks-subtitle">{notebooks.length} saved {notebooks.length === 1 ? 'query' : 'queries'}</p>
        </div>
        <button className="notebooks-new-btn" onClick={() => openSaveForm('')}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M6 1v10M1 6h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          New notebook
        </button>
      </div>

      {/* Save form */}
      <AnimatePresence>
        {showSaveForm && (
          <motion.div
            className="notebooks-save-form"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
          >
            <div className="save-form-inner">
              <p className="save-form-title">
                {pendingSql ? 'Save from SQL Lab' : 'New Notebook'}
              </p>
              <input
                className="scribble-input"
                placeholder="Notebook name (e.g. Top Scorers Query)"
                value={saveName}
                onChange={e => setSaveName(e.target.value)}
              />
              <input
                className="scribble-input"
                placeholder="Description (optional)"
                value={saveDesc}
                onChange={e => setSaveDesc(e.target.value)}
              />
              <textarea
                className="save-form-sql"
                placeholder="SELECT ..."
                value={saveSql}
                onChange={e => setSaveSql(e.target.value)}
                rows={4}
                spellCheck={false}
              />
              <div className="save-form-actions">
                <button
                  className="save-form-cancel"
                  onClick={() => { setShowSaveForm(false); onClearPending() }}
                >
                  Cancel
                </button>
                <button
                  className="save-form-submit"
                  onClick={handleSave}
                  disabled={!saveSql.trim()}
                >
                  Save notebook
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Notebook list */}
      {notebooks.length === 0 && !showSaveForm ? (
        <div className="notebooks-empty">
          <div className="notebooks-empty-icon">📓</div>
          <p className="notebooks-empty-title">No saved notebooks yet</p>
          <p className="notebooks-empty-desc">
            Write a query in the SQL Lab and click <strong>Save</strong> to preserve it here.
          </p>
          <button className="notebooks-new-btn" onClick={() => openSaveForm('')}>
            Create your first notebook
          </button>
        </div>
      ) : (
        <div className="notebooks-list">
          {notebooks.map(nb => (
            <div key={nb.id} className="notebook-card">
              <div
                className="notebook-card-header"
                onClick={() => setExpandedId(id => id === nb.id ? null : nb.id)}
              >
                <div className="notebook-card-left">
                  <span className="notebook-card-icon">📓</span>
                  <div>
                    <p className="notebook-card-name">{nb.name}</p>
                    {nb.description && (
                      <p className="notebook-card-desc">{nb.description}</p>
                    )}
                    <p className="notebook-card-date">{formatDate(nb.savedAt)}</p>
                  </div>
                </div>
                <div className="notebook-card-actions">
                  <button
                    className="notebook-action-btn"
                    style={{ color: ACCENT }}
                    onClick={e => { e.stopPropagation(); handleLoad(nb) }}
                    title="Load into SQL Lab"
                  >
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M2 2l8 4-8 4V2z" fill="currentColor" />
                    </svg>
                    Load
                  </button>
                  <button
                    className="notebook-action-btn notebook-action-btn--delete"
                    onClick={e => { e.stopPropagation(); remove(nb.id) }}
                    title="Delete notebook"
                  >
                    <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                      <path d="M1.5 1.5l8 8M9.5 1.5l-8 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                    </svg>
                  </button>
                </div>
              </div>

              <AnimatePresence>
                {expandedId === nb.id && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.18 }}
                    className="notebook-card-sql-wrap"
                  >
                    <pre className="notebook-card-sql">{nb.sql}</pre>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
