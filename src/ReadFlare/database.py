import sqlite3
import json
from contextlib import closing
from config import DB_PATH, DATA_DIR, VALID_CODE_LENGTHS, SEED_WATCHLIST_PATH
from diff import normalize_code

#state table vars
#stores the last seen version's timestamp from
#https://hts.usitc.gov/reststop/releaseList
STATE_TABLE = "system_state"
LAST_CHECK_KEY = "last_check"

#settings table
#stores settings configurable in web portal
SETTINGS_TABLE = "settings"

KV_TABLES = {STATE_TABLE, SETTINGS_TABLE}

#watchlist table
#stores info for tracked HTS codes
WATCHLIST_TABLE = "cpsc_watchlist"
WATCHLIST_TABLE_CODES = "hts_codes"
WATCHLIST_TABLE_CATEGORY = "hts_category"
WATCHLIST_TABLE_CHAPTER = "hts_chapter"

#runs table
#stores info for each edition
RUNS_TABLE = "update_runs"

#changes table
#stores code changes
CHANGES_TABLE = "changes"

#creates the database tables if they dont exist
def init_db():
    #create data dir if not exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    #automatically creates the .db file if it doesnt exist
    with closing(sqlite3.connect(DB_PATH)) as conn:
        with conn:
            cursor = conn.cursor()
            
            #create the state KV table
            cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {STATE_TABLE} (
            key TEXT PRIMARY KEY, value TEXT)""")

            #create the settings KV table
            cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {SETTINGS_TABLE} 
            (key TEXT PRIMARY KEY, value TEXT)""")

            #create watchlist table
            cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {WATCHLIST_TABLE} (
            {WATCHLIST_TABLE_CODES} TEXT PRIMARY KEY,
            {WATCHLIST_TABLE_CATEGORY} TEXT,
            {WATCHLIST_TABLE_CHAPTER} TEXT)""")

            #create runs table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {RUNS_TABLE}(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                edition_timestamp INTEGER NOT NULL,
                release_name TEXT,
                processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                total_changes INTEGER NOT NULL,
                alert_status TEXT NOT NULL DEFAULT 'pending',
                alert_attempts    INTEGER NOT NULL DEFAULT 0,
                last_alert_error  TEXT,
                report_html_path  TEXT,
                report_csv_path   TEXT
                )
            """)

            #create changes table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {CHANGES_TABLE}(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES {RUNS_TABLE}(id),
                code TEXT NOT NULL,
                change_type TEXT NOT NULL,
                old_description TEXT,
                new_description TEXT,
                origin TEXT,
                nature TEXT,
                effective_date TEXT,
                source TEXT,
                priority INTEGER NOT NULL,
                section TEXT NOT NULL,
                related_to TEXT
                )
        """)
    
    print("Database structures validated successfully.")

#KV tables
#general functions for later reuse 
def get_value(table, key, default=None):

    if(table not in KV_TABLES):
        raise ValueError(f"Unknown KV table: {table}")

    with closing(sqlite3.connect(DB_PATH)) as conn:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT value FROM {table} WHERE key = ?", (key,),
            )
            row = cursor.fetchone()
            return row[0] if row else default

def set_value(table, key, value):

    if(table not in KV_TABLES):
        raise ValueError(f"Unknown KV table: {table}")
    
    with closing(sqlite3.connect(DB_PATH)) as conn, conn:
        cursor = conn.cursor()
        cursor.execute(
            f"INSERT OR REPLACE INTO {table} (key, value) VALUES (?, ?)",
            (key, str(value)),
        )

#machine state functions
def get_last_timestamp(default_fallback):
    #gets the last successfully processed timestamp
    value = get_value(STATE_TABLE, LAST_CHECK_KEY)
    if(value is not None):
        return int(value)
    else:
        return default_fallback

def update_last_timestamp(new_timestamp):

    set_value(STATE_TABLE,LAST_CHECK_KEY, new_timestamp)


#watchlist functions
def add_htsCode(hts_code, hts_category):
    hts_code = normalize_code(hts_code)
    if len(hts_code) not in VALID_CODE_LENGTHS:
        raise ValueError(f"Invalid HTS code length: {hts_code}")

    #derive the chapter to reduce input errors
    hts_chapter = hts_code[:2]


    with closing(sqlite3.connect(DB_PATH)) as conn:
        with conn:
            cursor = conn.cursor()

            # add hts code
            cursor.execute(f"""
            INSERT INTO {WATCHLIST_TABLE}
            ({WATCHLIST_TABLE_CODES}, {WATCHLIST_TABLE_CATEGORY}, {WATCHLIST_TABLE_CHAPTER})
            VALUES (?, ?, ?)
            ON CONFLICT ({WATCHLIST_TABLE_CODES}) DO UPDATE SET 
            {WATCHLIST_TABLE_CATEGORY} = excluded.{WATCHLIST_TABLE_CATEGORY},
            {WATCHLIST_TABLE_CHAPTER} = excluded.{WATCHLIST_TABLE_CHAPTER}""",
            (hts_code, hts_category, hts_chapter),)

def remove_htsCode(hts_code):
    hts_code = normalize_code(hts_code)

    with closing(sqlite3.connect(DB_PATH)) as conn:
        with conn:
            cursor = conn.cursor()

            # remove hts code
            cursor.execute(f"""
            DELETE FROM {WATCHLIST_TABLE}
            WHERE {WATCHLIST_TABLE_CODES} = ?
            """, (hts_code,))
            return cursor.rowcount > 0

def get_htsCode(hts_code):
    hts_code = normalize_code(hts_code)

    #returns (code, category, chapter) or None if not on the watchlist
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
        SELECT {WATCHLIST_TABLE_CODES}, {WATCHLIST_TABLE_CATEGORY}, {WATCHLIST_TABLE_CHAPTER}
        FROM {WATCHLIST_TABLE}
        WHERE {WATCHLIST_TABLE_CODES} = ?
        """, (hts_code,))
        return cursor.fetchone()

