import { motion } from 'framer-motion'
import type { ChatMessage as ChatMessageType } from '../../types'

interface Props {
  message: ChatMessageType
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function ChatMessage({ message }: Props) {
  const isUser      = message.role === 'user'
  const isError     = message.role === 'error'

  return (
    <motion.div
      className={`chat-msg-row ${isUser ? 'chat-msg-row--user' : 'chat-msg-row--ai'}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: 'easeOut' }}
    >
      {!isUser && (
        <div className="chat-avatar">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.3" />
            <path d="M4.5 7h5M7 4.5v5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
        </div>
      )}

      <div className={`chat-bubble ${isUser ? 'chat-bubble--user' : isError ? 'chat-bubble--error' : 'chat-bubble--ai'}`}>
        {isError && (
          <div className="chat-bubble-error-label">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.2" />
              <path d="M6 4v3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
              <circle cx="6" cy="8.5" r="0.6" fill="currentColor" />
            </svg>
            Backend unavailable
          </div>
        )}
        <p className="chat-bubble-text">{message.content}</p>
        <span className="chat-bubble-time">{formatTime(message.timestamp)}</span>
      </div>

      {isUser && (
        <div className="chat-avatar chat-avatar--user">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <circle cx="6" cy="4" r="2.2" stroke="currentColor" strokeWidth="1.2" />
            <path d="M1.5 10.5C1.5 8.57 3.57 7 6 7s4.5 1.57 4.5 3.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
        </div>
      )}
    </motion.div>
  )
}
