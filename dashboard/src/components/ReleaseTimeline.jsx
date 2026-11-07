import { useMemo, useState } from 'react'

// Table of every release, newest first, with a text filter.
// 184 rows is small enough to filter in the browser; no pagination library needed.
export default function ReleaseTimeline({ releases, total }) {
  const [query, setQuery] = useState('')
  const [showAll, setShowAll] = useState(false)

  // useMemo so we only re-filter when the list or the query changes.
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return releases
    return releases.filter((r) =>
      [r.name, r.title, r.creator].some((field) => field?.toLowerCase().includes(q)),
    )
  }, [releases, query])

  // Show 15 rows by default so the page stays scannable during a demo.
  const visible = showAll ? filtered : filtered.slice(0, 15)

  return (
    <section className="card">
      <div className="card-header">
        <h2>Release history</h2>
        <input
          type="search"
          placeholder="Filter by name, title or creator"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Filter releases"
        />
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Release</th>
              <th>Published</th>
              <th>In effect</th>
              <th>Status</th>
              <th>Creator</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => (
              // name is unique per release in the USITC data, so it works as a key.
              <tr key={r.name} className={r.status === 'current' ? 'row-current' : ''}>
                <td>
                  <div>{r.title}</div>
                  <code className="muted">{r.name}</code>
                </td>
                <td>{r.createdDate}</td>
                <td>
                  {r.releaseStartDate} to {r.releaseEndDate ?? 'now'}
                </td>
                <td>
                  <span className={`pill pill-${r.status}`}>{r.status}</span>
                </td>
                <td>{r.creator}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card-footer muted">
        Showing {visible.length} of {filtered.length}
        {query ? ' matching' : ''} ({total} total)
        {filtered.length > 15 && (
          <button onClick={() => setShowAll((v) => !v)}>
            {showAll ? 'Show fewer' : 'Show all'}
          </button>
        )}
      </div>
    </section>
  )
}
