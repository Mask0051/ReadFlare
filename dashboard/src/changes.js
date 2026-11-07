// -----------------------------------------------------------------------------
// changes.js: labels and CSV export for the change report.
// The relevance buckets are decided in server/report.py; keep the keys in sync.
// -----------------------------------------------------------------------------

// Most important first (sponsor: "something new in jurisdiction ... most important").
export const RELEVANCE = {
  new_in_jurisdiction: { label: 'New in CPSC jurisdiction', short: 'New in CPSC scope', tone: 'error' },
  watchlist: { label: 'Watchlist code changed', short: 'Watchlist', tone: 'warn' },
  cpsc_chapter: { label: 'Other change in a CPSC chapter', short: 'CPSC chapter', tone: 'info' },
  other: { label: 'Outside CPSC scope', short: 'Outside scope', tone: 'neutral' },
}

// The four change types diff.py produces (ChangeType values).
export const CHANGE_TYPES = ['Added', 'Removed', 'Description Changed', 'Formatting Changed']

// One-line description for lists: the new text, or the old text for removed codes.
export function describe(c) {
  return c.after ?? c.before ?? ''
}

// Search link on the official site.
// NOTE: confirm this URL pattern on https://hts.usitc.gov before the demo.
export function htsUrl(htsCode) {
  return `https://hts.usitc.gov/search?query=${encodeURIComponent(htsCode)}`
}

// ---------------- CSV export ("table of HTS codes, export to CSV") ----------

// Quote a value for CSV: wrap in quotes and double inner quotes (RFC 4180).
function csvCell(value) {
  const s = value == null ? '' : String(value)
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

// Same columns, in the same order, as build_csv() in server/report.py.
export function changesToCsv(changes) {
  const header = [
    'hts_code', 'chapter', 'change_type', 'relevance', 'old_description',
    'new_description', 'categories', 'related_to', 'reason',
  ]
  const rows = changes.map((c) => [
    c.htsCode, c.chapter, c.changeType, c.relevance, c.before, c.after,
    c.categories.join('; '), c.relatedTo.join('; '), c.reason,
  ])
  return [header, ...rows].map((r) => r.map(csvCell).join(',')).join('\r\n')
}

// Trigger a browser download without a server round trip.
export function downloadText(filename, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
