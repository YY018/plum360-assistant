import { useEffect, useRef, useState } from 'react'

import { manualPageUrl } from '../api'
import { useApp } from '../appContext'
import { Icon } from './Icons'

/** Modal that shows rendered pages of the manual, with paging between them. */
export function ManualViewer({ pages, startIndex = 0, onClose }) {
  const { manual } = useApp()
  const [index, setIndex] = useState(startIndex)
  const [loaded, setLoaded] = useState(false)
  const [failed, setFailed] = useState(false)
  const closeRef = useRef(null)
  const previousFocus = useRef(null)

  const page = pages[index]
  const label = manual.labelForPage(page)
  const hasPrev = index > 0
  const hasNext = index < pages.length - 1

  useEffect(() => {
    setLoaded(false)
    setFailed(false)
  }, [page])

  useEffect(() => {
    previousFocus.current = document.activeElement
    closeRef.current?.focus()
    const onKey = (event) => {
      if (event.key === 'Escape') onClose()
      if (event.key === 'ArrowLeft') setIndex((value) => Math.max(0, value - 1))
      if (event.key === 'ArrowRight') setIndex((value) => Math.min(pages.length - 1, value + 1))
    }
    document.addEventListener('keydown', onKey)
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = overflow
      previousFocus.current?.focus?.()
    }
  }, [onClose, pages.length])

  return (
    <div className="viewer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="viewer" role="dialog" aria-modal="true" aria-label="Manual page">
        <header className="viewer-header">
          <div>
            <p className="viewer-title">{label ? `Manual page ${label}` : `Manual page ${page}`}</p>
            <p className="viewer-sub">
              PDF page {page}
              {pages.length > 1 && ` · ${index + 1} of ${pages.length} cited`}
            </p>
          </div>
          <div className="viewer-actions">
            <button type="button" onClick={() => setIndex(index - 1)} disabled={!hasPrev} aria-label="Previous page">
              <Icon name="arrow" size={16} className="flip" />
            </button>
            <button type="button" onClick={() => setIndex(index + 1)} disabled={!hasNext} aria-label="Next page">
              <Icon name="arrow" size={16} />
            </button>
            <button type="button" ref={closeRef} onClick={onClose} aria-label="Close">
              <Icon name="close" size={16} />
            </button>
          </div>
        </header>
        <div className="viewer-body">
          {failed ? (
            <p className="viewer-error">
              This page couldn't be loaded. Make sure the backend is running and the
              manual PDF is in data/raw/manuals/.
            </p>
          ) : (
            <img
              key={page}
              className={loaded ? 'is-loaded' : undefined}
              src={manualPageUrl(page)}
              alt={`Manual page ${label || page}`}
              onLoad={() => setLoaded(true)}
              onError={() => setFailed(true)}
            />
          )}
        </div>
      </div>
    </div>
  )
}
