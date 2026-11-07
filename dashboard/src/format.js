// Formatting helpers shared by components. Kept separate so they are easy
// to unit test later.

// Seconds-since-epoch -> "Oct 7, 2026, 11:55 AM" in the viewer's timezone.
export function formatTimestamp(seconds) {
  return new Date(seconds * 1000).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

// ISO string -> "3 min ago" style text for the "last checked" line.
export function timeAgo(iso) {
  const diffSec = Math.round((Date.now() - new Date(iso).getTime()) / 1000)
  if (diffSec < 60) return 'just now'
  const mins = Math.round(diffSec / 60)
  if (mins < 60) return `${mins} min ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours} h ago`
  return `${Math.round(hours / 24)} d ago`
}

// Seconds-since-epoch -> { days, hours, mins } elapsed until now.
// Used by the "Time since last change" line on Home.
export function elapsedSince(seconds) {
  const totalMins = Math.max(0, Math.floor((Date.now() / 1000 - seconds) / 60))
  return {
    days: Math.floor(totalMins / (60 * 24)),
    hours: Math.floor((totalMins / 60) % 24),
    mins: totalMins % 60,
  }
}
