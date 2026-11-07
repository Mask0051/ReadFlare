import { formatTimestamp } from '../format.js'

// Monitor health for the Settings page: last processed edition and the latest run.
export default function MonitorStatus({ status }) {
  const run = status.latestRun
  return (
    <section className="card">
      <h2 className="card-title">Monitor status</h2>
      <dl className="facts">
        <dt>Last processed release</dt>
        <dd>{formatTimestamp(status.lastSavedTimestamp)}</dd>
        <dt>Latest run</dt>
        <dd>
          {run
            ? `#${run.id} on ${run.processedAt} UTC, ${run.totalChanges} changes, alert: ${run.alertStatus}`
            : 'No update has been processed yet'}
        </dd>
        <dt>Checks every</dt>
        <dd>{status.checkIntervalMinutes} minutes</dd>
      </dl>
    </section>
  )
}
