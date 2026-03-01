import { useState, useCallback, useRef } from 'react'
import type { ChatMessage, ChatRequest, ChatResponse } from '../types'

const API_BASE = '/api/v1'

const WELCOME_MESSAGE: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content:
    "Hey! I'm your Sports Analytics AI assistant. Ask me anything about your NBA data — predictions, team performance, model explanations, data quality, or bankroll stats. What would you like to explore?",
  timestamp: new Date().toISOString(),
}

async function postChat(payload: ChatRequest, signal: AbortSignal): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export function useChatbot() {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE])
  const [isLoading, setIsLoading] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return

      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content: content.trim(),
        timestamp: new Date().toISOString(),
      }

      setMessages(prev => [...prev, userMsg])
      setIsLoading(true)

      if (abortRef.current) abortRef.current.abort()
      const ctrl = new AbortController()
      abortRef.current = ctrl

      try {
        const history = messages
          .filter(m => m.role !== 'error')
          .map(m => ({ role: m.role as 'user' | 'assistant', content: m.content }))

        const res = await postChat(
          { message: content.trim(), history },
          ctrl.signal
        )

        const assistantMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: res.reply,
          timestamp: new Date().toISOString(),
        }
        setMessages(prev => [...prev, assistantMsg])
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          const errorMsg: ChatMessage = {
            id: crypto.randomUUID(),
            role: 'error',
            content:
              'Backend integration is still in progress. The `/api/v1/chat` endpoint is not yet available. In the meantime, I can tell you that your RAG intelligence layer and PostgreSQL datasets are ready to be wired up.',
            timestamp: new Date().toISOString(),
          }
          setMessages(prev => [...prev, errorMsg])
        }
      } finally {
        setIsLoading(false)
      }
    },
    [messages, isLoading]
  )

  const clearHistory = useCallback(() => {
    if (abortRef.current) abortRef.current.abort()
    setMessages([WELCOME_MESSAGE])
    setIsLoading(false)
  }, [])

  return { messages, isLoading, sendMessage, clearHistory }
}
