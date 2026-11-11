import { createContext, useContext, useEffect, useMemo, useState } from 'react'

import { API_BASE } from './api'

/**
 * App-wide actions: open the chat drawer (optionally asking a question) and
 * open the manual viewer at given PDF pages. Also exposes manual metadata.
 */
export const AppContext = createContext({
  openChat: () => {},
  openManual: () => {},
  manual: { available: false, pageForLabel: () => null, labelForPage: () => null },
})

export const useApp = () => useContext(AppContext)

/** Fetches whether the manual PDF is served, plus printed page labels. */
export function useManualInfo() {
  const [info, setInfo] = useState({ available: false, labels: {} })

  useEffect(() => {
    let cancelled = false
    fetch(`${API_BASE}/manual`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!cancelled && data?.available) setInfo({ available: true, labels: data.labels || {} })
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  return useMemo(() => {
    const byPage = new Map(Object.entries(info.labels).map(([label, page]) => [page, label]))
    return {
      available: info.available,
      pageForLabel: (label) => info.labels[label] ?? null,
      labelForPage: (page) => byPage.get(page) ?? null,
    }
  }, [info])
}
