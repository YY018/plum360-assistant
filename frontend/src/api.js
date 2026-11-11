// Backend address. In development the API runs on its own port; in a
// production build the same server serves the site and the API, so requests
// are relative. Override either with VITE_API_BASE at build time.
const configured = import.meta.env.VITE_API_BASE
export const API_BASE = (configured ?? (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '')).replace(/\/$/, '')
export const API_LABEL = API_BASE || 'the server'

const ACCESS_CODE_KEY = 'plum360.accessCode'

// A demo access code can be given once in the link (?code=...) and is then
// remembered for this browser session. It is never written into the page.
export function accessCode() {
  try {
    const fromUrl = new URLSearchParams(window.location.search).get('code')
    if (fromUrl) {
      window.sessionStorage.setItem(ACCESS_CODE_KEY, fromUrl)
      window.history.replaceState(null, '', window.location.pathname + window.location.hash)
    }
    return window.sessionStorage.getItem(ACCESS_CODE_KEY) || ''
  } catch {
    return ''
  }
}

export function manualPageUrl(page) {
  const code = accessCode()
  return `${API_BASE}/manual/pages/${page}.png${code ? `?code=${encodeURIComponent(code)}` : ''}`
}
