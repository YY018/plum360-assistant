import { AgentMark } from './components/AgentMark'
import { ChatThread, Composer, DISCLAIMER } from './components/Chat'

/** Full-page assistant at #/assistant. */
export default function ChatPage({ chat }) {
  const { messages, loading, ask, stop, reset } = chat

  return (
    <div className="layout">
      <header className="topbar">
        <a className="brand" href="#/">
          <AgentMark size={18} />
          <span className="brand-name">Plum 360</span>
          <span className="brand-divider" aria-hidden="true">/</span>
          <span className="brand-sub">Assistant</span>
        </a>
        <div className="topbar-actions">
          {messages.length > 0 && (
            <button type="button" className="text-button" onClick={reset} disabled={loading}>
              New conversation
            </button>
          )}
          <a className="text-button" href="#/">
            Product guide
          </a>
        </div>
      </header>

      <main className="thread" aria-live="polite">
        <ChatThread messages={messages} loading={loading} onAsk={ask} />
      </main>

      <footer className="composer-area">
        <Composer loading={loading} onAsk={ask} onStop={stop} autoFocus />
        <p className="disclaimer">{DISCLAIMER}</p>
      </footer>
    </div>
  )
}
