import { useEffect, useState } from 'react'

import { useApp } from './appContext'
import { AgentMark } from './components/AgentMark'
import { Icon } from './components/Icons'
import { PumpIllustration } from './components/PumpIllustration'
import {
  ALARM_LEVELS,
  ALARM_NOTE,
  ALARM_REF,
  CARE,
  FEATURES,
  HERO,
  INTENDED_USE,
  INTENDED_USE_REF,
  SPECS,
  STATS,
  STEPS,
} from './content'

const SECTIONS = [
  ['features', 'Features'],
  ['diagrams', 'Diagrams'],
  ['how-it-works', 'How it works'],
  ['alarms', 'Alarms'],
  ['care', 'Care'],
  ['specs', 'Specifications'],
]

export const askHref = (question) => `#/assistant?q=${encodeURIComponent(question)}`

/** "Manual 11-6": opens that page in the viewer when the PDF is served. */
function Ref({ page: label }) {
  const { manual, openManual } = useApp()
  const pdfPage = manual.available ? manual.pageForLabel(label) : null
  if (!pdfPage) return <span className="ref">Manual {label}</span>
  return (
    <button
      type="button"
      className="ref ref-button"
      onClick={() => openManual([pdfPage], 0)}
      title={`View manual page ${label}`}
    >
      Manual {label}
    </button>
  )
}

/** Opens the chat drawer and asks; the href keeps it working without JS. */
function AskLink({ question, children = 'Ask the assistant' }) {
  const { openChat } = useApp()
  return (
    <a
      className="ask-link"
      href={askHref(question)}
      onClick={(event) => {
        event.preventDefault()
        openChat(question)
      }}
    >
      {children}
      <Icon name="arrow" size={14} />
    </a>
  )
}

