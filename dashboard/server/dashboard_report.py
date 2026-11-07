"""
dashboard_report.py: turns the diff output into what the dashboard and the email show.

Input is the list that diff.get_diff() returns (or the rows stored in the
changes table): {code, change_type, old_description, new_description}.

On top of that this module adds a "relevance" bucket and a plain-English
reason for each change, then builds:
  - the JSON the dashboard reads (build_report),
  - a CSV of the change table (build_csv),
  - the formatted HTML alert email (build_email).

Relevance buckets, most important first (sponsor notes, Nov 2026):
  new_in_jurisdiction  a NEW code in a chapter CPSC watches, or under a watched code.
                       "Something new in jurisdiction ... include in summary but as most important."
  watchlist            any other change to a watched code or its parent/child codes
                       (same parent/child rule as watchlist.find_related).
  cpsc_chapter         any other change in a chapter that has watched codes.
  other                everything else (e.g. chapter 99, food, chemicals).

"Chapter CPSC watches" = any chapter that has at least one code on the
watchlist (cpsc_watchlist table, seeded from data/seed_watchlist.json).
"""

import csv
import io
from html import escape

# These come from src/ReadFlare (api.py puts that folder on sys.path).
# Nothing in src/ReadFlare is modified; we only call its functions.
from diff import ChangeType, normalize_code
from watchlist import PRIORITY, find_related

NEW_IN_JURISDICTION = "new_in_jurisdiction"
WATCHLIST = "watchlist"
CPSC_CHAPTER = "cpsc_chapter"
OTHER = "other"

RELEVANCE_ORDER = [NEW_IN_JURISDICTION, WATCHLIST, CPSC_CHAPTER, OTHER]

RELEVANCE_LABELS = {
    NEW_IN_JURISDICTION: "New in CPSC jurisdiction",
    WATCHLIST: "Watchlist code changed",
    CPSC_CHAPTER: "Other change in a CPSC chapter",
    OTHER: "Outside CPSC scope",
}


def format_code(code):
    """'8703210110' -> '8703.21.01.10', the way hts.usitc.gov writes codes."""
    code = normalize_code(code)
    parts = [code[:4], code[4:6], code[6:8], code[8:10]]
    return ".".join(p for p in parts if p)


def build_watch_index(watch_rows):
    """
    watch_rows: iterable of (code, category, chapter) from the watchlist table.
    Returns lookups used by classify():
      codes: {code: category}
      chapters: {chapter: sorted list of categories in that chapter}
    """
    codes = {}
    chapters = {}
    for code, category, chapter in watch_rows:
        code = normalize_code(code)
        codes[code] = category or "Uncategorized"
        chapters.setdefault(str(chapter).zfill(2), set()).add(category or "Uncategorized")
    return {"codes": codes, "chapters": {ch: sorted(cats) for ch, cats in chapters.items()}}


def _short_list(items, limit=3):
    """['a','b','c','d'] -> 'a, b, c and 1 more'"""
    items = list(items)
    if len(items) <= limit:
        return ", ".join(items)
    return f"{', '.join(items[:limit])} and {len(items) - limit} more"


def classify(change, index):
    """Returns (relevance, reason, categories, related_to) for one change."""
    code = normalize_code(change["code"])
    chapter = code[:2]
    is_new = str(change["change_type"]) == ChangeType.ADDED

    watched = index["codes"]
    related = [] if code in watched else find_related(code, watched)
    chapter_categories = index["chapters"].get(chapter, [])

    if code in watched:
        categories = [watched[code]]
        reason = f"This code is on the watchlist ({categories[0]})."
    elif related:
        categories = sorted({watched[r] for r in related})
        reason = (f"Parent or child of watched code {_short_list(format_code(r) for r in related)} "
                  f"({_short_list(categories)}).")
    elif chapter_categories:
        categories = chapter_categories
        reason = f"Chapter {chapter} has watched codes for {_short_list(categories)}."
    else:
        return OTHER, f"Chapter {chapter} has no watched codes.", [], []

    if is_new:
        relevance = NEW_IN_JURISDICTION
        reason = "New code. " + reason
    elif code in watched or related:
        relevance = WATCHLIST
    else:
        relevance = CPSC_CHAPTER
    return relevance, reason, categories, [format_code(r) for r in related]


def build_report(changes, watch_rows, release=None, run=None, source="database"):
    """
    The JSON the dashboard reads from /api/changes/latest.
    changes: diff records (dicts with code, change_type, old_description, new_description).
    release: the matching releaseList entry (name/title), if known.
    run: the update_runs row (id, processed_at, ...), or None when read from a file.
    """
    index = build_watch_index(watch_rows)
    out = []
    for c in changes:
        relevance, reason, categories, related_to = classify(c, index)
        change_type = str(c["change_type"])
        code = normalize_code(c["code"])
        out.append({
            "code": code,
            "htsCode": format_code(code),
            "chapter": code[:2],
            "changeType": change_type,
            "before": c.get("old_description") or None,
            "after": c.get("new_description") or None,
            "priority": int(PRIORITY[ChangeType(change_type)]),  # 3 high .. 1 low, from watchlist.py
            "relevance": relevance,
            "reason": reason,
            "categories": categories,
            "relatedTo": related_to,
        })

    # Most important first, then higher change-type priority, then by code.
    out.sort(key=lambda c: (RELEVANCE_ORDER.index(c["relevance"]), -c["priority"], c["code"]))
    counts = {r: sum(1 for c in out if c["relevance"] == r) for r in RELEVANCE_ORDER}

    return {
        "source": source,
        "release": release,
        "run": run,
        "jurisdictionChapters": sorted(index["chapters"]),
        "counts": counts,
        "total": len(out),
        "changes": out,
    }


