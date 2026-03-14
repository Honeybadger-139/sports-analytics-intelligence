import { motion } from 'framer-motion'
import { useMemo } from 'react'
import { useLocation } from 'react-router-dom'
import ChatbotPanel from '../components/Chatbot/ChatbotPanel'

type ChatbotIntent = 'data-inquiry' | 'model-insight' | 'draft-help'

const INTENT_PROMPTS: Record<ChatbotIntent, string> = {
  'data-inquiry': 'Show me the top 5 NBA teams by win percentage in the current season and explain the trend briefly.',
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
        <ChatbotPanel starterKey={intent ?? undefined} starterPrompt={starterPrompt} />
      </motion.div>
    </div>
  )
}