#returns chapter, category, and code.
def get_all_htsCodes():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
        SELECT {WATCHLIST_TABLE_CHAPTER}, {WATCHLIST_TABLE_CATEGORY}, {WATCHLIST_TABLE_CODES}
        FROM {WATCHLIST_TABLE}
        ORDER BY {WATCHLIST_TABLE_CHAPTER}, {WATCHLIST_TABLE_CATEGORY}, {WATCHLIST_TABLE_CODES}
        """)
        rows = cursor.fetchall()

    codes_table = {}
    for chapter, category, code in rows:
        codes_table.setdefault(chapter, {}).setdefault(category or "Uncategorized", []).append(code)
    return codes_table

#used for split_by_watchlist function
def get_watchlist_codes():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT {WATCHLIST_TABLE_CODES} FROM {WATCHLIST_TABLE}")
        return {row[0] for row in cursor.fetchall()}

#
def watchlist_from_json(path):
    # import watchlist from seed_watchlist.json
    with open(path, encoding="utf-8") as file:
        entries = json.load(file)

    rows = []
    for entry in entries:
        for code in entry["hts_codes"]:
            code = normalize_code(str(code))
            if len(code) not in VALID_CODE_LENGTHS:
                print(f"Skipping invalid code: {code!r}")
                continue
            rows.append((code, entry["category"], code[:2]))


    with closing(sqlite3.connect(DB_PATH)) as conn:
        with conn:
            cursor = conn.cursor()

            # load json watchlist into table
            cursor.executemany(f"""
            INSERT OR REPLACE INTO {WATCHLIST_TABLE}
            ({WATCHLIST_TABLE_CODES}, {WATCHLIST_TABLE_CATEGORY}, {WATCHLIST_TABLE_CHAPTER})
            VALUES (?, ?, ?)
            """, rows)

    print(f"Loaded {len(rows)} HTS codes into {WATCHLIST_TABLE}.")

#returns True if watchlist table is empty
#returns False if not empty
def watchlist_is_empty():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT 1 FROM {WATCHLIST_TABLE} LIMIT 1")
        return cursor.fetchone() is None

#Runs/changes table
def store_run(edition_timestamp, split, release_name=None):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        with conn:
            cursor = conn.cursor()
            total = sum(len(records) for records in split.values())
            cursor.execute(
                f"INSERT INTO {RUNS_TABLE} (edition_timestamp, release_name, total_changes) VALUES (?, ?, ?)",
                (edition_timestamp, release_name, total),
            )

            run_id = cursor.lastrowid

            rows = []

            for section, records in split.items():
                for c in records:
                    related_to = c.get("related_to")
                    related_json = json.dumps(related_to) if related_to else None

                    row = (
                        run_id,
                        c["code"],
                        c["change_type"],
                        c["old_description"],
                        c["new_description"],
                        c["origin"],
                        c["nature"],
                        c["effective_date"],
                        c["source"],
                        int(c["priority"]),
                        section,
                        related_json
                    )
                    rows.append(row)

            cursor.executemany(f"""
                INSERT INTO {CHANGES_TABLE}
                (run_id, code, change_type, old_description, new_description,
                origin, nature, effective_date, source, priority, section, related_to)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, rows)
        
        return run_id

def set_alert_status(run_id, status):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        with conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE {RUNS_TABLE} SET alert_status = ? WHERE id = ?",
            (status, run_id))

def record_alert_attempt(run_id, status, error=None):
    with closing(sqlite3.connect(DB_PATH)) as conn, conn:
        conn.execute(
            f"""UPDATE {RUNS_TABLE}
                SET alert_status = ?, alert_attempts = alert_attempts + 1, last_alert_error = ?
                WHERE id = ?""",
            (status, error, run_id),
        )


def get_runs_to_retry(max_attempts):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        rows = conn.execute(
            f"""SELECT id, release_name FROM {RUNS_TABLE}
                WHERE alert_status = 'failed' AND alert_attempts < ?
                ORDER BY id""",
            (max_attempts,),
        ).fetchall()
    return rows


def set_report_paths(run_id, html_path, csv_path):
    with closing(sqlite3.connect(DB_PATH)) as conn, conn:
        conn.execute(
            f"UPDATE {RUNS_TABLE} SET report_html_path = ?, report_csv_path = ? WHERE id = ?",
            (str(html_path) if html_path else None, str(csv_path) if csv_path else None, run_id),
        )


def get_runs_with_reports(older_than_days=None):
    query = f"""SELECT id, report_html_path, report_csv_path FROM {RUNS_TABLE}
                WHERE report_html_path IS NOT NULL OR report_csv_path IS NOT NULL"""
    params = ()
    if older_than_days is not None:
        query += " AND processed_at < datetime('now', ?)"
        params = (f"-{int(older_than_days)} days",)
    with closing(sqlite3.connect(DB_PATH)) as conn:
        return conn.execute(query, params).fetchall()