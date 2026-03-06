import { useState, useCallback, useRef } from 'react'
import type { ChatMessage, ChatRequest, ChatResponse } from '../types'

const API_BASE = '/api/v1'

/** Stable per-browser session ID — persisted in localStorage for Langfuse trace grouping. */
const SESSION_STORAGE_KEY = 'sai_chat_session_id'

function getOrCreateSessionId(): string {
  try {
    const existing = localStorage.getItem(SESSION_STORAGE_KEY)
    if (existing) return existing
    const id = crypto.randomUUID()
    localStorage.setItem(SESSION_STORAGE_KEY, id)
    return id
  } catch {
    return 'anonymous'
  }
}

const WELCOME_MESSAGE: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content:
    "Hey! I'm your GameThread assistant — connected to your live NBA Postgres database and news feeds.\n\nAsk me about player stats, team win rates, predictions, bankroll performance, injury reports, or game context. What would you like to explore?",
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

type StreamHandlers = {
  onToken: (token: string) => void
  onDone: (payload: ChatResponse) => void
}

async function postChatStream(
  payload: ChatRequest,
  signal: AbortSignal,
  handlers: StreamHandlers
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  if (!res.body) throw new Error('Streaming response body unavailable')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const parseFrame = (frame: string) => {
    let event = 'message'
    let data = ''
    for (const line of frame.split('\n')) {
      if (line.startsWith('event:')) {
        event = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        data += line.slice(5).trim()
      }
    }
    if (!data) return

    const payloadData = JSON.parse(data) as { token?: string; reply?: string; message?: string }
    if (event === 'token' && payloadData.token) {
      handlers.onToken(payloadData.token)
      return
    }
    if (event === 'done') {
      handlers.onDone({ reply: payloadData.reply || '' })
      return
    }
    if (event === 'error') {
      throw new Error(payloadData.message || 'Streaming failed')
    }
  }

  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })

    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary).trim()
      buffer = buffer.slice(boundary + 2)
      if (frame) parseFrame(frame)
      boundary = buffer.indexOf('\n\n')
    }

    if (done) break
  }
}

export function useChatbot() {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE])
  const [isLoading, setIsLoading] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const sessionIdRef = useRef<string>(getOrCreateSessionId())

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

        const assistantMsgId = crypto.randomUUID()
        const assistantMsg: ChatMessage = {
          id: assistantMsgId,
          role: 'assistant',
          content: '',
          timestamp: new Date().toISOString(),
        }
        setMessages(prev => [...prev, assistantMsg])

        try {
          await postChatStream(
            { message: content.trim(), history, session_id: sessionIdRef.current },
            ctrl.signal,
            {
              onToken: (token) => {
                setMessages(prev =>
                  prev.map(msg =>
                    msg.id === assistantMsgId
                      ? { ...msg, content: msg.content + token }
                      : msg
                  )
                )
              },
              onDone: (payload) => {
                if (!payload.reply) return
                setMessages(prev =>
                  prev.map(msg =>
                    msg.id === assistantMsgId
                      ? { ...msg, content: payload.reply }
                      : msg
                  )
                )
              },
            }
          )
        } catch (streamErr) {
          // Backward-compatible fallback to non-stream endpoint if stream is unavailable.
          const streamHttp404 = (streamErr as Error).message?.includes('HTTP 404')
          if (!streamHttp404) throw streamErr

          const res = await postChat(
            { message: content.trim(), history, session_id: sessionIdRef.current },
            ctrl.signal
          )
          setMessages(prev =>
            prev.map(msg =>
              msg.id === assistantMsgId
                ? { ...msg, content: res.reply }
                : msg
            )
          )
        }
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
          setMessages(prev => {
            const trimmed = [...prev]
            const last = trimmed[trimmed.length - 1]
            if (last?.role === 'assistant' && !last.content.trim()) {
              trimmed.pop()
            }
            return [...trimmed, errorMsg]
          })
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
