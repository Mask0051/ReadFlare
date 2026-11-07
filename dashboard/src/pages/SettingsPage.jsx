import { useEffect, useState } from 'react'
import { USE_MOCK, getSettings, saveSettings } from '../api.js'
import MonitorStatus from '../components/MonitorStatus.jsx'

// Settings: monitor health plus the settings ReadFlare stores in its settings
// table (settings.py). Saving goes through settings.set_setting, which checks
// the key and the type.
export default function SettingsPage({ status }) {
  const [values, setValues] = useState(null)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    getSettings()
      .then(setValues)
      .catch((e) => setMessage({ error: true, text: e.message }))
  }, [])

  const onSave = async (e) => {
    e.preventDefault()
    try {
      setValues(
        await saveSettings({
          check_interval_minutes: values.check_interval_minutes,
          email_enabled: values.email_enabled,
        }),
      )
      setMessage({ text: 'Saved. The monitor picks this up on its next check.' })
    } catch (err) {
      setMessage({ error: true, text: err.message })
    }
  }

  return (
    <div className="stack narrow">
      <MonitorStatus status={status} />
      <section className="card">
        <h2 className="card-title">Settings</h2>
        {!values ? (
          <p className="muted">Loading…</p>
        ) : (
          <form className="settings-form" onSubmit={onSave}>
            <label>
              Check for new releases every (minutes)
              <input
                type="number"
                min="1"
                required
                disabled={USE_MOCK}
                value={values.check_interval_minutes}
                onChange={(e) =>
                  setValues({ ...values, check_interval_minutes: Number(e.target.value) })
                }
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                disabled={USE_MOCK}
                checked={values.email_enabled}
                onChange={(e) => setValues({ ...values, email_enabled: e.target.checked })}
              />
              Send alert emails
            </label>
            {USE_MOCK ? (
              <p className="muted small">Run the Python API to change settings.</p>
            ) : (
              <button type="submit">Save</button>
            )}
          </form>
        )}
        {message && <p className={message.error ? 'error-text' : 'muted small'}>{message.text}</p>}
        <p className="muted small">
          Data source: {USE_MOCK ? 'saved snapshot (public/mock)' : 'Python API'}.
        </p>
      </section>
    </div>
  )
}
