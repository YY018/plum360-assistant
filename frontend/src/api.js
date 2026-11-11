// Backend address. Override at build time with VITE_API_BASE.
export const API_BASE = (import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000').replace(/\/$/, '')

export const manualPageUrl = (page) => `${API_BASE}/manual/pages/${page}.png`
