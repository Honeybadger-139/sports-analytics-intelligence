import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import ChatMessage from './ChatMessage'
import { useChatbot } from '../../hooks/useChatbot'

const SUGGESTED = [
  "Which NBA team has the best win rate this season?",
  "What are today's top model predictions?",
  "Explain the last prediction — what drove the outcome?",
  "Are there any current data quality issues?",
  "Summarise bankroll performance this season",
  "Which players have the highest impact on model confidence?",
]

export default function ChatbotPanel() {
  const { messages, isLoading, sendMessage, clearHistory } = useChatbot()
  const [draft, setDraft] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef    = useRef<HTMLTextAreaElement>(null)
  const hasSentOnce    = messages.length > 1

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  function autoResize() {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function submit() {
    const trimmed = draft.trim()
    if (!trimmed || isLoading) return
    sendMessage(trimmed)
    setDraft('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  function useSuggestion(q: string) {
    setDraft(q)
    textareaRef.current?.focus()
  }

  return (
    <div className="chatbot-panel">
      {/* ── Sidebar ── */}
      <aside className="chatbot-sidebar">
        <div className="chatbot-sidebar-header">
          <div className="chatbot-sidebar-dot" />
          <span>AI Assistant</span>
        </div>

        <p className="chatbot-sidebar-label">About</p>
        <p className="chatbot-sidebar-desc">
          Ask plain-English questions about your live NBA datasets, model predictions, data quality,
          and bankroll performance.
        </p>

        <p className="chatbot-sidebar-label" style={{ marginTop: 24 }}>Suggested</p>
        <div className="chatbot-suggestions">
          {SUGGESTED.map(q => (
            <button
              key={q}
              className="chatbot-suggestion-btn"
              onClick={() => useSuggestion(q)}
            >
              {q}
            </button>
          ))}
        </div>

        {hasSentOnce && (
          <button className="chatbot-clear-btn" onClick={clearHistory}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M2 2l8 8M10 2L2 10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
            Clear history
          </button>
        )}

        <div className="chatbot-sidebar-footer">
          <span className="chatbot-wip-badge">
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <circle cx="5" cy="5" r="4" stroke="currentColor" strokeWidth="1" />
              <path d="M5 2.5v2.5l1.5 1" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
            </svg>
            Backend in progress
          </span>
        </div>
      </aside>

      {/* ── Main chat area ── */}
      <div className="chatbot-main">
        {/* Header */}
        <div className="chatbot-header">
          <div className="chatbot-header-left">
            <div className="chatbot-header-icon">💬</div>
            <div>
              <h1 className="chatbot-title">Chatbot</h1>
              <p className="chatbot-subtitle">Sports Analytics AI · Powered by your live data</p>
            </div>
          </div>
          {hasSentOnce && (
            <button className="chatbot-header-clear" onClick={clearHistory} title="Clear history">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
          )}
        </div>

        {/* Messages */}
        <div className="chatbot-messages">
          <div className="chatbot-messages-inner">
            {messages.map(msg => (
              <ChatMessage key={msg.id} message={msg} />
            ))}

            <AnimatePresence>
              {isLoading && (
                <motion.div
                  className="chat-msg-row chat-msg-row--ai"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 8 }}
                  transition={{ duration: 0.18 }}
                >
                  <div className="chat-avatar">
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                      <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.3" />
                      <path d="M4.5 7h5M7 4.5v5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                    </svg>
                  </div>
                  <div className="chat-bubble chat-bubble--ai chat-bubble--typing">
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input area */}
        <div className="chatbot-input-area">
          <div className="chatbot-input-box">
            <textarea
              ref={textareaRef}
              className="chatbot-textarea"
              placeholder="Ask about teams, predictions, data quality, bankroll…"
              value={draft}
              rows={1}
              onChange={e => { setDraft(e.target.value); autoResize() }}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
            />
            <button
              className="chatbot-send-btn"
              onClick={submit}
              disabled={!draft.trim() || isLoading}
              aria-label="Send message"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M14 8L2 2l3 6-3 6 12-6z" fill="currentColor" />
              </svg>
            </button>
          </div>
          <p className="chatbot-input-hint">
            Press <kbd>Enter</kbd> to send · <kbd>Shift+Enter</kbd> for new line
          </p>
        </div>
      </div>
    </div>
  )
}
