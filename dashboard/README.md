# CodeREAD dashboard

Web dashboard for the ReadFlare HTS monitor (`src/ReadFlare`). React + Vite front end,
small Flask API in `server/`. Nothing in `src/ReadFlare` is modified; the API only
imports and calls its functions.

| Page | What it shows |
| --- | --- |
| Home | Time since the last HTS release, and the latest changes in CPSC scope (most important first; click a row for before/after and why it was flagged) |
| Reports | Full change report: counts, filters, table, Export CSV, email preview, release history |
| Watchlist | The `cpsc_watchlist` table grouped by category; add and remove codes |
| Email List | Who should get the alert email |
| Settings (gear) | Monitor status, check interval, email on/off (`settings.py`) |

## How changes are ranked

`server/dashboard_report.py` puts every change from `diff.py` in one bucket, most important first:

1. **New in CPSC jurisdiction**: a new code in a chapter that has watched codes, or under a watched code. (Sponsor: "something new in jurisdiction, include in summary but as most important".)
2. **Watchlist code changed**: any other change to a watched code or its parent/child codes (same rule as `watchlist.find_related`).
3. **Other change in a CPSC chapter**: removed or reworded codes in chapters that have watched codes.
4. **Outside CPSC scope**: everything else.

A chapter "has watched codes" when the watchlist has at least one code in it.

## Run everything with one command

From the repo root (Windows: double-click `start.bat`):

```bash
python start.py
```

It builds the dashboard, starts the monitor (`src/ReadFlare/main.py`) and the API, and opens
http://localhost:5000, where the API also serves the dashboard. Ctrl+C stops everything.
Options: `--no-monitor` (dashboard and API only), `--no-build` (reuse the last build),
`--no-browser`.

## Run the parts separately

Python 3.11+ (diff.py uses `StrEnum`) and Node 18+.

```bash
# 1. API (from the repo root)
pip install -r dashboard/server/requirements.txt
python dashboard/server/api.py            # http://localhost:5000/api/status

# 2. Front end (from dashboard/)
npm install
copy .env.example .env.local              # then set VITE_USE_MOCK=false for live data
npm run dev                               # http://localhost:5173
```

With `VITE_USE_MOCK=true` (the default) the front end reads a saved snapshot in
`public/mock/` and needs no Python; editing is turned off. Refresh the snapshot with:

```bash
python dashboard/server/api.py --export-mock dashboard/public/mock
```

Production build: `npm run build` then `npm run preview` (http://localhost:4173).

## Where the data comes from

| Endpoint | Source |
| --- | --- |
| `GET /api/status` | `database.get_last_timestamp`, latest `update_runs` row, `engine.load_sample_data()` |
| `GET /api/releases` | `engine.load_sample_data()` (the releaseList response main.py uses today) |
| `GET /api/changes/latest` (+ `.csv`, `/email`) | latest run in the `changes` table; falls back to `data/dl/changes.json` when no complete run is stored |
| `GET/POST/DELETE /api/watchlist` | `database.get_all_htsCodes` / `add_htsCode` / `remove_htsCode` |
| `GET/PUT /api/settings` | `settings.get_all_settings` / `set_setting` |
| `GET/POST/DELETE /api/recipients` | the `email_recipients` setting (what `notify.send_alert` emails) |

The API runs the same start-up steps as `main.py` (`init_db`, seed the watchlist if empty).

## Known gaps

- ReadFlare now has its own `report.py` that builds the HTML and CSV attached to the alert.
  The dashboard's email preview (`dashboard_report.build_email`) is a separate design; the
  team can pick one.

## Layout

```
server/api.py          Flask API (imports src/ReadFlare)
server/dashboard_report.py  relevance ranking, CSV, HTML email (named so it doesn't clash with src/ReadFlare/report.py)
src/api.js             all data access (mock or live)
src/changes.js         relevance labels, CSV export
src/pages/             one file per nav page
src/components/        nav bar and shared pieces
public/mock/           saved API snapshot for mock mode
```
