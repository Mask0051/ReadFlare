# report.py
# builds the alert email summary and the attached reports (HTML + CSV) for one run,
# straight from the database, so the email, a resend, and the dashboard all match

import csv
import html
import io
import json
import sqlite3
from contextlib import closing
from datetime import date

from config import DB_PATH
from database import RUNS_TABLE, CHANGES_TABLE

SECTION_TITLES = {
    "watchlist": "Watchlist changes",
    "related": "Related changes (parent or child of a watchlist code)",
    "others": "All other changes",
}
PRIORITY_NAMES = {3: "High", 2: "Medium", 1: "Low"}
HIGH = 3


# ---------- data ----------

def get_run(run_id):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(f"SELECT * FROM {RUNS_TABLE} WHERE id = ?", (run_id,)).fetchone()
    return dict(row) if row else None


def get_run_changes(run_id):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""SELECT * FROM {CHANGES_TABLE}
                WHERE run_id = ?
                ORDER BY priority DESC, code""",
            (run_id,),
        ).fetchall()

    changes = []
    for r in rows:
        c = dict(r)
        c["related_to"] = json.loads(c["related_to"]) if c.get("related_to") else []
        changes.append(c)

    # watchlist first, then related, then others; highest priority first within each
    order = {key: i for i, key in enumerate(SECTION_TITLES)}
    changes.sort(key=lambda c: (order.get(c["section"], 99), -c["priority"], c["code"]))
    return changes


# ---------- formatting helpers ----------

def format_code(code):
    # matches the change record's style: "0704200000" -> "0704.20.0000", "99038570" -> "9903.85.70"
    if len(code) == 10:
        return f"{code[:4]}.{code[4:6]}.{code[6:]}"
    parts = [code[:4], code[4:6], code[6:8]]
    return ".".join(p for p in parts if p)


def format_date(iso):
    # "2026-07-01" -> "July 1, 2026"; anything else is shown as-is
    if not iso:
        return ""
    try:
        d = date.fromisoformat(iso)
        return f"{d:%B} {d.day}, {d.year}"
    except ValueError:
        return iso


def what_happened(c):
    # prefer the change record's wording ("Established (transferred from ...)"),
    # fall back to the diff's change type when the record didn't list it
    return c.get("nature") or c["change_type"]


def release_label(run):
    return run.get("release_name") or f"edition {run['edition_timestamp']}"


def counts_by_section(changes):
    counts = {"watchlist": 0, "related": 0, "others": 0}
    for c in changes:
        counts[c["section"]] = counts.get(c["section"], 0) + 1
    return counts


# ---------- email summary ----------

def build_email_summary(run_id):
    # returns (subject, body), or None if no high priority watchlist codes changed
    run = get_run(run_id)
    changes = get_run_changes(run_id)
    high = [c for c in changes if c["section"] == "watchlist" and c["priority"] >= HIGH]
    if not high:
        return None

    counts = counts_by_section(changes)
    label = release_label(run)
    subject = f"HTS update: {len(high)} watchlist code(s) affected ({label})"

    # one short line per code; the full wording ("transferred to ...") is in the report
    rows = [
        (format_code(c["code"]),
         (c.get("nature") or c["change_type"]).split(" (")[0],
         format_date(c.get("effective_date")) or "-",
         c.get("source") or "-")
        for c in high
    ]
    widths = [max(len(r[i]) for r in rows) for i in range(3)]

    lines = [f"HTS update: {label}", "", "Watchlist codes affected:", ""]
    for code, what, when, source in rows:
        lines.append(f"  {code:<{widths[0]}}   {what:<{widths[1]}}   {when:<{widths[2]}}   {source}")

    other_watch = counts["watchlist"] - len(high)
    extras = []
    if other_watch:
        extras.append(f"{other_watch} lower priority watchlist change(s)")
    if counts["related"]:
        extras.append(f"{counts['related']} related change(s)")
    if counts["others"]:
        extras.append(f"{counts['others']} other change(s)")

    lines.append("")
    if extras:
        lines.append("Also in this update: " + ", ".join(extras) + ".")
    lines.append("Full details are in the attached report.")
    return subject, "\n".join(lines)


# ---------- CSV report ----------

CSV_COLUMNS = ["section", "priority", "code", "change", "nature", "effective_date",
               "source", "old_description", "new_description", "related_to", "found_by"]

ORIGIN_LABELS = {"both": "Diff + Change Record", "diff": "Diff only", "record": "Change Record only"}


def build_report_csv(run_id):
    changes = get_run_changes(run_id)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for c in changes:
        writer.writerow([
            c["section"],
            PRIORITY_NAMES.get(c["priority"], c["priority"]),
            format_code(c["code"]),
            c["change_type"],
            c.get("nature") or "",
            c.get("effective_date") or "",
            c.get("source") or "",
            c.get("old_description") or "",
            c.get("new_description") or "",
            " ".join(format_code(r) for r in c["related_to"]),
            ORIGIN_LABELS.get(c.get("origin"), c.get("origin") or ""),
        ])
    return buf.getvalue()


# ---------- HTML report ----------

STYLE = """
body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
       color: #1f2328; background: #ffffff; margin: 0; padding: 24px; line-height: 1.45; }
