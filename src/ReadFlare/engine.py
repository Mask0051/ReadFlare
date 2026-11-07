import requests
import json
from enum import Enum
from config import USER_AGENT, URL, LATEST_EDITION_PATH, HTS_EXPORT_URL, EDITIONS_DIR, DATA_DIR, RELEASES_CACHE_PATH

#the statuses used by the engine for update checks
class TrackerStatus(Enum):
    NEW_UPDATE = "NEW_UPDATE"
    NO_CHANGE = "NO_CHANGE"
    DATA_ERROR = "DATA_ERROR"
    FETCH_ERROR = "FETCH_ERROR"


#returns with a Enum Status and max_timestamp if new update is detected.
#TrackerStatus.NEW_UPDATE if a fresh drop is identified
#TrackerStatus.NO_CHANGE if the timestamp is identical
#TrackerStatus.DATA_ERROR if a timestamp anomaly is detected
def checkChange(parsed_json, last_timestamp):
    release = {}
    if(len(parsed_json) > 0):
        try:
            #get most recent release
            release = max(parsed_json, key=lambda x: x["id"]["timestamp"])
            max_timestamp = release["id"]["timestamp"]
        except (TypeError, KeyError) as e:
            print(f"ERROR: {e}")
            return TrackerStatus.DATA_ERROR, last_timestamp, {}

        if(max_timestamp > last_timestamp):
            #new entry detected
            return TrackerStatus.NEW_UPDATE, max_timestamp, release
        elif(max_timestamp < last_timestamp):
            #new entry is older than last timestamp
            return TrackerStatus.DATA_ERROR, last_timestamp, release

        #default return is NO_CHANGE
        return TrackerStatus.NO_CHANGE, last_timestamp, release
    else:
        #empty data
        return TrackerStatus.DATA_ERROR, last_timestamp, release

def fetch_releases():
    headers = {"User-Agent": USER_AGENT}
    res = requests.get(URL, headers=headers, timeout=20)
    res.raise_for_status()
    parsed_json = res.json()

    # keep a copy so the dashboard shows exactly what the monitor last saw
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = RELEASES_CACHE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(parsed_json), encoding="utf-8")
    tmp.replace(RELEASES_CACHE_PATH)

    return parsed_json

def load_cached_releases():
    # last releases list the monitor fetched; falls back to the sample file if none yet
    path = RELEASES_CACHE_PATH if RELEASES_CACHE_PATH.exists() else DATA_DIR / "dl" / "sample_data.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load_sample_data():

    #using locally saved response for testing logic
    with open(DATA_DIR /"dl"/"sample_data.json", "r") as file:
        parsed_json = json.load(file)
    return parsed_json

#fetch latest release from the server
#returns True is successful, false if not
def fetch_latest_edition():
    print("Fetching Latest Edition")
    headers = {"User-Agent": USER_AGENT}

    try:
        res = requests.get(HTS_EXPORT_URL, headers=headers, timeout=120)
        res.raise_for_status()
        data = res.json()
    except (requests.RequestException, ValueError) as e:
        print(f"Failed to Fetch Latest Edition: {e}")
        return False

    #create the editions dir if not exists
    EDITIONS_DIR.mkdir(parents=True, exist_ok=True)

    #write to a temp file first then switch to json
    #if it crashes mid write, it will not be a broken json
    tmp_path = LATEST_EDITION_PATH.with_suffix(".tmp")
    with open(tmp_path,"w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False)
    tmp_path.replace(LATEST_EDITION_PATH)

    return True


