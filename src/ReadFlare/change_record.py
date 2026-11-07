# changerecord.py
# download, parse, and reconcile the HTS Change Record with the diff
#
# pipeline:
#   fetch_change_record(release) -> pdf path
#   extract_text(pdf path)       -> text
#   parse_change_record(text)    -> [record rows]
#   reconcile(rows, changes)     -> changes enriched with nature / effective_date / source

import re
import subprocess
from datetime import datetime

import requests

from config import EDITIONS_DIR
from diff import ChangeType

try:
    from config import USER_AGENT
except ImportError:
    USER_AGENT = "ReadFlare/0.1"

CHANGE_RECORD_URL = "https://hts.usitc.gov/reststop/file"

# header text varies a little between revisions ("Effective date" sometimes wraps
# so "date" lands on the next line by itself), so only match the stable start
HEADER_RE = re.compile(r"Item changed\s+Nature of change", re.IGNORECASE)   # Rev 17 uses "Item Changed"
HEADER_WRAP_RE = re.compile(r"^\s*date\s*$", re.IGNORECASE)
GLOSSARY_RE = re.compile(r"^\s*Term\s{2,}Meaning\s*$", re.IGNORECASE)
MONTHS = ("January|February|March|April|May|June|July|August|September|"
          "October|November|December")
# two date styles appear across revisions: "July 1, 2026" and "7/31/2026"
DATE_RE = re.compile(rf"(?:{MONTHS}) \d{{1,2}}, \d{{4}}|\b\d{{1,2}}/\d{{1,2}}/\d{{4}}\b")
# accepts both 10-digit styles: 0201.30.50.85 and 0201.30.5085
CODE_RE = re.compile(r"^\d{4}(?:\.\d{2}(?:\.\d{2}(?:\.?\d{2})?)?)?$")
VALID_LENGTHS = {4, 6, 8, 10}
GAP_RE = re.compile(r"\s{2,}")
CHUNK_RE = re.compile(r"\S+(?: \S+)*")
# a date line whose text starts this far in has an empty item column; the
# item (code) is printed on the next line instead (seen in Rev 11)
ITEM_INDENT = 8


