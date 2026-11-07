import { RELEVANCE, htsUrl } from '../changes.js'

// Pieces shared by Home (latest changes) and Reports (full table).

export function RelevanceBadge({ relevance, short = false }) {
  const r = RELEVANCE[relevance]
  return <span className={`badge badge-${r.tone}`}>{short ? r.short : r.label}</span>
}

// Expanded detail for one change: before/after side by side and why it was flagged.
export function ChangeDetail({ change: c }) {
  return (
    <div className="change-detail">
      <div className="before-after">
        <Side label="Before" text={c.before} empty="(did not exist)" />
        <Side label="After" text={c.after} empty="(removed)" />
      </div>
      <p className="muted small">
        {c.reason}{' '}
        <a href={htsUrl(c.htsCode)} target="_blank" rel="noreferrer">
          View on hts.usitc.gov
        </a>
      </p>
    </div>
  )
}

function Side({ label, text, empty }) {
  return (
    <div>
      <div className="ba-label">{label}</div>
      {text ?? <span className="muted">{empty}</span>}
    </div>
  )
}
