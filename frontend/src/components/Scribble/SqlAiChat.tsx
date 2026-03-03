import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useAiSql, type AiMessage } from '../../hooks/useScribble'

const SUGGESTIONS = [
  'Top 10 players by points per game this season',
  'Show me the last 20 completed games with scores',
  'Which team has the best win rate in 2025-26?',
  'Players with more than 5 assists per game this season',
  'Head-to-head record between Lakers and Celtics',
  'Show model predictions with confidence above 80%',
]

interface SqlAiChatProps {
  open: boolean
  onClose: () => void
  /** Called when user hits "Load" on an AI-generated SQL */
  onLoadSql: (sql: string) => void
}

function LoadIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 12" fill="currentColor" aria-hidden>
      <path d="M1 1l8 5-8 5V1z" />
    </svg>
  )
}

function CopyIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 12 12" fill="none" aria-hidden>
      <rect x="4" y="4" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.1" />
      <path d="M1 8V2a1 1 0 011-1h6" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
    </svg>
  )
}

function MessageBubble({
  msg,
  onLoad,
}: {
  msg: AiMessage
  onLoad: (sql: string) => void
}) {
  const [copied, setCopied] = useState(false)

  function handleCopy(sql: string) {
    navigator.clipboard.writeText(sql).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    })
  }

  if (msg.role === 'user') {
    return (
      <motion.div
        className="sac-row sac-row--user"
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.16 }}
      >
        <div className="sac-bubble sac-bubble--user">{msg.content}</div>
      </motion.div>
    )
  }

  if (msg.role === 'error') {
    return (
      <motion.div
        className="sac-row sac-row--error"
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.16 }}
      >
        <div className="sac-error-bubble">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <circle cx="6" cy="6" r="5.25" stroke="currentColor" strokeWidth="1.2" />
            <path d="M6 4v2.5M6 8.5v.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
          {msg.content}
        </div>
      </motion.div>
    )
  }

  // Assistant message
  return (
    <motion.div
      className="sac-row sac-row--ai"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.16 }}
    >
      <div className="sac-avatar">
        <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
          <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.3" />
          <path d="M4 7h6M7 4v6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
        </svg>
      </div>
      <div className="sac-ai-content">
        {msg.content && <p className="sac-explanation">{msg.content}</p>}
        {msg.sql && (
          <div className="sac-sql-block">
            <div className="sac-sql-header">
              <span className="sac-sql-label">SQL</span>
              <div className="sac-sql-actions">
                <button
                  className="sac-sql-action-btn"
                  onClick={() => handleCopy(msg.sql!)}
                  title="Copy SQL"
                >
                  <CopyIcon />
                  {copied ? 'Copied!' : 'Copy'}
                </button>
                <button
                  className="sac-sql-action-btn sac-sql-action-btn--load"
                  onClick={() => onLoad(msg.sql!)}
                  title="Load into editor"
                >
                  <LoadIcon />
                  Load into editor
                </button>
              </div>
            </div>
            <pre className="sac-sql-code">{msg.sql}</pre>
          </div>
        )}
      </div>
    </motion.div>
  )
}

export default function SqlAiChat({ open, onClose, onLoadSql }: SqlAiChatProps) {
  const { messages, loading, send, clear } = useAiSql()
  const [draft, setDraft] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef    = useRef<HTMLTextAreaElement>(null)
  const panelRef       = useRef<HTMLDivElement>(null)
  const hasMsgs        = messages.length > 0

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  useEffect(() => {
    function onKey(e: globalThis.KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    if (open) window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  // Auto-focus textarea when panel opens
  useEffect(() => {
    if (open) setTimeout(() => textareaRef.current?.focus(), 150)
  }, [open])

  function autoResize() {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function submit() {
    const t = draft.trim()
    if (!t || loading) return
    send(t)
    setDraft('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  function handleLoad(sql: string) {
    onLoadSql(sql)
    onClose()
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          ref={panelRef}
          className="sac-panel"
          initial={{ x: '100%', opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: '100%', opacity: 0 }}
          transition={{ type: 'spring', stiffness: 340, damping: 32 }}
        >
          {/* ── Header ── */}
          <div className="sac-header">
            <div className="sac-header-left">
              <div className="sac-header-dot-ring">
                <span className="sac-header-dot" />
              </div>
              <div>
                <h2 className="sac-title">SQL Assistant</h2>
                <p className="sac-subtitle">Describe what you need — AI writes the query</p>
              </div>
            </div>
            <div className="sac-header-right">
              {hasMsgs && (
                <button className="sac-clear-btn" onClick={clear} title="Clear conversation">
                  <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
                    <path d="M2 2l8 8M10 2L2 10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                  </svg>
                </button>
              )}
              <button className="sac-close-btn" onClick={onClose} title="Close (Esc)">
                <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                  <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                </svg>
              </button>
            </div>
          </div>

          {/* ── Badge row ── */}
          <div className="sac-badge-row">
            <span className="sac-live-badge">
              <span className="sac-live-dot" />
              Schema-aware · Gemini
            </span>
            <span className="sac-schema-badge">9 tables · live columns</span>
          </div>

          {/* ── Messages or Welcome ── */}
          <div className="sac-body">
            {!hasMsgs ? (
              <div className="sac-welcome">
                <div className="sac-welcome-icon">
                  <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                    <circle cx="16" cy="16" r="14" stroke="currentColor" strokeWidth="1.4" opacity=".25" />
                    <path d="M10 16h12M16 10v12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" opacity=".6" />
                    <circle cx="16" cy="16" r="3" fill="var(--accent-green)" opacity=".8" />
                  </svg>
                </div>
                <p className="sac-welcome-title">Ask anything about your NBA data</p>
                <p className="sac-welcome-hint">
                  The AI knows your exact tables and columns —<br/>every query it writes will run against your live database.
                </p>
                <div className="sac-suggestions">
                  {SUGGESTIONS.map(s => (
                    <button
                      key={s}
                      className="sac-suggestion"
                      onClick={() => { setDraft(s); textareaRef.current?.focus() }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="sac-messages">
                {messages.map(msg => (
                  <MessageBubble key={msg.id} msg={msg} onLoad={handleLoad} />
                ))}
                <AnimatePresence>
                  {loading && (
                    <motion.div
                      className="sac-row sac-row--ai"
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                    >
                      <div className="sac-avatar">
                        <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                          <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.3" />
                          <path d="M4 7h6M7 4v6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                        </svg>
                      </div>
                      <div className="sac-typing">
                        <span className="sac-typing-dot" />
                        <span className="sac-typing-dot" />
                        <span className="sac-typing-dot" />
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* ── Input ── */}
          <div className="sac-input-area">
            <div className="sac-input-box">
              <textarea
                ref={textareaRef}
                className="sac-textarea"
                placeholder="e.g. Top 5 scorers in 2024-25 with team names"
                value={draft}
                rows={1}
                onChange={e => { setDraft(e.target.value); autoResize() }}
                onKeyDown={handleKeyDown}
                disabled={loading}
              />
              <button
                className="sac-send-btn"
                onClick={submit}
                disabled={!draft.trim() || loading}
                aria-label="Generate SQL"
              >
                {loading ? (
                  <span className="sac-send-spinner" />
                ) : (
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                    <path d="M14 8L2 2l3 6-3 6 12-6z" fill="currentColor" />
                  </svg>
                )}
              </button>
            </div>
            <p className="sac-input-hint">
              <kbd>Enter</kbd> generate · <kbd>Shift+Enter</kbd> new line · Click <strong>Load</strong> to send SQL to editor
            </p>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
