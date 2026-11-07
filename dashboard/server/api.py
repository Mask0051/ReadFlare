"""
api.py: JSON API for the CodeREAD dashboard.

Run from the repo root (needs Python 3.11+, because diff.py uses StrEnum):
    pip install -r dashboard/server/requirements.txt
    python dashboard/server/api.py               # http://localhost:5000/api/...

It serves the built dashboard (dashboard/dist) and a JSON API over what the
ReadFlare monitor (src/ReadFlare) produces. It imports ReadFlare's modules and
calls their functions; the watchlist, settings and email list it edits are the
same ones the monitor uses.
  - releases:   engine.load_cached_releases()   (the list main.py last fetched)
  - state:      database.get_last_timestamp(), update_runs / changes tables
  - watchlist:  database.add_htsCode(), remove_htsCode()
  - settings:   settings.get_all_settings(), set_setting()
  - recipients: the "email_recipients" setting, which notify.send_alert uses
  - diff:       data/dl/changes.json when no complete run is stored yet (testing)

Flask docs: https://flask.palletsprojects.com/en/stable/quickstart/
"""

import json
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from datetime import datetime


# Make the ReadFlare modules importable without moving or editing them.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src" / "ReadFlare"))

from flask import Flask, Response, jsonify, request, send_from_directory  # noqa: E402

import config  # noqa: E402
import database  # noqa: E402
import engine  # noqa: E402
import settings  # noqa: E402
import dashboard_report as report  # noqa: E402  (dashboard/server/dashboard_report.py;
# named so it doesn't clash with src/ReadFlare/report.py)

# The built dashboard (npm run build). When it exists, this server also serves
# the web page, so the dashboard and the API share one address:
# http://localhost:5000. /api/* routes are matched first.
DIST_DIR = Path(__file__).resolve().parents[1] / "dist"

app = Flask(__name__, static_folder=str(DIST_DIR), static_url_path="")


@app.get("/")
def index():
    if not (DIST_DIR / "index.html").exists():
        return ("Dashboard not built yet. Run start.py from the repo root, "
                "or `npm run build` in dashboard/.", 404)
    return send_from_directory(DIST_DIR, "index.html")

# The diff output saved by the team (diff.get_diff on two editions).
CHANGES_FILE = config.DATA_DIR / "dl" / "changes.json"

# The email list is the "email_recipients" setting, the same list notify.send_alert uses.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")  # sanity check, not full RFC 5322


def db():
    return closing(sqlite3.connect(config.DB_PATH))


def setup():
    """Same start-up steps as main.py: create tables, seed the watchlist if empty."""
    database.init_db()
    if database.watchlist_is_empty():
        database.watchlist_from_json(config.SEED_WATCHLIST_PATH)


# ---------------------------------------------------------------- helpers ---

def normalize_release(raw):
    return {
        "name": raw["name"],
        "title": raw.get("title"),
        "timestamp": raw["id"]["timestamp"],
        "createdDate": raw.get("date"),
        "creator": raw.get("creator"),
        "status": raw.get("status"),
        "releaseStartDate": raw.get("releaseStartDate"),
        "releaseEndDate": raw.get("releaseEndDate"),
    }


def load_releases():
    """Newest first. The USITC list is not strictly sorted, so sort here."""
    releases = [normalize_release(r) for r in engine.load_cached_releases()]
    releases.sort(key=lambda r: r["timestamp"], reverse=True)
    return releases


def watch_rows():
    """(code, category, chapter) for every watched code."""
    with db() as conn:
        return conn.execute(
            f"SELECT {database.WATCHLIST_TABLE_CODES}, {database.WATCHLIST_TABLE_CATEGORY}, "
            f"{database.WATCHLIST_TABLE_CHAPTER} FROM {database.WATCHLIST_TABLE}"
        ).fetchall()


