import { useEffect, useRef } from 'react'

import { AgentMark } from './AgentMark'
import { ChatThread, Composer, DISCLAIMER } from './Chat'
import { Icon } from './Icons'

/** Slide-in chat panel shown over the product guide. */
export function ChatDrawer({ open, chat, onClose }) {
  const { messages, loading, ask, stop, reset } = chat
  const panelRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => {
      // The manual viewer handles Escape itself when it is open on top.
      if (event.key === 'Escape' && !document.querySelector('.viewer')) onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return (
    <aside
      ref={panelRef}
      className={`drawer${open ? ' is-open' : ''}`}
      aria-label="Plum 360 assistant"
      aria-hidden={!open}
      inert={open ? undefined : ''}
    >
      <header className="drawer-header">
        <div className="drawer-title">
          <AgentMark size={18} active={loading} />
          <span>Manual assistant</span>
        </div>
        <div className="drawer-actions">
          {messages.length > 0 && (
            <button type="button" className="text-button" onClick={reset} disabled={loading}>
              Clear
            </button>
          )}
          <a className="icon-button" href="#/assistant" title="Open full page" aria-label="Open full page">
            <Icon name="expand" size={16} />
          </a>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close assistant">
            <Icon name="close" size={16} />
          </button>
        </div>
      </header>
      <div className="drawer-thread" aria-live="polite">
        <ChatThread messages={messages} loading={loading} onAsk={ask} compact />
      </div>
      <footer className="drawer-footer">
        <Composer loading={loading} onAsk={ask} onStop={stop} autoFocus={open} />
        <p className="disclaimer">{DISCLAIMER}</p>
      </footer>
    </aside>
  )
}