function scrollToSection(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function SectionHeading({ eyebrow, title, children }) {
  return (
    <div className="section-heading">
      <p className="eyebrow">{eyebrow}</p>
      <h2>{title}</h2>
      {children && <p className="section-lead">{children}</p>}
    </div>
  )
}

function AlarmLookup() {
  const { openChat } = useApp()
  const [code, setCode] = useState('')
  const trimmed = code.trim().toUpperCase()

  const submit = (event) => {
    event.preventDefault()
    if (trimmed) {
      openChat(`What does alarm ${trimmed} indicate?`)
      setCode('')
    }
  }

  return (
    <form className="alarm-lookup" onSubmit={submit}>
      <label htmlFor="alarm-code">Look up an alarm code</label>
      <p className="alarm-lookup-hint">The assistant finds the code in the manual's alarm tables.</p>
      <div className="alarm-lookup-row">
        <input
          id="alarm-code"
          value={code}
          onChange={(event) => setCode(event.target.value)}
          placeholder="e.g. E301"
          maxLength={8}
          autoComplete="off"
          spellCheck="false"
        />
        <button type="submit" disabled={!trimmed}>
          Explain
        </button>
      </div>
    </form>
  )
}

/** Figures exported from the manual (scripts/export_manual_figures.py). */
function useManualFigures() {
  const [figures, setFigures] = useState([])
  useEffect(() => {
    let cancelled = false
    fetch('/manual-figures/figures.json')
      .then((response) => (response.ok ? response.json() : []))
      .then((data) => {
        if (!cancelled && Array.isArray(data)) setFigures(data)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])
  return figures
}

function Diagrams({ figures }) {
  if (!figures.length) return null
  return (
    <section className="section" id="diagrams">
      <SectionHeading eyebrow="From the manual" title="Hardware at a glance">
        Diagrams from the System Operating Manual's equipment description.
      </SectionHeading>
      <div className="figure-grid">
        {figures.map((figure) => (
          <figure className="diagram" key={figure.src}>
            <div className="diagram-image">
              <img src={figure.src} alt={figure.caption} loading="lazy" />
            </div>
            <figcaption>
              <span>{figure.caption}</span>
              <Ref page={figure.ref} />
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  )
}

export default function ProductPage() {
  const { openChat } = useApp()
  const figures = useManualFigures()
  const sections = figures.length ? SECTIONS : SECTIONS.filter(([id]) => id !== 'diagrams')

  return (
    <div className="site">
      <header className="site-nav">
        <div className="site-nav-inner">
          <a className="brand" href="#/" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            <AgentMark size={18} />
            <span className="brand-name">Plum 360</span>
            <span className="brand-divider" aria-hidden="true">/</span>
            <span className="brand-sub">Product guide</span>
          </a>
          <nav className="site-links" aria-label="Sections">
            {sections.map(([id, label]) => (
              <button key={id} type="button" onClick={() => scrollToSection(id)}>
                {label}
              </button>
            ))}
          </nav>
          <a className="button button-small" href="#/assistant">
            Open assistant
          </a>
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow">{HERO.eyebrow}</p>
            <h1>{HERO.title}</h1>
            <p className="hero-lead">{HERO.lead}</p>
            <div className="hero-actions">
              <button
                type="button"
                className="button"
                onClick={() => openChat('How do I set up the infuser for a new infusion?')}
              >
                Ask how to use it
              </button>
              <button type="button" className="button button-quiet" onClick={() => scrollToSection('features')}>
                Explore features
              </button>
            </div>
            <p className="hero-note">
              Independent reference built from the System Operating Manual
              (IFU0000340). Not affiliated with ICU Medical.
            </p>
          </div>
          <figure className="hero-figure">
            <PumpIllustration />
          </figure>
        </section>

        <section className="stats" aria-label="At a glance">
          {STATS.map((stat) => (
            <div className="stat" key={stat.label}>
              <p className="stat-value">
                {stat.value}
                {stat.unit && <span className="stat-unit"> {stat.unit}</span>}
              </p>
              <p className="stat-label">{stat.label}</p>
              <Ref page={stat.ref} />
            </div>
          ))}
        </section>

        <section className="section" id="features">
          <SectionHeading eyebrow="Features" title="What the infuser does">
            The capabilities described in the manual's introduction and equipment
            description.
          </SectionHeading>
          <div className="feature-grid">
            {FEATURES.map((feature) => (
              <article className="feature" key={feature.title}>
                <span className="feature-icon">
                  <Icon name={feature.icon} size={20} />
                </span>
                <h3>{feature.title}</h3>
                <p>{feature.text}</p>
                <div className="card-foot">
                  <Ref page={feature.ref} />
                  <AskLink question={feature.ask}>Ask</AskLink>
                </div>
              </article>
            ))}
          </div>
        </section>

        <Diagrams figures={figures} />

        <section className="section" id="how-it-works">
          <SectionHeading eyebrow="How it works" title="From set-up to delivery">
            An overview of the basic workflow. Each step links to the full
            procedure in the assistant.
          </SectionHeading>
          <ol className="steps">
            {STEPS.map((step, index) => (
              <li className="step" key={step.title}>
                <span className="step-number">{String(index + 1).padStart(2, '0')}</span>
                <div className="step-body">
                  <h3>{step.title}</h3>
                  <p>{step.text}</p>
                </div>
                <div className="step-meta">
                  <Ref page={step.ref} />
                  <AskLink question={step.ask}>Full steps</AskLink>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section className="section" id="alarms">
          <SectionHeading eyebrow="Alarms" title="Three priority levels">
            {ALARM_NOTE}
          </SectionHeading>
          <div className="alarm-layout">
            <div className="alarm-levels">
              {ALARM_LEVELS.map((alarm) => (
                <div className={`alarm-level is-${alarm.level.toLowerCase()}`} key={alarm.level}>
                  <p className="alarm-name">{alarm.level} priority</p>
                  <div className="beeps" aria-label={`${alarm.beeps} beeps`}>
                    {Array.from({ length: alarm.beeps }, (_, index) => (
                      <span key={index} className="beep" />
                    ))}
                  </div>
                  <p className="alarm-count">{alarm.beeps} beeps</p>
                </div>
              ))}
              <Ref page={ALARM_REF} />
            </div>
            <AlarmLookup />
          </div>
        </section>

        <section className="section" id="care">
          <SectionHeading eyebrow="Care" title="Cleaning, battery, and maintenance" />
          <div className="care-grid">
            {CARE.map((item) => (
              <article className="care" key={item.title}>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
                <div className="card-foot">
                  <Ref page={item.ref} />
                  <AskLink question={item.ask}>Ask</AskLink>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="section" id="specs">
          <SectionHeading eyebrow="Specifications" title="Technical details" />
          <dl className="specs">
            {SPECS.map(([term, value, ref]) => (
              <div className="spec-row" key={term}>
                <dt>{term}</dt>
                <dd>{value}</dd>
                <Ref page={ref} />
              </div>
            ))}
          </dl>
        </section>

        <section className="cta">
          <div>
            <h2>Have a question the page doesn't answer?</h2>
            <p>
              The assistant searches all 268 pages of the operating manual and cites
              where each answer comes from.
            </p>
          </div>
          <button type="button" className="button" onClick={() => openChat()}>
            Ask the assistant
          </button>
        </section>
      </main>

      <footer className="site-footer">
        <p>
          <strong>Intended use.</strong> {INTENDED_USE} <Ref page={INTENDED_USE_REF} />
        </p>
        <p>
          This site is an independent reference project and is not a medical device.
          Do not use it for dosing, programming, or alarm response decisions. Follow
          the official manual, facility procedures, and qualified clinical guidance.
        </p>
      </footer>
    </div>
  )
}
