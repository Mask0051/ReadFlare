# CodeREAD (ReadFlare)

ReadFlare watches the U.S. Harmonized Tariff Schedule (HTS) for new releases and tells you when codes CPSC cares about are affected. When the U.S. International Trade Commission (USITC) publishes a revision, it downloads it, works out what changed, matches the changes against your watchlist, emails a short alert with a full report attached, and shows everything on a local web dashboard.

Built for the U.S. Consumer Product Safety Commission (CPSC) as part of GMU's Challenge X.

It has two parts that run together:

- **The monitor** (`src/ReadFlare`, code name ReadFlare) checks USITC for new releases, finds the changes, stores them and sends alerts.
- **The dashboard** (`dashboard/`) is a web page for viewing changes and reports and managing the watchlist, the email list and settings.

---

## Quick start

You need **Python 3.11+** and **Node.js 18+**. Then, from the repo root:

```bash
python start.py
```

On Windows you can double-click **`start.bat`** instead.

`start.py` does everything:

1. installs the Python packages in `requirements.txt` if they're missing,
2. installs the dashboard packages the first time and builds the dashboard,
3. starts the monitor (`src/ReadFlare/main.py`),
4. starts the API and dashboard (`dashboard/server/api.py`) at **http://localhost:5000**,
5. opens that page in your browser.

Press `Ctrl+C` once to stop everything.

