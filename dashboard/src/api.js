// -----------------------------------------------------------------------------
// api.js: the ONLY file that knows where data comes from.
//
// Real mode (VITE_USE_MOCK=false): calls dashboard/server/api.py at /api/*.
// Mock mode (default): reads static snapshots in public/mock/, written by
//   python dashboard/server/api.py --export-mock dashboard/public/mock
// so both modes return exactly the same JSON. Mock mode is read-only.
// -----------------------------------------------------------------------------

// Docs: https://vite.dev/guide/env-and-mode
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'

// GET path -> mock file name.
const MOCK_FILES = {
  '/api/status': '/mock/status.json',
  '/api/releases?limit=500': '/mock/releases.json',
  '/api/changes/latest': '/mock/changes.json',
  '/api/watchlist': '/mock/watchlist.json',
  '/api/settings': '/mock/settings.json',
  '/api/recipients': '/mock/recipients.json',
}

// GET JSON; turn HTTP errors into thrown errors so callers have one error path.
async function get(path) {
  const url = USE_MOCK ? MOCK_FILES[path] : path
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${url} returned HTTP ${res.status}`)
  return res.json()
}

// POST / PUT / DELETE. The API answers with the updated list (or an {error}).
async function send(method, path, body) {
  if (USE_MOCK) throw new Error('Editing needs the Python API (mock data is read-only).')
  const res = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`)
  return data
}

export const getStatus = () => get('/api/status')
export const getReleases = () => get('/api/releases?limit=500')
export const getChanges = () => get('/api/changes/latest')

export const getWatchlist = () => get('/api/watchlist')
export const addWatchCode = (code, category) => send('POST', '/api/watchlist', { code, category })
export const removeWatchCode = (code) =>
  send('DELETE', `/api/watchlist/${encodeURIComponent(code)}`)

export const getSettings = () => get('/api/settings')
export const saveSettings = (values) => send('PUT', '/api/settings', values)

export const getRecipients = () => get('/api/recipients')
export const addRecipient = (email) => send('POST', '/api/recipients', { email })
export const removeRecipient = (email) =>
  send('DELETE', `/api/recipients/${encodeURIComponent(email)}`)

// The alert email as HTML, rendered by server/report.py in both modes.
export const EMAIL_URL = USE_MOCK ? '/mock/email.html' : '/api/changes/latest/email'
