import { useEffect, useState } from 'react'
import { USE_MOCK, addRecipient, getRecipients, removeRecipient } from '../api.js'

// Who receives the alert email when a new release has changes.
export default function EmailListPage() {
  const [list, setList] = useState(null)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    getRecipients()
      .then((r) => setList(r.recipients))
      .catch((e) => setError(e.message))
  }, [])

  // Wraps add/remove so both update the list and show errors the same way.
  const run = async (action) => {
    try {
      setList((await action()).recipients)
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }

  const onSubmit = (e) => {
    e.preventDefault() // stop the form from reloading the page
    const email = draft.trim().toLowerCase()
    // type="email" on the input already checks the format in the browser.
    if (!email) return
    run(() => addRecipient(email))
    setDraft('')
  }

  return (
    <section className="card narrow">
      <h2 className="card-title">Email list</h2>
      <p className="muted small">
        Who should get the alert email when a new HTS release has changes.
        {USE_MOCK && ' Run the Python API to edit this list.'}
      </p>

      {!USE_MOCK && (
      <form className="add-row" onSubmit={onSubmit}>
        <input
          type="email"
          required
          placeholder="name@cpsc.gov"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          aria-label="Email address"
        />
        <button type="submit">Add</button>
      </form>
      )}
      {error && <p className="error-text">{error}</p>}

      {list === null ? (
        <p className="muted">Loading…</p>
      ) : list.length === 0 ? (
        <p className="muted">No one is on the list yet.</p>
      ) : (
        <ul className="plain-list">
          {list.map((email) => (
            <li key={email}>
              <span>{email}</span>
              {!USE_MOCK && (
                <button className="link-button" onClick={() => run(() => removeRecipient(email))}>
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