def to_iso_date(text):
    # "July 1, 2026" or "7/31/2026" -> "2026-07-01" / "2026-07-31"
    for fmt in ("%B %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return text


def is_complete_code(item):
    item = item.strip()
    return bool(CODE_RE.match(item)) and len(re.sub(r"\D", "", item)) in VALID_LENGTHS


# ---------- 1. download ----------

def fetch_change_record(release_name):
    # download the change record PDF for one release (e.g. "2026HTSRev22")
    # returns the Path to the saved PDF, or None if it couldn't be fetched
    try:
        res = requests.get(
            CHANGE_RECORD_URL,
            params={"release": release_name, "filename": "Change Record"},
            headers={"User-Agent": USER_AGENT},
            timeout=60,
        )
        res.raise_for_status()
    except requests.RequestException as e:
        print(f"Change record fetch failed for {release_name}: {e}")
        return None

    # the server sends application/octet-stream, so check the bytes instead
    if not res.content.startswith(b"%PDF"):
        print(f"Change record for {release_name} is not a PDF")
        return None

    EDITIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = EDITIONS_DIR / f"change_record_{release_name}.pdf"
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_bytes(res.content)
    tmp_path.replace(path)
    return path


# ---------- 2. extract text ----------

def extract_text(pdf_path):
    # -layout keeps the table columns lined up, which the parser relies on
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


# ---------- 3. parse ----------

def parse_change_record(text):
    # returns [{code, nature, effective_date, source}] for HTS code rows only
    rows = []
    in_table = False
    nature_col = date_col = None   # column positions taken from the last real row

    for line in text.splitlines():
        if GLOSSARY_RE.match(line):
            break                          # glossary at the end is not data
        if HEADER_RE.search(line):
            in_table = True                # header repeats on every page
            continue
        if not in_table or not line.strip():
            continue
        if HEADER_WRAP_RE.match(line):
            continue                       # second line of a wrapped header, not row text
        if line.strip().isdigit():
            # a lone number left of the source column is a page number;
            # in the source column it's a wrapped citation ("91 Fed. Reg." / "7107")
            pos = len(line) - len(line.lstrip())
            if date_col is None or pos < date_col:
                continue

        date = DATE_RE.search(line)
        if date:
            # a real row: item and nature sit left of the date
            left = line[:date.start()].rstrip()
            stripped = left.lstrip()
            offset = len(left) - len(stripped)
            gap = GAP_RE.search(stripped)
            if offset >= ITEM_INDENT:
                # item column is empty; the code comes on the next line
                item, nature = "", stripped
                nature_col = offset
            elif gap:
                item, nature = stripped[:gap.start()], stripped[gap.end():]
                nature_col = offset + gap.end()
            else:
                item, nature = stripped, ""
                nature_col = None
            date_col = date.start()
            rows.append({
                "item": item.strip(),
                "nature": nature.strip(),
                "effective_date": to_iso_date(date.group()),
                "source": line[date.end():].strip(),
            })
            continue

        if not rows:
            continue

        # continuation of a wrapped row: put each chunk in a column by its position
        last = rows[-1]
        for chunk in CHUNK_RE.finditer(line):
            pos, piece = chunk.start(), chunk.group()
            if date_col is not None and pos >= date_col:
                last["source"] = (last["source"] + " " + piece).strip()
            elif nature_col is not None and pos >= nature_col - 2:
                last["nature"] = (last["nature"] + " " + piece).strip()
            elif is_complete_code(last["item"]):
                # codes never wrap, so item text under a finished code is a new,
                # dateless row (e.g. "Statistical Annex A" in Rev 5); keep it
                # separate so it doesn't corrupt the code row above
                last = {"item": piece, "nature": "", "effective_date": "", "source": ""}
                rows.append(last)
            else:
                last["item"] = (last["item"] + " " + piece).strip()

    # note rows (U.S. notes, annexes) were parsed only so their wrapped lines
    # don't leak into code rows; keep HTS code rows that have a date
    code_rows = []
    for row in rows:
        if is_complete_code(row["item"]) and row["effective_date"]:
            code_rows.append({
                "code": re.sub(r"\D", "", row["item"]),
                "nature": row["nature"],
                "effective_date": row["effective_date"],
                "source": row["source"],
            })
    return code_rows


def get_change_record(release_name):
    # download + extract + parse in one call; returns [] on any failure
    # so a broken PDF never stops the diff pipeline
    pdf_path = fetch_change_record(release_name)
    if pdf_path is None:
        return []
    try:
        return parse_change_record(extract_text(pdf_path))
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"Could not read change record {pdf_path}: {e}")
        return []


# ---------- 4. reconcile with the diff ----------

def reconcile(record_rows, changes, include_ch99=False):
    # attaches nature / effective_date / source to each diff change,
    # and turns unmatched record rows into their own change records
    #
    # every change gets an "origin":
    #   "both"   - found by the diff and listed in the change record
    #   "diff"   - found by the diff only (USITC didn't list it)
    #   "record" - listed in the change record only (often a rate or ch. 99 change)
    if not include_ch99:
        record_rows = [r for r in record_rows if not r["code"].startswith("99")]

    index = {}
    for row in record_rows:
        index.setdefault(row["code"], row)   # first row wins on duplicates

    used = set()
    for change in changes:
        code = change["code"]
        match = None
        # the record usually lists 8-digit lines, the diff 10-digit codes,
        # so use the longest record code that prefixes this change's code
        for length in (10, 8, 6, 4):
            if len(code) >= length and code[:length] in index:
                match = index[code[:length]]
                break

        if match:
            used.add(match["code"])
            change["origin"] = "both"
            change["nature"] = match["nature"]
            change["effective_date"] = match["effective_date"]
            change["source"] = match["source"]
        else:
            change["origin"] = "diff"
            change["nature"] = None
            change["effective_date"] = None
            change["source"] = None

    record_only = []
    for code, row in index.items():
        if code in used:
            continue
        record_only.append({
            "code": code,
            "change_type": ChangeType.RECORD_ONLY,
            "old_description": "",
            "new_description": "",
            "origin": "record",
            "nature": row["nature"],
            "effective_date": row["effective_date"],
            "source": row["source"],
        })

    matched = sum(1 for c in changes if c["origin"] == "both")
    print(f"Change record: {len(record_rows)} rows | matched: {matched} | "
          f"diff only: {len(changes) - matched} | record only: {len(record_only)}")

    return changes + record_only