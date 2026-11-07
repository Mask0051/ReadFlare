from enum import IntEnum
from diff import ChangeType, normalize_code

class Priority(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

PRIORITY = {
    ChangeType.ADDED: Priority.HIGH,
    ChangeType.REMOVED: Priority.HIGH,
    ChangeType.RECORD_ONLY: Priority.HIGH,
    ChangeType.CH99_LINK_CHANGED: Priority.HIGH,
    ChangeType.DESCRIPTION_CHANGED: Priority.MEDIUM,
    ChangeType.FORMATTING_CHANGED: Priority.LOW
}

def find_related(code, watchlist):
    #tracked codes this change sits above or below in hierarchy
    #gets parents and children
    return sorted(
        w for w in watchlist if w != code and (w.startswith(code) or code.startswith(w))
    )

def split_by_watchlist(changes, watchlist):
    #normalize watchlist codes to same standard as changes/diff
    watchlist = {normalize_code(w) for w in watchlist}
    
    result = {"watchlist": [], "related": [], "others": []}

    for change in changes:
        record = {**change, "priority": PRIORITY[change["change_type"]]}
        code = change["code"]

        if code in watchlist:
            result["watchlist"].append(record)
        elif related := find_related(code, watchlist):
            record["related_to"] = related
            result["related"].append(record)
        else:
            result["others"].append(record)

    #sorts from hight to low prio
    for section in result.values():
        section.sort(key=lambda c: c["priority"], reverse=True)

    return result