| Flag | Effect |
|---|---|
| `--no-monitor` | Start only the dashboard and API, without checking USITC |
| `--no-build` | Reuse the existing dashboard build (faster restarts when the front end hasn't changed) |
| `--no-browser` | Don't open a browser tab |

### What happens on the first run

1. The `data/` folder and the database are created.
2. The watchlist is filled from the seed file. This only happens while the watchlist is empty, so your later edits are never overwritten.
3. The current HTS edition is downloaded and saved as the **baseline**. There is nothing to compare it with yet, so no changes are reported.
4. The dashboard shows the current release and says **"No report yet"**. That's expected.

The first real report appears when the **next** HTS release is published. After that, the monitor checks every `check_interval_minutes` (default 60).

To start completely fresh, stop the program and delete the `data/` folder.

---

## Requirements

| Requirement | Why |
|---|---|
| **Python 3.11 or newer** | The code uses `StrEnum` |
| **Node.js 18 or newer** | To build the dashboard |
| **Poppler (`pdftotext`)** | To read the Change Record PDFs. See below |
| **Network access to `hts.usitc.gov`** | To download releases and Change Records |

Python packages are listed in `requirements.txt` (`flask`, `requests`). `start.py` installs them if they're missing. On Linux, the system Python may refuse to install packages; if so, use a virtual environment:

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python start.py
```

### Poppler / pdftotext

The Change Record PDFs are read with `pdftotext`. Without it everything still runs, but changes won't have an effective date or legal source. `start.py` prints a warning if it's missing.

| System | Install |
|---|---|
| Windows | Install Poppler for Windows and add its `bin` folder to `PATH` |
| Fedora | `sudo dnf install poppler-utils` |
| Debian / Ubuntu | `sudo apt install poppler-utils` |
| macOS | `brew install poppler` |

---

## What the monitor does

For every new HTS release:

1. **Detects the release.** Polls USITC's release list and compares the newest release with the last one processed.
2. **Downloads the full schedule** (JSON).
3. **Diffs it against the previous edition.** Finds codes that were added, removed, or had their description changed. Whitespace-only edits are kept but marked as low-priority formatting changes.
4. **Reads the official Change Record.** Downloads the release's Change Record PDF and pulls out each code's nature of change, effective date and legal source (for example a Presidential Proclamation or `484(f)`).
5. **Reconciles the two sources.** Each change is tagged as found by both, by the diff only (USITC didn't list it), or by the Change Record only. Changes the Change Record didn't list get the release's start date and the source "Not listed in change record".
6. **Matches against the watchlist:**
   - **Watchlist:** the code itself is on the watchlist
   - **Related:** a parent or child of a watchlist code changed
   - **Other:** everything else. Logged, but not emailed
7. **Stores everything** in a local SQLite database, so there's a full history of every release.
8. **Saves a report** (HTML and CSV) in `data/reports/`.
9. **Sends an alert email** if any high-priority watchlist code changed. The body is one line per code, with the full report attached.

### Example alert

```
Subject: HTS update: 1 watchlist code(s) affected (2026 HTS Revision 11)

HTS update: 2026 HTS Revision 11

Watchlist codes affected:

  0704.20.0020   Established   July 1, 2026   484(f)

Also in this update: 3 related change(s), 1053 other change(s).
Full details are in the attached report.
```

### Priorities

| Change | Priority | In the email? |
|---|---|---|
| Added / Removed | High | Yes (watchlist) |
| Listed in the Change Record only | High | Yes (watchlist) |
| Description changed | Medium | Report only |
| Formatting only (whitespace) | Low | Report only |

Related changes are counted in the email and listed in full in the report.

---

## The dashboard

Open **http://localhost:5000** while `start.py` is running.

| Page | What it shows |
|---|---|
| **Home** | Time since the last HTS release took effect, and the latest CPSC-relevant changes |
| **Reports** | The full change table for the latest release, with filters, CSV export, an email preview, and the release history |
| **Watchlist** | Watched HTS codes grouped by category. Add or remove codes |
| **Email List** | Who receives the alert email |
| **Settings** | The check interval, and whether email alerts are on |

Changes made on the dashboard take effect right away. The monitor reads the watchlist, the email list and settings from the same database on every check, so nothing needs a restart.

### How the dashboard ranks changes

The email sorts changes into watchlist, related and other. The dashboard adds a level on top so that new codes in CPSC areas come first:

1. **New in CPSC jurisdiction:** a code added in a chapter that has at least one watched code, or under a watched code
2. **Watchlist:** matches a watched code, or its parent or child
3. **CPSC chapter:** any other change in a chapter that has a watched code
4. **Other**

Because of the chapter-level rule, the dashboard can list more changes as CPSC-relevant than the email does.

### Developing the dashboard

To work on the front end with live reloading, run the API and Vite separately:

```bash
python dashboard/server/api.py               # terminal 1: API on port 5000

cd dashboard
VITE_USE_MOCK=false npm run dev              # terminal 2: dashboard on port 5173
```

Without `VITE_USE_MOCK=false`, `npm run dev` uses a saved snapshot in `dashboard/public/mock/`. That's useful for front-end work without Python, but it is read-only. To refresh the snapshot from the current database:

```bash
python dashboard/server/api.py --export-mock dashboard/public/mock
```

See [`dashboard/README.md`](dashboard/README.md) for the API endpoints.

---

## Configuration

### Paths

Fixed paths and URLs live in `src/ReadFlare/config.py` and rarely need changing.

| Environment variable | Default | Meaning |
|---|---|---|
| `READFLARE_DATA_DIR` | `<repo>/data` | Where the database, downloads and reports are kept |
| `READFLARE_SMTP_PASSWORD` | not set | SMTP password, if your mail server needs one. It is never stored in the database |

### Settings

User settings are stored in the database. Their defaults live in `src/ReadFlare/settings.py`, and only values someone has changed are saved, so a fresh install works with no setup. The check interval, email on/off, and the email list can be changed on the dashboard. The rest can be set from the command line, run from `src/ReadFlare`:

```bash
python -c "import settings; settings.set_setting('smtp_host', 'mailrelay.example.gov')"
python -c "import settings; print(settings.get_all_settings())"
```

| Setting | Default | Meaning |
|---|---|---|
| `check_interval_minutes` | `60` | How often to check for a new release |
| `track_ch99_links` | `False` | Also track Chapter 99 (additional duty) references. See [Chapter 99](#chapter-99) |
| `email_enabled` | `False` | Send alert emails |
| `email_from` | `""` | Address alerts are sent from |
| `email_recipients` | `[]` | Addresses that receive alerts (the dashboard's Email List page) |
| `smtp_host` | `""` | Mail server |
| `smtp_port` | `587` | Mail server port |
| `smtp_use_tls` | `True` | Use STARTTLS |
| `smtp_user` | `""` | Login username. Leave empty for servers that don't need a login |

---

## Email setup

Alerts are sent over standard SMTP, so they work with whatever mail system your organization already uses.

1. Set up the mail server (from `src/ReadFlare`):
   ```bash
   python -c "
   import settings
   settings.set_setting('smtp_host', 'mailrelay.example.gov')
   settings.set_setting('smtp_port', 25)
   settings.set_setting('smtp_use_tls', False)
   settings.set_setting('smtp_user', '')
   settings.set_setting('email_from', 'hts-alerts@example.gov')
   "
   ```
2. Add recipients on the dashboard's **Email List** page.
3. Turn on **email alerts** on the **Settings** page.

### Typical values

| Your situation | Host | Port | TLS | Login |
|---|---|---|---|---|
| Internal SMTP relay | your relay | 25 (ask IT) | Usually off | Usually none. IT allowlists this machine instead |
| Microsoft 365 mailbox | `smtp.office365.com` | 587 | On | Mailbox + password. See the note below |
| Gmail / Google Workspace | `smtp.gmail.com` | 587 | On | Account + app password |
| Local testing (Mailpit) | `localhost` | 1025 | Off | None |

> **Microsoft 365:** Microsoft has been retiring basic username/password login for SMTP in Exchange Online. If password login is refused, ask IT for an internal relay instead.

### Questions to send your IT team

1. Do you have an internal SMTP relay that applications can send through? If so, what are the host and port, and does it need a login or an IP allowlist?
2. What "From" address should these alerts come from?
3. If there's no relay, can you provide a service mailbox, and does it support SMTP login with a password?
4. Who should receive the alerts?

Question 1 usually settles it. With a relay, there's no password to manage.

### Common errors

These appear in the monitor's output, and the run is marked as failed.

| Message | What to do |
|---|---|
| `STARTTLS extension not supported by server` | Turn TLS off (`smtp_use_tls = False`). Common for internal relays |
| `Authentication failed` / `535` | Check `smtp_user` and `READFLARE_SMTP_PASSWORD` |
| `Sender address rejected` | Ask IT which address the app may send as |
| `Recipient address rejected` / `Relay access denied` | The relay may only deliver internally, or this machine needs allowlisting |
| `Connection refused` / `Name or service not known` | Check the host and port, and that this machine can reach the server |

### Testing locally with Mailpit

Mailpit is a fake mail server that catches every email in a local web inbox, so nothing is actually sent.

```bash
podman run -d --name mailpit -p 1025:1025 -p 8025:8025 docker.io/axllent/mailpit
# or: docker run -d --name mailpit -p 1025:1025 -p 8025:8025 axllent/mailpit
```

Use the Mailpit values from the table above, then open <http://localhost:8025> to read the alerts.

---

## Reports

Every processed release saves a report, even when no email is sent:

```
data/reports/hts_changes_<release>_run<N>.html
data/reports/hts_changes_<release>_run<N>.csv
```

- **HTML** is for reading. It shows summary counts, then the watchlist, related and other changes, with the full Change Record wording, before/after descriptions, effective date and source.
- **CSV** is for working with the data in Excel. One row per change.

The same files are attached to the alert email.

---

## Project layout

```
codeRead/
├── start.py                     # starts the monitor, API and dashboard
├── start.bat                    # Windows launcher for start.py
├── requirements.txt             # Python packages for the monitor and the API
├── README.md
│
├── src/ReadFlare/               # the monitor
│   ├── main.py                  # the check loop and the update pipeline
│   ├── config.py                # paths and URLs
│   ├── settings.py              # user settings (stored in the database)
│   ├── engine.py                # release detection, edition download, release cache
│   ├── diff.py                  # edition parsing and comparison
│   ├── changerecord.py          # Change Record download, parsing, reconciliation
│   ├── watchlist.py             # watchlist matching and priorities
│   ├── database.py              # SQLite tables and queries
│   ├── report.py                # email summary, HTML and CSV reports
│   ├── notify.py                # sending email
│   ├── check_change_records.py  # parser regression test
│   └── debug_change_records.py  # shows rows the parser missed
│
├── dashboard/                   # the web dashboard
│   ├── src/                     # React front end (pages, components, api.js)
│   ├── server/
│   │   ├── api.py               # Flask API; also serves the built dashboard
│   │   └── dashboard_report.py  # dashboard ranking, CSV and HTML email preview
│   ├── package.json
│   └── vite.config.js
│
└── data/                        # created at runtime; not in git
    ├── tracker_data.db
    ├── releases.json            # the release list the monitor last fetched
    ├── editions/                # last and latest edition, Change Record PDFs
    ├── reports/                 # generated reports
    └── dl/                      # test downloads
```

---

## Testing the Change Record parser

USITC's Change Record PDFs don't all use the same layout (date formats, header wording, how rows wrap), so the parser has a regression test. It downloads a year's Change Records and checks that the number of rows the parser finds matches a raw count of code lines. Run it from `src/ReadFlare`:

```bash
python check_change_records.py                          # 2026
python check_change_records.py --year 2025 --last 40    # another year
```

Downloads are cached in `data/dl/` and spaced 20 seconds apart. Any revision marked `MISMATCH` can be inspected with:

```bash
python debug_change_records.py    # writes data/dl/debug.txt
```

Rerun this whenever the parser changes, and now and then as new revisions come out.

---

## Chapter 99

Chapter 99 of the HTS holds temporary and additional duties (for example Section 301 and Section 232 tariffs and proclamation tariffs). These change what an importer pays, not how a product is classified, so they're **off by default**.

With `track_ch99_links` turned on, the monitor also:

- reports when a product line gains or loses a footnote pointing to a Chapter 99 heading. That usually means an additional duty started or stopped applying. The Change Record leaves these footnotes out, so the diff is the only place they show up.
- includes Chapter 99 rows from the Change Record.

Footnotes are advisory pointers, so a removed footnote doesn't by itself prove a duty ended.

---

## Things to know

- **The first run only sets a baseline.** Changes are reported from the next release onward.
- **Change Records are not cumulative.** Each one covers a single revision. If releases were skipped (for example the program was off for a while), the diff still catches every change, but only the latest release's Change Record supplies dates and sources.
- **Sources are advisory.** USITC notes that the Change Record is provided for reference and is not part of the legal text of the HTS. Check the official HTS before acting on a classification.
- **Rate changes inside Chapter 99 headings** (for example a heading going from 25% to 50%) show up in the Change Record as `Modified` rows, not in the diff.

---

## Planned

- Mail server settings on the dashboard, with presets and a "send test email" button
- Report history on the dashboard: view, delete or regenerate past reports, and resend an alert
- Automatic retry for alert emails that failed to send
- Per-recipient watchlists
