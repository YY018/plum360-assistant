import { useCallback, useRef, useState } from 'react'
import { API_BASE, API_LABEL, accessCode } from './api'

const API_URL = `${API_BASE}/chat/stream`
const HISTORY_LIMIT = 16

// Reads an NDJSON response body and calls onEvent for every parsed line.
async function readEvents(response, onEvent) {
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
    const lines = buffer.split('\n')
    buffer = lines.pop()
    for (const line of lines) {
      if (line.trim()) onEvent(JSON.parse(line))
    }
    if (done) break
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer))
}

let nextId = 1

/**
 * Conversation state and streaming for the assistant. Lives at the app root
 * so the conversation (and any in-flight answer) survives page navigation.
 */
export function useChat() {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const messagesRef = useRef(messages)
  const loadingRef = useRef(false)
  const abortRef = useRef(null)

  // No abort-on-unmount here: this hook lives at the app root, and React's
  // development double-mount would otherwise cancel a question asked from the
  // URL right after it starts.
  messagesRef.current = messages

  const patchMessage = (id, patch) =>
    setMessages((previous) =>
      previous.map((message) => (message.id === id ? { ...message, ...patch } : message)),
    )

  const ask = useCallback(async (question) => {
    const trimmed = (question || '').trim()
    if (!trimmed || loadingRef.current) return false

    // The API is stateless: send prior completed turns as history.
    const history = messagesRef.current
      .filter((message) => !message.error && !message.streaming && message.content)
      .map(({ role, content }) => ({ role, content }))
      .slice(-HISTORY_LIMIT)

    const id = nextId++
    setMessages((previous) => [
      ...previous,
      { id: nextId++, role: 'user', content: trimmed },
      { id, role: 'assistant', content: '', stage: 'thinking', streaming: true },
    ])
    loadingRef.current = true
    setLoading(true)

    const controller = new AbortController()
    abortRef.current = controller

    // Models send text in bursts; reveal it at a steady pace that speeds up
    // when the display falls behind.
    const typing = { target: '', shown: 0, final: null, frame: 0 }

    const finish = (patch) => {
      cancelAnimationFrame(typing.frame)
      patchMessage(id, { streaming: false, ...patch })
      loadingRef.current = false
      setLoading(false)
      abortRef.current = null
    }

    const tick = () => {
      const remaining = typing.target.length - typing.shown
      if (remaining > 0) {
        typing.shown += Math.max(2, Math.ceil(remaining / 14))
        patchMessage(id, { content: typing.target.slice(0, typing.shown) })
      }
      if (typing.final && typing.shown >= typing.target.length) {
        finish(typing.final)
        return
      }
      typing.frame = requestAnimationFrame(tick)
    }

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(accessCode() ? { 'X-Access-Code': accessCode() } : {}),
        },
        body: JSON.stringify({ question: trimmed, history }),
        signal: controller.signal,
      })
      if (!response.ok || !response.body) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || `The server responded with ${response.status}.`)
      }

      typing.frame = requestAnimationFrame(tick)
      let failure = null

      await readEvents(response, (event) => {
        if (event.type === 'status') {
          patchMessage(id, { stage: event.stage })
        } else if (event.type === 'token') {
          typing.target += event.text
        } else if (event.type === 'error') {
          failure = event.message
        } else if (event.type === 'done') {
          const answer = event.answer || 'No answer was returned.'
          // The final answer is authoritative. If it only extends what was
          // streamed, keep typing; if the server replaced it, show it at once.
          if (!answer.startsWith(typing.target.slice(0, typing.shown))) {
            typing.shown = answer.length
          }
          typing.target = answer
          typing.final = {
            content: answer,
            citations: event.citations || [],
            sources: event.sources || [],
            notice: event.safety_message || '',
          }
        }
      })

      if (failure) {
        finish({ content: failure, error: true })
      } else if (!typing.final) {
        finish({ content: 'The response ended unexpectedly. Please try again.', error: true })
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        finish({ content: typing.target.slice(0, typing.shown), stopped: true })
        return true
      }
      const content =
        error instanceof TypeError
          ? `Could not reach the assistant API at ${API_LABEL}. Is the backend running?`
          : error.message
      finish({ content, error: true })
    }
    return true
  }, [])

  const stop = useCallback(() => abortRef.current?.abort(), [])
  const reset = useCallback(() => {
    if (!loadingRef.current) setMessages([])
  }, [])

  return { messages, loading, ask, stop, reset }
}
