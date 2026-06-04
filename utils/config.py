import json
from pathlib import Path
from .ffmpeg import get_ffmpeg_path

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
    """Load configuration from file, merge with defaults, and add ffmpeg_path."""
    config = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                # Recursively merge user config into defaults
                for section, values in user_config.items():
                    if section in config:
                        if isinstance(values, dict):
                            config[section].update(values)
                        else:
                            config[section] = values
                    else:
                        config[section] = values
        except Exception:
            pass
    # Add ffmpeg path dynamically (not stored in file)
    config['ffmpeg_path'] = get_ffmpeg_path()
    return config

def save_config(config):
    """Save configuration to file (excluding runtime ffmpeg_path)."""
    to_save = {k: v for k, v in config.items() if k != 'ffmpeg_path'}
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(to_save, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Could not save config: {e}")