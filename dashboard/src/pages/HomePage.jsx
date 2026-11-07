import { useEffect, useState } from 'react'
import { elapsedSince } from '../format.js'
import { ChangeDetail, RelevanceBadge } from '../components/ChangeParts.jsx'
import { describe } from '../changes.js'

// How many rows each Home group shows. The full list is on Reports.
const HOME_ROWS = 8

// Home, per the wireframe: time since the HTS last changed, then the latest
// changes a CPSC reviewer needs to look at (most important first).
export default function HomePage({ currentRelease, report }) {
  return (
    <div className="stack">
      <TimeSinceChange release={currentRelease} />
      <LatestChanges report={report} />
    </div>
  )
}

// "10/30/2026" -> unix seconds at local midnight, or null
function usDateToSeconds(s) {
  const m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(s ?? '')
  if (!m) return null
  return new Date(Number(m[3]), Number(m[1]) - 1, Number(m[2])).getTime() / 1000
}

function TimeSinceChange({ release }) {
  // Re-render once a minute so the counter stays current.
  const [, setTick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 60_000)
    return () => clearInterval(id)
  }, [])

  if (!release) return null
  // Time since the newest release took effect (releaseStartDate).
  // id.timestamp is when USITC created the release record, usually days earlier,
  // so it's only used as a fallback if the start date is missing.
  const since = usDateToSeconds(release.releaseStartDate) ?? release.timestamp
  const { days, hours, mins } = elapsedSince(since)
  return (
    <section className="hero">
      <div className="hero-label">Time since last HTS release</div>
      <div className="hero-value">
        <Unit n={days} unit="day" /> <Unit n={hours} unit="hour" /> <Unit n={mins} unit="min" />
      </div>
      <div className="muted">
        Latest release: {release.title} · {release.name} · in effect since{' '}
        {release.releaseStartDate}
      </div>
    </section>
  )
}

function Unit({ n, unit }) {
  return (
    <span className="unit">
      <strong>{n}</strong> {n === 1 ? unit : `${unit}s`}
    </span>
  )
}

function LatestChanges({ report }) {
  const [open, setOpen] = useState(null) // code of the expanded row

  // Home is the short list a CPSC reviewer checks: new codes in CPSC chapters
  // (most important, per the sponsor) and exact watchlist matches. Other
  // changes in CPSC chapters and everything else stay on Reports.
  const newCodes = report.changes.filter((c) => c.relevance === 'new_in_jurisdiction')
  const watched = report.changes.filter((c) => c.relevance === 'watchlist')
  const rows = { open, setOpen }

  return (
    <section className="card">
      <div className="card-header">
        <h2>Latest changes</h2>
        <a href="#/reports" className="small">
          Full report →
        </a>
      </div>
      <p className="muted small top-note">
        {newCodes.length + watched.length} of {report.total} changes need review.
      </p>
      {newCodes.length + watched.length === 0 ? (
        <p className="muted">Nothing new in CPSC scope and no watchlist codes changed.</p>
      ) : (
        <>
          <ChangeGroup title="New in CPSC jurisdiction" changes={newCodes} {...rows} />
          <ChangeGroup title="Watchlist codes changed" changes={watched} {...rows} />
        </>
      )}
    </section>
  )
}

function ChangeGroup({ title, changes, open, setOpen }) {
  if (changes.length === 0) return null
  const shown = changes.slice(0, HOME_ROWS)
  return (
    <>
      <h3 className="small">
        {title} ({changes.length})
      </h3>
      <ul className="change-list">
        {shown.map((c) => {
          const isOpen = open === c.code
          return (
            <li key={c.code}>
              <button
                className={`change-row ${isOpen ? 'open' : ''}`}
                onClick={() => setOpen(isOpen ? null : c.code)}
                aria-expanded={isOpen}
              >
                <code className="hts">{c.htsCode}</code>
                <span className="change-type">{c.changeType}</span>
                <span className="change-desc">{describe(c)}</span>
                <RelevanceBadge relevance={c.relevance} short />
              </button>
              {isOpen && <ChangeDetail change={c} />}
            </li>
          )
        })}
      </ul>
      {changes.length > HOME_ROWS && (
        <a href="#/reports" className="more-link small">
          {changes.length - HOME_ROWS} more in the full report
        </a>
      )}
    </>
  )
}
