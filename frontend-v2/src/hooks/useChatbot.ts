import { useState, useCallback, useRef } from 'react'
import type { ChatMessage, ChatRequest, ChatResponse } from '../types'

const API_BASE = '/api/v1'

const WELCOME_MESSAGE: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content:
    "Hey! I'm your Sports Analytics AI assistant — connected to your live NBA Postgres database and news feeds.\n\nAsk me about player stats, team win rates, predictions, bankroll performance, injury reports, or game context. What would you like to explore?",
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
          const isNetworkError = (err as Error).message?.includes('Failed to fetch')
            || (err as Error).message?.includes('NetworkError')
          const errorMsg: ChatMessage = {
            id: crypto.randomUUID(),
            role: 'error',
            content: isNetworkError
              ? 'Could not reach the backend. Make sure the FastAPI server is running (`uvicorn main:app --reload` inside `backend/`).'
              : `Something went wrong: ${(err as Error).message || 'Unknown error'}. Please try again.`,
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
