import { useCallback, useEffect, useMemo, useState } from 'react'

import ChatPage from './ChatPage'
import ProductPage from './ProductPage'
import { AppContext, useManualInfo } from './appContext'
import { AgentMark } from './components/AgentMark'
import { ChatDrawer } from './components/ChatDrawer'
import { Icon } from './components/Icons'
import { ManualViewer } from './components/ManualViewer'
import { useChat } from './useChat'

// Hash routes: "#/" is the product guide, "#/assistant" the full-page chatbot.
// "#/assistant?q=..." opens the chatbot and asks that question.
function readRoute() {
  const raw = window.location.hash.replace(/^#/, '') || '/'
  const [path, query = ''] = raw.split('?')
  return {
    page: path.startsWith('/assistant') ? 'assistant' : 'product',
    question: new URLSearchParams(query).get('q'),
  }
}

const TEASER_KEY = 'plum360.teaserDismissed'

function readTeaserDismissed() {
  try {
    return window.sessionStorage.getItem(TEASER_KEY) === '1'
  } catch {
    return false
  }
}

function rememberTeaserDismissed() {
  try {
    window.sessionStorage.setItem(TEASER_KEY, '1')
  } catch {
    // Storage unavailable; the teaser simply returns next visit.
  }
}

function ChatLauncher({ onOpen }) {
  const [showTeaser, setShowTeaser] = useState(false)

  useEffect(() => {
    if (readTeaserDismissed()) return undefined
    const timer = setTimeout(() => setShowTeaser(true), 1500)
    return () => clearTimeout(timer)
  }, [])

  const dismiss = () => {
    setShowTeaser(false)
    rememberTeaserDismissed()
  }

  return (
    <div className="launcher">
      {showTeaser && (
        <div className="launcher-teaser" role="status">
          <button type="button" className="teaser-close" onClick={dismiss} aria-label="Dismiss">
            <Icon name="close" size={14} />
          </button>
          <p className="teaser-title">Hi, I'm the manual assistant.</p>
          <p>Ask me how to use the infuser, what an alarm means, or how to clean it.</p>
        </div>
      )}
      <button
        type="button"
        className="launcher-button"
        onClick={() => {
          dismiss()
          onOpen()
        }}
      >
        <span className="launcher-mark">
          <AgentMark size={20} />
        </span>
        Ask about Plum 360
      </button>
    </div>
  )
}

export default function App() {
  const chat = useChat()
  const manual = useManualInfo()
  const [route, setRoute] = useState(readRoute)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [viewer, setViewer] = useState(null)

  useEffect(() => {
    const onHashChange = () => {
      setRoute(readRoute())
      setDrawerOpen(false)
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const { ask } = chat

  // A question passed in the URL is asked once, then removed from the URL so
  // refreshing the page doesn't ask it again.
  useEffect(() => {
    if (route.page !== 'assistant' || !route.question) return
    ask(route.question)
    window.history.replaceState(null, '', '#/assistant')
    setRoute({ page: 'assistant', question: null })
  }, [route, ask])

  useEffect(() => {
    document.title =
      route.page === 'assistant' ? 'Plum 360 · Assistant' : 'Plum 360 · Product guide'
  }, [route.page])

  const openChat = useCallback(
    (question) => {
      rememberTeaserDismissed()
      setDrawerOpen(true)
      if (question) ask(question)
    },
    [ask],
  )
  const closeChat = useCallback(() => setDrawerOpen(false), [])
  const openManual = useCallback((pages, startIndex = 0) => {
    if (pages?.length) setViewer({ pages, startIndex })
  }, [])
  const closeManual = useCallback(() => setViewer(null), [])

  const context = useMemo(
    () => ({ openChat, openManual, manual }),
    [openChat, openManual, manual],
  )

  return (
    <AppContext.Provider value={context}>
      {route.page === 'assistant' ? (
        <ChatPage chat={chat} />
      ) : (
        <>
          <ProductPage />
          {!drawerOpen && <ChatLauncher onOpen={() => openChat()} />}
          <ChatDrawer open={drawerOpen} chat={chat} onClose={closeChat} />
          {drawerOpen && <div className="drawer-scrim" onClick={closeChat} aria-hidden="true" />}
        </>
      )}
      {viewer && (
        <ManualViewer
          key={viewer.pages.join(',')}
          pages={viewer.pages}
          startIndex={viewer.startIndex}
          onClose={closeManual}
        />
      )}
    </AppContext.Provider>
  )
}