main { max-width: 1100px; margin: 0 auto; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 17px; margin: 32px 0 8px; padding-bottom: 6px; border-bottom: 1px solid #d0d7de; }
.meta { color: #59636e; margin: 0 0 20px; }
.cards { display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0; }
.card { border: 1px solid #d0d7de; border-radius: 8px; padding: 10px 16px; min-width: 130px; }
.card b { display: block; font-size: 22px; font-variant-numeric: tabular-nums; }
.card span { color: #59636e; font-size: 13px; }
.card.alert { border-color: #cf222e; }
.card.alert b { color: #cf222e; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; vertical-align: top; padding: 7px 10px; border-bottom: 1px solid #eaeef2; }
th { background: #f6f8fa; font-weight: 600; position: sticky; top: 0; }
td.code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; white-space: nowrap; }
td.nowrap { white-space: nowrap; }
.pill { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }
.p3 { background: #ffebe9; color: #a40e26; }
.p2 { background: #fff8c5; color: #7d4e00; }
.p1 { background: #eaeef2; color: #59636e; }
.was { color: #59636e; }
.small { color: #59636e; font-size: 12px; }
.empty { color: #59636e; font-style: italic; }
@media print { th { position: static; } body { padding: 0; } }
"""


def _e(text):
    return html.escape(str(text or ""))


def _row_html(c, show_related):
    old, new = c.get("old_description"), c.get("new_description")
    if old and new and old != new:
        desc = f'<div class="was">Before: {_e(old)}</div><div>After: {_e(new)}</div>'
    else:
        desc = _e(new or old)

    related = ""
    if show_related and c["related_to"]:
        related = f'<div class="small">Related to: {_e(", ".join(format_code(r) for r in c["related_to"]))}</div>'

    p = c["priority"]
    return (
        "<tr>"
        f'<td><span class="pill p{p}">{PRIORITY_NAMES.get(p, p)}</span></td>'
        f'<td class="code">{_e(format_code(c["code"]))}</td>'
        f"<td>{_e(what_happened(c))}{related}</td>"
        f"<td>{desc}</td>"
        f"<td class=\"nowrap\">{_e(format_date(c.get('effective_date')))}</td>"
        f"<td>{_e(c.get('source'))}</td>"
        f'<td class="small">{_e(ORIGIN_LABELS.get(c.get("origin"), ""))}</td>'
        "</tr>"
    )


def _section_html(key, changes):
    rows = [c for c in changes if c["section"] == key]
    out = [f"<h2>{_e(SECTION_TITLES[key])} ({len(rows)})</h2>"]
    if not rows:
        out.append('<p class="empty">None in this update.</p>')
        return "\n".join(out)
    out.append(
        "<table><thead><tr><th>Priority</th><th>Code</th><th>Change</th>"
        "<th>Description</th><th>Effective</th><th>Source</th><th>Found by</th>"
        "</tr></thead><tbody>"
    )
    out.extend(_row_html(c, show_related=(key == "related")) for c in rows)
    out.append("</tbody></table>")
    return "\n".join(out)


def build_report_html(run_id):
    run = get_run(run_id)
    changes = get_run_changes(run_id)
    counts = counts_by_section(changes)
    label = release_label(run)
    high = sum(1 for c in changes if c["section"] == "watchlist" and c["priority"] >= HIGH)
    origins = {o: sum(1 for c in changes if c.get("origin") == o) for o in ORIGIN_LABELS}

    cards = [
        ("alert" if high else "", high, "High priority watchlist"),
        ("", counts["watchlist"], "Watchlist changes"),
        ("", counts["related"], "Related changes"),
        ("", counts["others"], "Other changes"),
    ]
    cards_html = "".join(
        f'<div class="card {cls}"><b>{n}</b><span>{_e(text)}</span></div>' for cls, n, text in cards
    )
    recon = " · ".join(f"{_e(ORIGIN_LABELS[o])}: {n}" for o, n in origins.items())

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HTS Change Report: {_e(label)}</title>
<style>{STYLE}</style>
</head>
<body>
<main>
<h1>HTS Change Report: {_e(label)}</h1>
<p class="meta">Processed {_e(run.get("processed_at"))} UTC · {len(changes)} total changes</p>
<div class="cards">{cards_html}</div>
<p class="small">How changes were found: {recon}</p>
{_section_html("watchlist", changes)}
{_section_html("related", changes)}
{_section_html("others", changes)}
</main>
</body>
</html>
"""