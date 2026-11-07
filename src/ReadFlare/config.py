"""
config.py: fixed paths, URLs and constants.

These are set before the program starts and are not meant to be changed by users.
User-changeable settings (check interval, email, etc.) live in settings.py and the database.
"""

import os
from pathlib import Path


# ------------------------------------------------------------------- paths ---

# repo root: src/ReadFlare/config.py -> codeRead/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# runtime data (database, downloads, reports); override with READFLARE_DATA_DIR
DATA_DIR = Path(os.environ.get("READFLARE_DATA_DIR", PROJECT_ROOT / "data"))

# SQLite database
DB_PATH = DATA_DIR / "tracker_data.db"

# downloaded HTS editions and Change Record PDFs
EDITIONS_DIR = DATA_DIR / "editions"
LAST_EDITION_PATH = EDITIONS_DIR / "lastEdition.json"      # previous edition (the baseline)
LATEST_EDITION_PATH = EDITIONS_DIR / "latestEdition.json"  # newly fetched edition

# generated HTML and CSV reports
REPORTS_DIR = DATA_DIR / "reports"

# the release list the monitor last fetched (the dashboard reads this)
RELEASES_CACHE_PATH = DATA_DIR / "releases.json"

# starting watchlist, loaded only when the watchlist table is empty
# (lives outside data/ so it's included in the repo)
SEED_WATCHLIST_PATH = PROJECT_ROOT / "seed" / "seed_watchlist.json"


# --------------------------------------------------------------- USITC API ---

# list of HTS releases, used to detect a new one
URL = "https://hts.usitc.gov/reststop/releaseList"

# the full current schedule as JSON (all chapters, 0101 to 9999)
HTS_EXPORT_URL = "https://hts.usitc.gov/reststop/exportList?from=0101&to=9999&format=JSON&styles=false"

# identifies this program to USITC's servers
USER_AGENT = "CodeRead-HTS-Monitor/0.1 (GMU Challenge X; contact: ENTER HERE)"


# --------------------------------------------------------------- HTS rules ---

# HTS codes are 4 (heading), 6 (subheading), 8 (tariff line), or 10 (statistical) digits
VALID_CODE_LENGTHS = {4, 6, 8, 10}
