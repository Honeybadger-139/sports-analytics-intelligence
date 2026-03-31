import { motion } from 'framer-motion'
import { useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ChatbotPanel from '../components/Chatbot/ChatbotPanel'

const ACCENT = 'var(--accent-chat)'

const CHATBOT_TABS = [
  { label: 'Data Inquiry',  path: '/chatbot' },
  { label: 'Model Insight', path: '/chatbot/model-insight' },
  { label: 'Draft Help',    path: '/chatbot/draft-help' },
]

type ChatbotIntent = 'data-inquiry' | 'model-insight' | 'draft-help'

const INTENT_PROMPTS: Record<ChatbotIntent, string> = {
  'data-inquiry': 'Show me the top 5 NBA teams by win rate in the current season and explain the trend briefly.',
  'model-insight': 'For today’s highest-confidence game prediction, explain the key model drivers and confidence risks.',
  'draft-help': 'Compare two high-impact players by recent points, rebounds, assists, and consistency so I can evaluate draft value.',
}

function resolveIntent(search: string): ChatbotIntent | null {
  const intent = new URLSearchParams(search).get('intent')
  if (intent === 'data-inquiry' || intent === 'model-insight' || intent === 'draft-help') {
    return intent
  }
  return null
}

export default function Chatbot() {
  const location = useLocation()
  const navigate = useNavigate()
  const intent = useMemo(() => resolveIntent(location.search), [location.search])
  const starterPrompt = intent ? INTENT_PROMPTS[intent] : undefined

  return (
    <div className="page-shell full-height">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3 }}
        style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}
      >
        {/* Tab strip — consistent across all three chatbot sub-pages */}
        <div style={{ display: 'flex', gap: 2, padding: '12px 20px 0', background: 'var(--bg-panel)', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
          {CHATBOT_TABS.map(tab => {
            const active = location.pathname === tab.path
            return (
              <button
                key={tab.path}
                onClick={() => navigate(tab.path)}
                style={{
                  padding: '6px 14px', borderRadius: '6px 6px 0 0',
                  border: 'none', cursor: 'pointer',
                  background: active ? 'var(--bg-base)' : 'transparent',
                  color: active ? ACCENT : 'var(--text-2)',
                  fontWeight: 600, fontSize: '0.7rem',
                  textTransform: 'uppercase', letterSpacing: '0.05em',
                  borderBottom: active ? `2px solid ${ACCENT}` : '2px solid transparent',
                  transition: 'all 0.15s',
                }}
              >
                {tab.label}
              </button>
            )
          })}
        </div>

        <ChatbotPanel starterKey={intent ?? undefined} starterPrompt={starterPrompt} />
      </motion.div>
    </div>
  )
}
