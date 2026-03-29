import { motion } from 'framer-motion'
import type { ChatMessage as ChatMessageType } from '../../types'
import styles from './Chatbot.module.css'

interface Props {
  message: ChatMessageType
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const compactNumberFormatter = new Intl.NumberFormat('en-US', {
  maximumFractionDigits: 3,
})

function formatNumber(value: number): string {
  const formatted = compactNumberFormatter.format(value)
  return formatted === '-0' ? '0' : formatted
}

function formatNumericLikeString(value: string): string | null {
  const trimmed = value.trim()
  if (!trimmed) return null

  const looksDecimal = trimmed.includes('.') || /e/i.test(trimmed)
  if (!looksDecimal) return null

  const normalized = trimmed.replace(/,/g, '')
  const parsed = Number(normalized)
  if (!Number.isFinite(parsed)) return null

  return formatNumber(parsed)
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'number') {
    return Number.isInteger(value) ? value.toString() : formatNumber(value)
  }
  if (typeof value === 'string') {
    const formatted = formatNumericLikeString(value)
    return formatted ?? value
  }
  return String(value)
}

export default function ChatMessage({ message }: Props) {
  const isUser  = message.role === 'user'
  const isError = message.role === 'error'
  const hasTable = !isUser && !isError && !!message.table && message.table.rows.length > 0
  const keyNumbers = !isUser && !isError ? (message.key_numbers ?? []) : []
  const sources = !isUser && !isError ? (message.sources ?? []) : []

  const bubbleClass = isUser
    ? styles['chat-bubble--user']
    : isError
      ? styles['chat-bubble--error']
      : styles['chat-bubble--ai']

  return (
    <motion.div
      className={`${styles['chat-msg-row']} ${isUser ? styles['chat-msg-row--user'] : styles['chat-msg-row--ai']}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: 'easeOut' }}
    >
      {!isUser && (
        <div className={styles['chat-avatar']}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.3" />
            <path d="M4.5 7h5M7 4.5v5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
        </div>
      )}

      <div className={`${styles['chat-bubble']} ${bubbleClass}`}>
        {isError && (
          <div className={styles['chat-bubble-error-label']}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.2" />
              <path d="M6 4v3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
              <circle cx="6" cy="8.5" r="0.6" fill="currentColor" />
            </svg>
            Backend unavailable
          </div>
        )}
        <p className={styles['chat-bubble-text']}>{message.content}</p>
        {keyNumbers.length > 0 && (
          <div className={styles['chat-key-numbers']}>
            {keyNumbers.slice(0, 5).map((item, index) => (
              <div key={`${item.label}-${index}`} className={styles['chat-key-number']}>
                <span className={styles['chat-key-number-label']}>{item.label}</span>
                <span className={styles['chat-key-number-value']}>{formatValue(item.value)}</span>
              </div>
            ))}
          </div>
        )}
        {hasTable && (
          <div className={styles['chat-table-wrap']}>
            <table className={styles['chat-table']}>
              <thead>
                <tr>
                  {message.table?.columns.map((col) => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {message.table?.rows.slice(0, 10).map((row, rowIndex) => (
                  <tr key={`row-${rowIndex}`}>
                    {message.table?.columns.map((col) => (
                      <td key={`${rowIndex}-${col}`}>{formatValue(row[col])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {typeof message.table?.row_count === 'number' && message.table.row_count > 10 && (
              <p className={styles['chat-table-note']}>Showing first 10 rows of {message.table.row_count}.</p>
            )}
          </div>
        )}
        {sources.length > 0 && (
          <div className={styles['chat-sources']}>
            <p className={styles['chat-sources-label']}>Sources</p>
            {sources.slice(0, 3).map((src, idx) => (
              src.url ? (
                <a
                  key={`${src.title}-${idx}`}
                  href={src.url}
                  target="_blank"
                  rel="noreferrer"
                  className={styles['chat-source-link']}
                >
                  {src.title}
                </a>
              ) : (
                <span key={`${src.title}-${idx}`} className={styles['chat-source-link']}>{src.title}</span>
              )
            ))}
          </div>
        )}
        {!isUser && !isError && typeof message.confidence === 'number' && (
          <div className={styles['chat-metadata-line']}>
            confidence {Math.round(message.confidence * 100)}%
          </div>
        )}
        <span className={styles['chat-bubble-time']}>{formatTime(message.timestamp)}</span>
      </div>

      {isUser && (
        <div className={`${styles['chat-avatar']} ${styles['chat-avatar--user']}`}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <circle cx="6" cy="4" r="2.2" stroke="currentColor" strokeWidth="1.2" />
            <path d="M1.5 10.5C1.5 8.57 3.57 7 6 7s4.5 1.57 4.5 3.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
        </div>
      )}
    </motion.div>
  )
}
