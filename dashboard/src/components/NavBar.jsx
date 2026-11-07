// Top bar from the wireframe: brand, page links, settings gear on the right.
// Links are plain hash links (#/reports), so the browser back button and
// refresh keep you on the same page with no router library.

import { PAGES } from '../pages.js'

export default function NavBar({ page }) {
  return (
    <header className="navbar">
      <a className="brand" href="#/home">
        Code<span className='redRead'>READ</span>
      </a>
      <nav className="nav-links">
        {PAGES.map((p) => (
          <a key={p.id} href={`#/${p.id}`} aria-current={page === p.id ? 'page' : undefined}>
            {p.label}
          </a>
        ))}
      </nav>
      <a
        className="nav-settings"
        href="#/settings"
        aria-current={page === 'settings' ? 'page' : undefined}
        aria-label="Settings"
        title="Settings"
      >
        {/* Gear icon, inline SVG so there is no icon dependency */}
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      </a>
    </header>
  )
}
