import { useEffect, useId, useRef, useState } from 'react'

import { setAccessCode } from '../api'
import { useApp } from '../appContext'
import { AgentMark, greeting } from './AgentMark'

export const EXAMPLES = [
  'What does alarm E301 indicate?',
  'How do I clean the infuser?',
  'What is the connectivity engine?',
]

const STAGE_LABELS = {
  thinking: 'Thinking',
  searching: 'Searching the manual',
  reading: 'Reading the relevant pages',
  refining: 'Looking a little further in the manual',
}

// Answers from the agent may use "Meaning:" / "Manual-listed action:" lines.
const LABELLED_LINE = /^(Meaning|Manual-listed action):\s*(.*)$/
const BULLET = /^\s*(?:[-*•]|\d+[.)])\s+(.*)$/

// Minimal inline formatting for model replies: **bold** only.
function Inline({ text }) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4 ? (
      <strong key={index}>{part.slice(2, -2)}</strong>
    ) : (
      part
    ),
  )
}

function AnswerBody({ text }) {
  const lines = text.split('\n').filter((line) => line.trim())
  return (
    <div className="answer">
      {lines.map((line, index) => {
        const labelled = line.match(LABELLED_LINE)
        if (labelled) {
          return (
            <div className="answer-field" key={index}>
              <span className="answer-label">{labelled[1]}</span>
              <p><Inline text={labelled[2]} /></p>
            </div>
          )
        }
        const bullet = line.match(BULLET)
        if (bullet) {
          return (
            <p className="answer-bullet" key={index}>
              <Inline text={bullet[1]} />
            </p>
          )
        }
        return <p key={index}><Inline text={line} /></p>
      })}
    </div>
  )
}

// [12, 13, 14, 20] -> "12–14, 20"
function compressNumbers(numbers) {
  const ranges = []
  for (const number of numbers) {
    const last = ranges[ranges.length - 1]
    if (last && number === last[1] + 1) last[1] = number
    else ranges.push([number, number])
  }
  return ranges.map(([start, end]) => (start === end ? `${start}` : `${start}–${end}`)).join(', ')
}

// Prefer the manual's printed labels ("9-6–9-8"); fall back to PDF pages.
function describePages(pages, labelForPage) {
  const labels = pages.map(labelForPage)
  if (pages.length && labels.every(Boolean)) {
    return labels.length === 1 ? labels[0] : `${labels[0]} – ${labels[labels.length - 1]}`
  }
  return `p. ${compressNumbers(pages)}`
}

// Older answers only carry text citations: "file.pdf (pages 12, 13)".
function pagesFromCitation(citation) {
  const match = citation.match(/\((?:pages?\s+)?([\d,\s]+)\)\s*$/i)
  return match ? match[1].split(',').map((page) => Number(page.trim())).filter(Boolean) : []
}

function Sources({ message }) {
  const { openManual, manual } = useApp()
  const sources = message.sources?.length
    ? message.sources
    : (message.citations || []).map((citation) => ({ citation, pages: pagesFromCitation(citation) }))
  if (!sources.length) return null

  return (
    <ol className="sources">
      {sources.map((source, index) => {
        const pages = source.pages || []
        const text = pages.length ? describePages(pages, manual.labelForPage) : 'manual excerpt'
        const content = (
          <>
            <span className="source-index">{index + 1}</span>
            <span className="source-name">Operating manual</span>
            <span className="source-pages">{text}</span>
          </>
        )
        return (
          <li key={`${source.citation}-${index}`}>
            {manual.available && pages.length ? (
              <button
                type="button"
                className="source-button"
                onClick={() => openManual(pages, 0)}
                title="View this page of the manual"
              >
                {content}
                <span className="source-view">View page</span>
              </button>
            ) : (
              <span className="source-static">{content}</span>
            )}
          </li>
        )
      })}
    </ol>
  )
}

