import { useEffect, useMemo, useState } from 'react'
import { USE_MOCK, addWatchCode, getWatchlist, removeWatchCode } from '../api.js'

// The CPSC watchlist (cpsc_watchlist table, seeded from data/seed_watchlist.json),
// grouped by product category. Add/remove go through database.add_htsCode /
// remove_htsCode, which validate the code length.
export default function WatchlistPage() {
  const [codes, setCodes] = useState(null)
  const [query, setQuery] = useState('')
  const [form, setForm] = useState({ code: '', category: '' })
  const [error, setError] = useState(null)

  useEffect(() => {
    getWatchlist()
      .then((r) => setCodes(r.codes))
      .catch((e) => setError(e.message))
  }, [])

  // Shared by add and remove: both return the updated list.
  const run = async (action) => {
    try {
      setCodes((await action()).codes)
      setError(null)
      return true
    } catch (e) {
      setError(e.message)
      return false
    }
  }

  const onAdd = async (e) => {
    e.preventDefault() // stop the form from reloading the page
    if (await run(() => addWatchCode(form.code, form.category))) setForm({ code: '', category: '' })
  }

  // Filter, then group by category for display.
  const groups = useMemo(() => {
    if (!codes) return []
    const q = query.trim().toLowerCase()
    const digits = q.replace(/\D/g, '')
    const byCategory = new Map()
    for (const c of codes) {
      const category = c.category ?? 'Uncategorized'
      if (q && !category.toLowerCase().includes(q) && !(digits && c.code.startsWith(digits))) continue
      if (!byCategory.has(category)) byCategory.set(category, [])
      byCategory.get(category).push(c)
    }
    return [...byCategory.entries()]
  }, [codes, query])

  const categories = useMemo(
    () => [...new Set((codes ?? []).map((c) => c.category).filter(Boolean))].sort(),
    [codes],
  )

  return (
    <section className="card">
      <div className="card-header">
        <h2>Watchlist</h2>
        <input
          type="search"
          placeholder="Search code or category"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search watchlist"
        />
      </div>
      <p className="muted small top-note">
        {codes ? `${codes.length} codes in ${categories.length} categories.` : 'Loading…'} A change
        to any of these, or in their chapters, is flagged in reports.
      </p>

      {!USE_MOCK && (
        <form className="add-row" onSubmit={onAdd}>
          <input
            required
            placeholder="HTS code, e.g. 9503.00.00.71"
            value={form.code}
            onChange={(e) => setForm({ ...form, code: e.target.value })}
            aria-label="HTS code"
          />
          <input
            list="watch-categories"
            placeholder="Category"
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
            aria-label="Category"
          />
          <datalist id="watch-categories">
            {categories.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
          <button type="submit">Add</button>
        </form>
      )}
      {error && <p className="error-text">{error}</p>}

      {groups.map(([category, items]) => (
        <details key={category} className="watch-group" open={Boolean(query)}>
          <summary>
            <span>{category}</span>
            <span className="muted small">
              ch. {[...new Set(items.map((c) => c.chapter))].join(', ')} · {items.length} codes
            </span>
          </summary>
          <ul className="code-grid">
            {items.map((c) => (
              <li key={c.code}>
                <code>{c.htsCode}</code>
                {!USE_MOCK && (
                  <button
                    className="link-button small"
                    onClick={() => run(() => removeWatchCode(c.code))}
                    aria-label={`Remove ${c.htsCode}`}
                  >
                    Remove
                  </button>
                )}
              </li>
            ))}
          </ul>
        </details>
      ))}
    </section>
  )
}
