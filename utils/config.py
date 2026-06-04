import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CONFIG_FILE = BASE_DIR / "settings.json"

DEFAULT_CONFIG = {
    "download_dir": str(BASE_DIR / "downloads"),
    "youtube": {
        "audio_quality": "320k",
        "auto_retry": True,
        "max_retries": 3,
        "quiet_mode": True
    },
    "spotify": {
        "client_id": "",
        "client_secret": "",
        "audio_quality": "320k",
        "auto_retry": True,
        "max_retries": 3,
        "quiet_mode": True
    },
    "common": {
        "enable_logging": True,
        "history_limit": 100
    }
}

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                # Merge with defaults (add missing keys)
                for section, defaults in DEFAULT_CONFIG.items():
                    if section not in user_config:
                        user_config[section] = defaults
                    else:
                        if isinstance(defaults, dict):
                            for key, val in defaults.items():
                                if key not in user_config[section]:
                                    user_config[section][key] = val
                return user_config
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Could not save config: {e}")