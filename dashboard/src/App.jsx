import { useCallback, useEffect, useState } from 'react'
import { getChanges, getReleases, getStatus } from './api.js'
import NavBar from './components/NavBar.jsx'
import { PAGES } from './pages.js'
import HomePage from './pages/HomePage.jsx'
import ReportsPage from './pages/ReportsPage.jsx'
import WatchlistPage from './pages/WatchlistPage.jsx'
import EmailListPage from './pages/EmailListPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'

// How often to re-ask the API for fresh data (ms).
const REFRESH_MS = 60_000

const VALID_PAGES = [...PAGES.map((p) => p.id), 'settings']

// Read the page from the URL hash, e.g. "#/reports" -> "reports".
function pageFromHash() {
  const id = window.location.hash.replace(/^#\/?/, '')
  return VALID_PAGES.includes(id) ? id : 'home'
}

export default function App() {
  const [page, setPage] = useState(pageFromHash)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  // Follow the hash when a nav link is clicked or Back is pressed.
  useEffect(() => {
    const onHash = () => setPage(pageFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  // Status, releases and the change report are shared by several pages, so
  // they load here once. Watchlist, settings and email list load on their page.
  const load = useCallback(async () => {
    try {
      const [status, releases, report] = await Promise.all([
        getStatus(),
        getReleases(),
        getChanges(),
      ])
      setData({ status, releases, report })
      setError(null)
    } catch (err) {
      setError(err.message) // keep the last good data on screen
    }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, REFRESH_MS)
    return () => clearInterval(id)
  }, [load])

  return (
    <>
      <NavBar page={page} />
      <main className="page">
        {error && <div className="error-banner">Could not load data: {error}</div>}
        {!data && !error && <p className="muted">Loading…</p>}
        {data && page === 'home' && (
          <HomePage currentRelease={data.status.currentRelease} report={data.report} />
        )}
        {data && page === 'reports' && (
          <ReportsPage report={data.report} releases={data.releases} />
        )}
        {page === 'watchlist' && <WatchlistPage />}
        {page === 'emails' && <EmailListPage />}
        {data && page === 'settings' && <SettingsPage status={data.status} />}
      </main>
    </>
  )
}
