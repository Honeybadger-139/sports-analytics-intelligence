import { useState, useEffect, useRef } from 'react'
import type { ViewCreateRequest } from '../../types'

interface CreateViewModalProps {
  /** The SQL currently in the editor — pre-filled as the view body */
  initialSql: string
  onConfirm: (payload: ViewCreateRequest) => Promise<void>
  onClose: () => void
}

/** Normalise an arbitrary string into a valid PG view name (lowercase, underscores) */
function slugify(str: string): string {
  return str
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 63)
}

export default function CreateViewModal({ initialSql, onConfirm, onClose }: CreateViewModalProps) {
  const [name, setName]               = useState('')
  const [description, setDescription] = useState('')
  const [sql, setSql]                 = useState(initialSql)
  const [submitting, setSubmitting]   = useState(false)
  const [error, setError]             = useState<string | null>(null)
  const nameRef = useRef<HTMLInputElement>(null)

  // Auto-focus name field on mount
  useEffect(() => {
    nameRef.current?.focus()
  }, [])

  // Dismiss on Escape key
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const sluggedName = slugify(name)
  const nameValid = sluggedName.length > 0

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!nameValid || !sql.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      await onConfirm({ name: sluggedName, description: description.trim(), sql: sql.trim() })
      onClose()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="cvm-backdrop" onClick={onClose}>
      <div className="cvm-modal" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="cvm-title">

        {/* Header */}
        <div className="cvm-header">
          <div className="cvm-header-left">
            <svg className="cvm-header-icon" viewBox="0 0 20 20" fill="none">
              <path d="M3 5h14M3 10h14M3 15h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              <circle cx="16" cy="15" r="3" fill="var(--accent-green)" opacity=".9"/>
              <path d="M15 15h2M16 14v2" stroke="#fff" strokeWidth="1.2" strokeLinecap="round"/>
            </svg>
            <h2 className="cvm-title" id="cvm-title">Create PostgreSQL View</h2>
          </div>
          <button className="cvm-close" onClick={onClose} aria-label="Close">
            <svg viewBox="0 0 16 16" fill="none">
              <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        {/* Explanation pill */}
        <div className="cvm-info-bar">
          <svg viewBox="0 0 16 16" fill="none" className="cvm-info-icon">
            <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.2"/>
            <path d="M8 7v4M8 5.5v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <span>The view will be created in your PostgreSQL <code>public</code> schema and is immediately queryable from the SQL editor.</span>
        </div>

        <form className="cvm-form" onSubmit={handleSubmit}>

          {/* View name */}
          <label className="cvm-label">
            <span className="cvm-label-text">View name <span className="cvm-required">*</span></span>
            <input
              ref={nameRef}
              className="cvm-input"
              placeholder="e.g. top_scorers_2025"
              value={name}
              onChange={e => setName(e.target.value)}
              autoComplete="off"
              spellCheck={false}
              maxLength={80}
            />
            {name && (
              <span className={`cvm-slug-preview ${nameValid ? 'ok' : 'err'}`}>
                → stored as: <code>{sluggedName || '(invalid)'}</code>
              </span>
            )}
          </label>

          {/* Description */}
          <label className="cvm-label">
            <span className="cvm-label-text">Description <span className="cvm-optional">(optional)</span></span>
            <input
              className="cvm-input"
              placeholder="Briefly describe what this view contains"
              value={description}
              onChange={e => setDescription(e.target.value)}
              maxLength={500}
            />
          </label>

          {/* SQL body */}
          <label className="cvm-label cvm-label--sql">
            <span className="cvm-label-text">View definition (SELECT query) <span className="cvm-required">*</span></span>
            <textarea
              className="cvm-textarea"
              value={sql}
              onChange={e => setSql(e.target.value)}
              spellCheck={false}
              rows={9}
            />
            <span className="cvm-sql-hint">Only SELECT / WITH queries are allowed. LIMIT clauses are stripped for view definitions.</span>
          </label>

          {/* Error */}
          {error && (
            <div className="cvm-error">
              <svg viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.2"/>
                <path d="M8 5v4M8 11.5v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="cvm-actions">
            <button type="button" className="cvm-btn cvm-btn--cancel" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button
              type="submit"
              className="cvm-btn cvm-btn--create"
              disabled={!nameValid || !sql.trim() || submitting}
            >
              {submitting ? (
                <>
                  <span className="cvm-spinner" />
                  Creating…
                </>
              ) : (
                <>
                  <svg viewBox="0 0 16 16" fill="none">
                    <circle cx="8" cy="8" r="7" fill="var(--accent-green)" opacity=".2"/>
                    <path d="M5 8l2 2 4-4" stroke="var(--accent-green)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Create View
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
