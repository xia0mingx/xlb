import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { useCurrency } from '../currency'
import type { ChatMessage } from '../api/types'

const TRANSCRIPT_KEY = 'xlb.chat.transcript'
const AVOID_KEY = 'xlb.chat.avoid'

// Replaying the whole transcript on every turn costs tokens and eventually
// exceeds the context window, so the client keeps a bounded tail. The backend
// trims again on its side - neither end trusts the other to have done it.
const MAX_TRANSCRIPT = 40

/** Storage throws outright in private windows and embedded contexts, not merely returns null. */
function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function writeJson(key: string, value: unknown) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Non-fatal: the conversation still works for this session.
  }
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    readJson<ChatMessage[]>(TRANSCRIPT_KEY, []),
  )
  const [avoid, setAvoid] = useState<string[]>(() => readJson<string[]>(AVOID_KEY, []))
  const { currency } = useCurrency()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Held in a ref as well so send() always posts the current values without
  // being re-created on every keystroke-driven render.
  const stateRef = useRef({ messages, avoid, currency: currency.code })
  useEffect(() => {
    stateRef.current = { messages, avoid, currency: currency.code }
  }, [messages, avoid, currency.code])

  useEffect(() => {
    writeJson(TRANSCRIPT_KEY, messages.slice(-MAX_TRANSCRIPT))
  }, [messages])

  useEffect(() => {
    writeJson(AVOID_KEY, avoid)
  }, [avoid])

  const send = useCallback(async (text: string) => {
    const message = text.trim()
    if (!message || stateRef.current === null) return

    const history = stateRef.current.messages.slice(-MAX_TRANSCRIPT)
    setMessages((prev) => [...prev, { role: 'user', content: message }])
    setPending(true)
    setError(null)

    try {
      const result = await api.chat({
        message,
        history,
        avoid: stateRef.current.avoid,
        currency: stateRef.current.currency,
      })
      setMessages((prev) => [...prev, { role: 'assistant', content: result.reply }])
      // The assistant may have recorded an allergy this turn; adopt what it returned.
      setAvoid(result.avoid)
    } catch (err) {
      const detail = err instanceof Error ? err.message : 'Something went wrong.'
      setError(
        detail.includes('not configured')
          ? 'The assistant is not configured on this server yet.'
          : 'The assistant could not be reached. Please try again.',
      )
      // Drop the optimistic user turn so retrying does not duplicate it.
      setMessages((prev) => prev.slice(0, -1))
    } finally {
      setPending(false)
    }
  }, [])

  const removeAvoid = useCallback((term: string) => {
    setAvoid((prev) => prev.filter((t) => t !== term))
  }, [])

  const reset = useCallback(() => {
    setMessages([])
    setError(null)
  }, [])

  return { messages, avoid, pending, error, send, removeAvoid, reset }
}