# ----------------------------------------------------------------------------
# CSV ("table of HTS codes, export to CSV")
# ----------------------------------------------------------------------------

CSV_COLUMNS = ["hts_code", "chapter", "change_type", "relevance", "old_description",
               "new_description", "categories", "related_to", "reason"]


def build_csv(report):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(CSV_COLUMNS)
    for c in report["changes"]:
        w.writerow([c["htsCode"], c["chapter"], c["changeType"], c["relevance"],
                    c["before"] or "", c["after"] or "", "; ".join(c["categories"]),
                    "; ".join(c["relatedTo"]), c["reason"]])
    return out.getvalue()


# ----------------------------------------------------------------------------
# HTML email. Email clients (Outlook especially) ignore <style> blocks, so
# everything is inline styles and plain tables.
# ----------------------------------------------------------------------------

SECTION_STYLE = {
    NEW_IN_JURISDICTION: ("#a32121", "#fbe3e3",
                          "New codes in chapters CPSC watches, or under a watched code. Review these first."),
    WATCHLIST: ("#8a5a00", "#fdf1d8",
                "Watched codes (or their parent/child codes) that were removed or reworded. "
                "Check any targeting rule that uses them."),
    CPSC_CHAPTER: ("#1f4ea8", "#e2ebfb",
                   "Removed or reworded codes in chapters that have watched codes."),
}


def _rows(changes):
    rows = []
    for c in changes:
        if c["before"] and c["after"]:
            desc = (f'<span style="color:#5d6b7c;text-decoration:line-through">{escape(c["before"])}</span>'
                    f'<br>{escape(c["after"])}')
        else:
            desc = escape(c["after"] or c["before"] or "")
        rows.append(f"""
        <tr>
          <td style="padding:8px 10px 8px 0;border-top:1px solid #dde2e8;vertical-align:top;white-space:nowrap;font-family:Consolas,monospace;font-weight:600">{escape(c["htsCode"])}</td>
          <td style="padding:8px 10px 8px 0;border-top:1px solid #dde2e8;vertical-align:top;white-space:nowrap;color:#4a5563">{escape(c["changeType"])}</td>
          <td style="padding:8px 0;border-top:1px solid #dde2e8;vertical-align:top">{desc}
            <div style="font-size:12px;color:#5d6b7c;margin-top:2px">{escape(c["reason"])}</div></td>
        </tr>""")
    return "".join(rows)


def _section(report, relevance):
    changes = [c for c in report["changes"] if c["relevance"] == relevance]
    if not changes:
        return ""
    fg, _bg, subtitle = SECTION_STYLE[relevance]
    title = RELEVANCE_LABELS[relevance]
    if relevance == NEW_IN_JURISDICTION:
        title = "Most important: " + title
    return f"""
  <h2 style="font-size:16px;margin:28px 0 4px;color:{fg}">{escape(title)} ({len(changes)})</h2>
  <p style="margin:0 0 8px;font-size:13px;color:#5d6b7c">{subtitle}</p>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;line-height:1.4">{_rows(changes)}
  </table>"""


def _stat(n, label, fg, bg):
    return (f'<td style="padding:0 3px;width:25%"><div style="background:{bg};color:{fg};border-radius:8px;padding:10px 12px">'
            f'<div style="font-size:22px;font-weight:700">{n}</div><div style="font-size:12px">{label}</div></div></td>')


def build_email(report):
    """Returns (subject, html)."""
    n = report["counts"]
    release = report.get("release") or {}
    title = release.get("title") or release.get("name") or "New HTS release"
    subject = (f"HTS {title}: {n[NEW_IN_JURISDICTION]} new in CPSC jurisdiction, "
               f"{n[WATCHLIST]} watchlist changes")

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{escape(subject)}</title></head>
<body style="margin:0;background:#f6f7f9;font-family:Segoe UI,Roboto,Arial,sans-serif;color:#1c2430">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f7f9"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="680" cellpadding="0" cellspacing="0" style="max-width:680px;width:100%;background:#ffffff;border:1px solid #dde2e8;border-radius:10px">
<tr><td style="padding:24px 28px">
  <div style="font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:#5d6b7c">CodeREAD HTS change alert</div>
  <h1 style="font-size:22px;margin:4px 0 2px">{escape(title)}</h1>
  <div style="font-size:13px;color:#5d6b7c">{report["total"]} code changes compared with the previous edition</div>

  <table role="presentation" cellpadding="0" cellspacing="0" style="margin:18px 0 0;width:100%"><tr>
    {_stat(n[NEW_IN_JURISDICTION], "New in CPSC jurisdiction", "#a32121", "#fbe3e3")}
    {_stat(n[WATCHLIST], "Watchlist codes changed", "#8a5a00", "#fdf1d8")}
    {_stat(n[CPSC_CHAPTER], "Other in CPSC chapters", "#1f4ea8", "#e2ebfb")}
    {_stat(n[OTHER], "Outside CPSC scope", "#4a5563", "#eceff3")}
  </tr></table>

  {_section(report, NEW_IN_JURISDICTION)}
  {_section(report, WATCHLIST)}
  {_section(report, CPSC_CHAPTER)}

  <p style="font-size:13px;color:#4a5563;margin:28px 0 0">
    {n[OTHER]} other changes are outside the chapters CPSC watches. They are included in the attached CSV.
  </p>
  <p style="font-size:12px;color:#5d6b7c;margin:16px 0 0;border-top:1px solid #dde2e8;padding-top:12px">
    Relevance is based on the CodeREAD watchlist: a chapter counts as CPSC jurisdiction when it has at
    least one watched code. Verify against the official USITC change record before acting.
  </p>
</td></tr></table>
</td></tr></table>
</body></html>"""
    return subject, html