def latest_run():
    """The newest update_runs row as a dict, or None."""
    with db() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(f"SELECT * FROM {database.RUNS_TABLE} ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        return None
    row = dict(row)
    return {
        "id": row["id"],
        "editionTimestamp": row["edition_timestamp"],
        "processedAt": row["processed_at"],
        "totalChanges": row["total_changes"],
        # The column is spelled alter_status in init_db; read either spelling.
        "alertStatus": row.get("alert_status", row.get("alter_status")),
    }


def run_changes(run_id):
    with db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT code, change_type, old_description, new_description FROM {database.CHANGES_TABLE} "
            "WHERE run_id = ?", (run_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def latest_report():
    """Changes for the latest stored run, or an empty report if none has been processed yet."""
    run = latest_run()
    if run:
        changes = run_changes(run["id"])
        release = next((r for r in load_releases() if r["timestamp"] == run["editionTimestamp"]), None)
        return report.build_report(changes, watch_rows(), release=release, run=run, source="database")
    return report.build_report([], watch_rows(), source="none")

def us_date_to_iso(s):
    # "10/30/2026" -> "2026-10-30", or None
    try:
        return datetime.strptime(s, "%m/%d/%Y").date().isoformat()
    except (TypeError, ValueError):
        return None

# -------------------------------------------------------------- endpoints ---

@app.get("/api/status")
def status():
    releases = load_releases()
    current = next((r for r in releases if r["status"] == "current"), releases[0] if releases else None)
    return jsonify({
        "lastSavedTimestamp": database.get_last_timestamp(settings.get_setting("fallback_timestamp")),
        "currentRelease": current,
        # when the current release took effect; use this for "time since last release"
        "currentReleaseEffective": us_date_to_iso(current.get("releaseStartDate")) if current else None,
        "latestRun": latest_run(),
        "checkIntervalMinutes": settings.get_setting("check_interval_minutes"),
    })


@app.get("/api/releases")
def releases():
    limit = request.args.get("limit", default=50, type=int)
    rs = load_releases()
    return jsonify({"total": len(rs), "releases": rs[:limit]})


@app.get("/api/changes/latest")
def changes_latest():
    return jsonify(latest_report())


@app.get("/api/changes/latest.csv")
def changes_latest_csv():
    return Response(report.build_csv(latest_report()), mimetype="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="hts_changes.csv"'})


@app.get("/api/changes/latest/email")
def changes_latest_email():
    _subject, html = report.build_email(latest_report())
    return Response(html, mimetype="text/html")


# Watchlist: uses database.add_htsCode / remove_htsCode, which validate the code.
@app.get("/api/watchlist")
def watchlist_get():
    rows = sorted(watch_rows(), key=lambda r: (r[1] or "", r[0]))
    return jsonify({"codes": [
        {"code": code, "htsCode": report.format_code(code), "category": category, "chapter": chapter}
        for code, category, chapter in rows
    ]})


@app.post("/api/watchlist")
def watchlist_add():
    body = request.get_json(silent=True) or {}
    try:
        database.add_htsCode(str(body.get("code", "")), (body.get("category") or "").strip() or None)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return watchlist_get()


@app.delete("/api/watchlist/<code>")
def watchlist_remove(code):
    database.remove_htsCode(code)
    return watchlist_get()


# Settings: uses settings.set_setting, which only accepts keys in DEFAULTS.
@app.get("/api/settings")
def settings_get():
    return jsonify(settings.get_all_settings())


@app.put("/api/settings")
def settings_put():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "Expected a JSON object of settings"}), 400

    # check every key first, so a bad value never leaves the settings half saved
    for key, value in body.items():
        if key not in settings.DEFAULTS:
            return jsonify({"error": f"Unknown setting: {key}"}), 400
        expected = type(settings.DEFAULTS[key])
        # bool is a subclass of int in Python, so don't let True pass as a number
        if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
            return jsonify({"error": f"{key} must be {expected.__name__}"}), 400

    for key, value in body.items():
        settings.set_setting(key, value)
    return settings_get()


# Email list: stored in the "email_recipients" setting (settings.py), so the
# addresses added here are the ones notify.send_alert emails.
def list_recipients():
    return sorted(settings.get_setting("email_recipients"))


@app.get("/api/recipients")
def recipients_get():
    return jsonify({"recipients": list_recipients()})


@app.post("/api/recipients")
def recipients_add():
    email = ((request.get_json(silent=True) or {}).get("email") or "").strip().lower()
    if not EMAIL_RE.match(email):
        return jsonify({"error": "Not a valid email address"}), 400
    current = list_recipients()
    if email not in current:
        settings.set_setting("email_recipients", current + [email])
    return recipients_get()


@app.delete("/api/recipients/<email>")
def recipients_remove(email):
    remaining = [e for e in list_recipients() if e != email.lower()]
    settings.set_setting("email_recipients", remaining)
    return recipients_get()


# ------------------------------------------------------------- mock export ---

def export_mock(out_dir):
    """
    Save every GET response as a static file, so the dashboard can run on
    `npm run dev` / `npm run preview` with no Python (VITE_USE_MOCK=true).
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    client = app.test_client()
    files = {
        "status.json": "/api/status",
        "releases.json": "/api/releases?limit=500",
        "changes.json": "/api/changes/latest",
        "watchlist.json": "/api/watchlist",
        "settings.json": "/api/settings",
        "recipients.json": "/api/recipients",
        "email.html": "/api/changes/latest/email",
    }
    for name, url in files.items():
        res = client.get(url)
        if res.status_code != 200:
            raise SystemExit(f"{url} returned HTTP {res.status_code}")
        (out / name).write_bytes(res.data)
        print(f"wrote {out / name}")


if __name__ == "__main__":
    setup()
    if len(sys.argv) == 3 and sys.argv[1] == "--export-mock":
        export_mock(sys.argv[2])
    else:
        # start.py passes --no-debug: the debug reloader would start the server twice.
        app.run(port=5000, debug="--no-debug" not in sys.argv)