/** Shown when the server asks for the demo access code. */
function AccessCodePrompt({ message, onAsk }) {
  const [code, setCode] = useState('')
  const inputId = useId()
  const submit = (event) => {
    event.preventDefault()
    if (!code.trim()) return
    setAccessCode(code)
    onAsk(message.question, { retry: true })
  }
  return (
    <form className="code-prompt" onSubmit={submit}>
      <label htmlFor={inputId}>
        This demo is invite-only. Enter the access code you were given to continue.
      </label>
      <div className="code-prompt-row">
        <input
          id={inputId}
          type="password"
          value={code}
          onChange={(event) => setCode(event.target.value)}
          placeholder="Access code"
          autoComplete="off"
          autoFocus
        />
        <button type="submit" disabled={!code.trim()}>
          Continue
        </button>
      </div>
    </form>
  )
}

function Message({ message, onAsk }) {
  if (message.role === 'user') {
    return (
      <div className="message message-user">
        <p>{message.content}</p>
      </div>
    )
  }

  const waiting = message.streaming && !message.content

  return (
    <article className="message message-assistant" aria-busy={message.streaming || undefined}>
      <AgentMark size={18} active={message.streaming} className="avatar" />
      <div className="message-body">
        {message.error && message.needsCode ? (
          <AccessCodePrompt message={message} onAsk={onAsk} />
        ) : message.error ? (
          <p className="message-error">{message.content}</p>
        ) : waiting ? (
          <p className="pending">{STAGE_LABELS[message.stage] || STAGE_LABELS.thinking}</p>
        ) : (
          <>
            <div className={message.streaming ? 'is-streaming' : undefined}>
              <AnswerBody text={message.content} />
            </div>
            {message.stopped && <p className="stopped">Stopped.</p>}
            {message.notice && <p className="notice">{message.notice}</p>}
            {!message.streaming && <Sources message={message} />}
          </>
        )}
      </div>
    </article>
  )
}

export function ChatIntro({ onAsk, compact = false }) {
  return (
    <section className={`intro${compact ? ' is-compact' : ''}`}>
      <AgentMark size={compact ? 32 : 40} className="intro-mark" />
      <h1>{greeting()}.</h1>
      <p>
        I'm the Plum 360 manual assistant. Ask about an alarm, a procedure, or a
        feature, and I'll search the System Operating Manual, summarize what it
        says, and cite the pages.
      </p>
      <ul className="examples">
        {EXAMPLES.map((example) => (
          <li key={example}>
            <button type="button" onClick={() => onAsk(example)}>
              {example}
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

/** Message list with auto-scroll; render inside a scrolling container. */
export function ChatThread({ messages, loading, onAsk, compact = false }) {
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: loading ? 'auto' : 'smooth', block: 'end' })
  }, [messages, loading])

  return (
    <>
      {messages.length === 0 ? (
        <ChatIntro onAsk={onAsk} compact={compact} />
      ) : (
        messages.map((message) => <Message key={message.id} message={message} onAsk={onAsk} />)
      )}
      <div ref={endRef} />
    </>
  )
}

export function Composer({ loading, onAsk, onStop, autoFocus = false }) {
  const [draft, setDraft] = useState('')
  const inputRef = useRef(null)
  const inputId = useId()

  useEffect(() => {
    const input = inputRef.current
    if (!input) return
    input.style.height = 'auto'
    input.style.height = `${Math.min(input.scrollHeight, 180)}px`
  }, [draft])

  useEffect(() => {
    if (!loading && autoFocus) inputRef.current?.focus()
  }, [loading, autoFocus])

  const send = async () => {
    if (await onAsk(draft)) setDraft('')
  }

  return (
    <form
      className="composer"
      onSubmit={(event) => {
        event.preventDefault()
        if (loading) onStop()
        else send()
      }}
    >
      <label className="visually-hidden" htmlFor={inputId}>
        Question
      </label>
      <textarea
          id={inputId}
          ref={inputRef}
          rows={1}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault()
              if (!loading) send()
            }
          }}
          placeholder="Ask about an alarm, procedure, or feature"
          autoFocus={autoFocus}
        />
      <button type="submit" className={loading ? 'is-stop' : undefined} disabled={!loading && !draft.trim()}>
        {loading ? 'Stop' : 'Ask'}
      </button>
    </form>
  )
}

export const DISCLAIMER =
  'Reference only. Not a medical device. Do not use for dosing, programming, or alarm response decisions.'
