import re
from enum import StrEnum
import json
from collections import Counter

CH99_REF = re.compile(r"9903\.\d{2}\.\d{2}")

class ChangeType(StrEnum):
    ADDED = "Added"
    REMOVED = "Removed"
    DESCRIPTION_CHANGED = "Description Changed"
    FORMATTING_CHANGED = "Formatting Changed"
    RECORD_ONLY = "Change Record Only"
    CH99_LINK_CHANGED = "Chapter 99 Link Changed"

def normalize_code(htsno):
    # "2404.19.05.10" -> "2404190510"
    return re.sub(r"\D", "", htsno)


def normalize_description(description):
    # strip ends and collapse repeated whitespace so spacing alone isn't a "change"
    if description is None:
        return ""
    return re.sub(r"\s+", " ", description).strip()


def parse_edition(entries):
    # turns the exportList / archive JSON (a list of entries) into {code: description}
    codes = {}
    duplicates = []

    for entry in entries:
        htsno = entry.get("htsno")
        if not htsno:
            # grouping text lines have no code; skip them
            continue

        code = normalize_code(htsno)
        if not code:
            continue

        if code in codes:
            duplicates.append(code)

        codes[code] = normalize_description(entry.get("description"))

    if duplicates:
        print(f"WARNING: {len(duplicates)} duplicate codes found, e.g. {duplicates[:5]}")

    return codes


def whitespace_insensitive(s):
    # drop all whitespace so spacing-only edits (like "chapterand" -> "chapter and") compare equal
    return re.sub(r"\s+", "", s or "")


def diff_editions(old, new):
    # compares two {code: description} dicts and returns a list of change records
    old_keys = set(old)
    new_keys = set(new)
    changes = []

    for code in sorted(new_keys - old_keys):
        changes.append({
            "code": code,
            "change_type": ChangeType.ADDED,
            "old_description": "",
            "new_description": new[code],
        })

    for code in sorted(old_keys - new_keys):
        changes.append({
            "code": code,
            "change_type": ChangeType.REMOVED,
            "old_description": old[code],
            "new_description": "",
        })

    for code in sorted(old_keys & new_keys):
        if old[code] == new[code]:
            continue
        if whitespace_insensitive(old[code]) == whitespace_insensitive(new[code]):
            change_type = ChangeType.FORMATTING_CHANGED
        else:
            change_type = ChangeType.DESCRIPTION_CHANGED
        changes.append({
            "code": code,
            "change_type": change_type,
            "old_description": old[code],
            "new_description": new[code],
        })

    return changes

def get_diff(last_edition_path, latest_edition_path, include_ch99=False):
    with open(last_edition_path, "r", encoding="utf-8") as f:
        old_entries = json.load(f)
    with open(latest_edition_path, "r", encoding="utf-8") as f:
        new_entries = json.load(f)

    old = parse_edition(old_entries)
    new = parse_edition(new_entries)

    changes = diff_editions(old, new)

    #if tracking chapter 99 is enabled
    if include_ch99:
        changes.extend(diff_ch99_refs(
            parse_ch99_refs(old_entries),
            parse_ch99_refs(new_entries),
            set(old) & set(new),))

    print(f"Old: {len(old)} codes | New: {len(new)} codes | Changes: {len(changes)}")
    print(Counter(c["change_type"].name for c in changes))

    return changes, old, new

def parse_ch99_refs(entries):
    # {code: {"9903.90.08 (other)", ...}} for lines whose footnotes point to chapter 99
    refs = {}
    for entry in entries:
        htsno = entry.get("htsno")
        if not htsno:
            continue
        code = normalize_code(htsno)
        for note in entry.get("footnotes") or []:
            columns = ", ".join(note.get("columns") or [])
            for ref in CH99_REF.findall(note.get("value") or ""):
                label = f"{ref} ({columns})" if columns else ref
                refs.setdefault(code, set()).add(label)
    return refs


def diff_ch99_refs(old_refs, new_refs, codes_in_both):
    # codes in both editions that gained or lost a chapter 99 footnote
    changes = []
    for code in sorted(codes_in_both):
        before = old_refs.get(code, set())
        after = new_refs.get(code, set())
        if before == after:
            continue
        changes.append({
            "code": code,
            "change_type": ChangeType.CH99_LINK_CHANGED,
            "old_description": ", ".join(sorted(before)) or "(no chapter 99 references)",
            "new_description": ", ".join(sorted(after)) or "(no chapter 99 references)",
        })
    return changes



# if __name__ == "__main__":
    
#     with open("testEdition.json", "r", encoding="utf-8") as f:
#         old_entries = json.load(f)
#     with open("latestEdition.json", "r", encoding="utf-8") as f:
#         new_entries = json.load(f)

#     old = parse_edition(old_entries)
#     new = parse_edition(new_entries)
#     changes = diff_editions(old, new)

#     print(f"Old: {len(old)} codes | New: {len(new)} codes | Changes: {len(changes)}")
#     print(Counter(c["change_type"].name for c in changes))

#     with open("changes.json", "w") as f:
#         # for change in changes:
#         #     print(change["change_type"].name, change["code"], "|",
#         #           change["old_description"], "->", change["new_description"], file=f)

#         json.dump(changes, f, indent=2)