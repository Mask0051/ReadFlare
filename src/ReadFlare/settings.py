import json
from database import get_value, set_value, SETTINGS_TABLE
import settings

DEFAULTS = {
    "email_enabled": False,
    "email_from": "",
    "email_recipients": [],
    "smtp_host": "",
    "smtp_port": 587,
    "smtp_use_tls": True,
    "smtp_user": "",
    "check_interval_minutes": 30,
    "fallback_timestamp": 1791388510,
    "track_ch99_links": False
    
}

EMAIL_PRESETS = {
    "internal_relay": {"smtp_port": 25,   "smtp_use_tls": False, "smtp_user": ""},
    "microsoft365": {"smtp_host": "smtp.office365.com", "smtp_port": 587, "smtp_use_tls": True},
    "gmail": {"smtp_host": "smtp.gmail.com",     "smtp_port": 587, "smtp_use_tls": True},
    "amazon_ses": {"smtp_port": 587,  "smtp_use_tls": True},   # host depends on region
    "mailpit": {"smtp_host": "localhost", "smtp_port": 1025, "smtp_use_tls": False, "smtp_user": ""},
}

def apply_email_preset(name):
    for key, value in EMAIL_PRESETS[name].items():
        settings.set_setting(key, value)

def set_setting(key, value):
    if key not in DEFAULTS:
        raise KeyError(f"Unknown setting: {key}")

    excepted = type(DEFAULTS[key])
    if not isinstance(value, excepted):
        raise TypeError(f"{key} must be {excepted.__name__}")

    #store in json
    set_value(table=SETTINGS_TABLE, key=key, value=json.dumps(value))

def get_setting(key):
    if key not in DEFAULTS:
        raise KeyError(f"Unknown setting: {key}")

    raw= get_value(table=SETTINGS_TABLE, key=key)

    if(raw is not None):
        return json.loads(raw)
    else:
        return DEFAULTS[key]

def get_all_settings():
    #returns a dict of key-value of settings.
    #returns user defined settings or default.
    return {key: get_setting(key) for key in DEFAULTS}


