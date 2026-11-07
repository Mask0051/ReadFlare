import { Fragment, useMemo, useState } from 'react'
import { EMAIL_URL } from '../api.js'
import { CHANGE_TYPES, RELEVANCE, changesToCsv, describe, downloadText } from '../changes.js'
import { ChangeDetail, RelevanceBadge } from '../components/ChangeParts.jsx'
import ReleaseTimeline from '../components/ReleaseTimeline.jsx'

const PAGE_SIZE = 50 // rows per "Show more" click; 491 rows at once is a lot to scan

// Reports: the full change report (counts, filters, table, CSV, email preview)
// and the release history.
export default function ReportsPage({ report, releases }) {
  // Hooks must run before any early return.
  const [showEmail, setShowEmail] = useState(false)

  // Fresh install: the monitor has saved its baseline but hasn't processed a release yet.
  if (report.source === 'none') {
    return (
      <div className="stack">
        <section className="card">
          <h2>No report yet</h2>
          <p className="muted">
            The monitor has saved the current HTS edition as its starting point. The full change
            report will appear here after the next release is published and processed.
          </p>
        </section>
        <ReleaseTimeline releases={releases.releases} total={releases.total} />
      </div>
    )
  }

  const title = report.release
    ? `${report.release.title} (${report.release.name})`
    : 'Latest report'

  return (
    <div className="stack">
      <section className="card">
        <div className="card-header">
          <h2>{title}</h2>
          <button onClick={() => setShowEmail((v) => !v)}>
            {showEmail ? 'Hide email' : 'Preview email'}
          </button>
        </div>
        <p className="muted small top-note">
          Run #{report.run?.id}, processed {report.run?.processedAt} UTC.{' '}
          CPSC chapters: {report.jurisdictionChapters.join(', ')}.
        </p>

        <div className="stats">
          {Object.entries(RELEVANCE).map(([key, r]) => (
            <div key={key} className={`stat stat-${r.tone}`}>
              <span className="stat-value">{report.counts[key]}</span> {r.label}
            </div>
          ))}
        </div>

        {showEmail && <EmailPreview />}
        <ChangeTable changes={report.changes} />
      </section>
      <ReleaseTimeline releases={releases.releases} total={releases.total} />
    </div>
  )
}

// The email exactly as server/report.py renders it. sandbox="" blocks scripts.
function EmailPreview() {
  return (
    <div className="email-preview">
      <div className="row-between small muted">
        <span>
          Preview of the formatted alert. notify.py still sends the plain-text digest today.
        </span>
        <a href={EMAIL_URL} target="_blank" rel="noreferrer">
          Open in new tab
        </a>
      </div>
      <iframe title="Email preview" src={EMAIL_URL} sandbox="" />
    </div>
  )
}

function ChangeTable({ changes }) {
  const [relevance, setRelevance] = useState('cpsc') // 'cpsc' = everything except "other"
  const [type, setType] = useState('all')
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState(PAGE_SIZE)
  const [open, setOpen] = useState(null)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const digits = q.replace(/\D/g, '') // "8413.91" matches code 841391...
    return changes.filter(
      (c) =>
        (relevance === 'all' ||
          (relevance === 'cpsc' ? c.relevance !== 'other' : c.relevance === relevance)) &&
        (type === 'all' || c.changeType === type) &&
        (!q ||
          (digits && c.code.startsWith(digits)) ||
          describe(c).toLowerCase().includes(q) ||
          c.before?.toLowerCase().includes(q) ||
          c.categories.some((cat) => cat.toLowerCase().includes(q))),
    )
  }, [changes, relevance, type, query])

  // Filters change -> start again from the first page.
  const update = (setter) => (e) => {
    setter(e.target.value)
    setLimit(PAGE_SIZE)
  }

  // Exports every filtered row (not only the visible page).
  const exportCsv = () => downloadText('hts_changes.csv', changesToCsv(filtered), 'text/csv')

  return (
    <>
      <div className="filters">
        <input
          type="search"
          placeholder="Code, description or category"
          value={query}
          onChange={update(setQuery)}
          aria-label="Search changes"
        />
        <select value={relevance} onChange={update(setRelevance)} aria-label="Relevance">
          <option value="cpsc">CPSC scope only</option>
          <option value="all">All changes</option>
          {Object.entries(RELEVANCE).map(([k, r]) => (
            <option key={k} value={k}>
              {r.label}
            </option>
          ))}
        </select>
        <select value={type} onChange={update(setType)} aria-label="Change type">
          <option value="all">All change types</option>
          {CHANGE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <button className="push-right" onClick={exportCsv}>
          Export CSV ({filtered.length})
        </button>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>HTS code</th>
              <th>Change</th>
              <th>Description</th>
              <th>Relevance</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, limit).map((c) => {
              const isOpen = open === c.code
              return (
                <Fragment key={c.code}>
                  <tr
                    className={`clickable ${isOpen ? 'row-open' : ''}`}
                    onClick={() => setOpen(isOpen ? null : c.code)}
                  >
                    <td>
                      <code className="hts">{c.htsCode}</code>
                    </td>
                    <td className="nowrap">{c.changeType}</td>
                    <td>{describe(c)}</td>
                    <td>
                      <RelevanceBadge relevance={c.relevance} short />
                    </td>
                  </tr>
                  {isOpen && (
                    <tr className="row-detail">
                      <td colSpan={4}>
                        <ChangeDetail change={c} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
        {filtered.length === 0 && <p className="muted">No changes match these filters.</p>}
      </div>
      <div className="card-footer muted">
        Showing {Math.min(limit, filtered.length)} of {filtered.length}
        {filtered.length > limit && (
          <button onClick={() => setLimit((n) => n + PAGE_SIZE)}>Show more</button>
        )}
      </div>
    </>
  )
}